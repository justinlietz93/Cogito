"""Research Enhancer CLI

Purpose:
- Provide a CLI workflow to enhance research proposals with vector search and LLM analysis.
- Enforce ingestion ONLY from the project INPUT/ directory and support an arbitrary number of files by aggregating them.
- Materialize the aggregated INPUT/ corpus into the project's output/doc/ folder for downstream components.

External dependencies:
- CLI (argparse)
- File system access
- ArXiv caching/vector backends used indirectly via infrastructure services

Fallback semantics:
- If INPUT/ contains no files, the enhancer proceeds without aggregated corpus (logs a warning).
- If vector store configuration is incomplete, service-layer fallbacks may apply (handled in infrastructure).

Timeout strategy:
- This module itself performs local orchestration; network timeouts are handled inside gateway/service implementations.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Optional, Sequence

# Application composition
from .ai_clients import AIOrchestrator
from .application.research_enhancement import (
    ProjectDocumentsNotFound,
    ResearchEnhancementService,
)
from .domain import ResearchEnhancementResult
from .infrastructure import (
    ArxivReferenceService,
    FileSystemResearchEnhancementRepository,
    OrchestratorContentGenerator,
)

# Centralized ingestion utilities
from src.input_reader import find_all_input_files, concatenate_inputs

_LOGGER = logging.getLogger(__name__)


def _ingest_input_corpus(*, cogito_root: Path, output_dir: Path) -> Optional[Path]:
    """Aggregate all files from INPUT/ (recursive) and write to output_dir/doc/.

    This enforces that pipelines ingest only from INPUT/ and supports an arbitrary
    number of files via concatenation with file headers.

    Args:
        cogito_root: Repository root (ancestor containing INPUT/).
        output_dir: Project output directory where the aggregated corpus should be materialized.

    Returns:
        Path to the materialized aggregated corpus file or None if no files were found.

    Raises:
        OSError: If writing the aggregated file fails.
    """
    input_dir = cogito_root / "INPUT"
    if not input_dir.exists() or not input_dir.is_dir():
        _LOGGER.warning("INPUT directory does not exist at %s", input_dir)
        return None

    try:
        candidates = find_all_input_files(
            base_dir=str(cogito_root), input_dir_name="INPUT", recursive=True
        )
    except Exception as exc:  # defensive logging
        _LOGGER.error("Failed to discover INPUT files: %s", exc)
        return None

    if not candidates:
        _LOGGER.warning("No input files found under %s", input_dir)
        return None

    _LOGGER.info("INGEST: Found %d input files under %s", len(candidates), input_dir)
    combined = concatenate_inputs(candidates)

    doc_dir = output_dir / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    out_path = doc_dir / "INPUT_AGGREGATED.md"
    out_path.write_text(combined, encoding="utf-8")
    _LOGGER.info("Materialized aggregated INPUT corpus to %s", out_path)
    return out_path


def enhance_research(
    *,
    model: str | None = None,
    force_fallback: bool = False,
    output_dir: str = "some_project",
    max_papers: int = 20,
    max_concepts: int | None = None,
) -> ResearchEnhancementResult:
    """Run the research enhancement workflow and return the resulting artefacts.

    Summary:
        Composes the enhancement service and executes the workflow. Prior to running
        the core enhancement, aggregates INPUT/ content into output_dir/doc/INPUT_AGGREGATED.md
        so downstream processes can utilize the unified corpus.

    Parameters:
        model: Optional provider override (orchestrator selects defaults if None).
        force_fallback: Force use of fallback vector store implementation.
        output_dir: Folder that receives generated artefacts and (now) contains the aggregated corpus.
        max_papers: Maximum number of papers to retrieve.
        max_concepts: Optional override for the maximum number of extracted key concepts.

    Returns:
        ResearchEnhancementResult with key concepts, papers, and paths to outputs.

    Raises:
        ProjectDocumentsNotFound: When expected project docs are missing for the workflow.
        OSError: On file system write failures for aggregated input.
    """
    base_dir = Path(output_dir)

    # Always prepare an orchestrator/generator
    orchestrator = AIOrchestrator(model_name=model)
    generator = OrchestratorContentGenerator(orchestrator)

    # Reference service (vector/metadata)
    reference_service = ArxivReferenceService(
        cache_root=Path("storage"), force_fallback=force_fallback
    )

    # Repositories
    repository = FileSystemResearchEnhancementRepository(base_dir)

    # INPUT-only ingestion and aggregation (materialize for downstream)
    cogito_root = Path(__file__).resolve().parents[2]
    try:
        _ingest_input_corpus(cogito_root=cogito_root, output_dir=base_dir)
    except OSError as exc:
        _LOGGER.error("Failed to write aggregated INPUT corpus: %s", exc)
        # Proceeding without the corpus would violate the INPUT-only policy;
        # however, we fail-fast here to keep the pipeline consistent.
        raise

    # Compose service
    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    _LOGGER.info("Starting Syncretic Catalyst research enhancement")
    start = time.time()

    result = service.enhance(max_papers=max_papers, max_concepts=max_concepts)

    duration = time.time() - start
    _LOGGER.info("Enhancement completed in %.2f seconds", duration)
    _LOGGER.info("Extracted %s key concepts", len(result.key_concepts))
    _LOGGER.info("Retrieved %s relevant papers", len(result.papers))
    _LOGGER.info("Outputs written to %s", base_dir)

    return result


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the research enhancer."""
    parser = argparse.ArgumentParser(
        description="Enhance research proposals using vector search and LLM analysis (INPUT-only ingestion).",
    )
    parser.add_argument(
        "--model",
        dest="model",
        help="Optional provider override (e.g. claude, deepseek, openai, gemini)",
    )
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Force use of the fallback vector store implementation",
    )
    parser.add_argument(
        "--output-dir",
        default="some_project",
        help="Directory that receives outputs (and INPUT_AGGREGATED.md under output_dir/doc/).",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=20,
        help="Maximum number of papers to retrieve during enhancement",
    )
    parser.add_argument(
        "--max-concepts",
        type=int,
        help="Optional override for the maximum number of key concepts to extract",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        enhance_research(
            model=args.model,
            force_fallback=args.force_fallback,
            output_dir=args.output_dir,
            max_papers=args.max_papers,
            max_concepts=args.max_concepts,
        )
    except ProjectDocumentsNotFound as exc:
        _LOGGER.error("%s", exc)
        _LOGGER.error(
            "No project documents were found in %s. Populate the directory with Syncretic Catalyst "
            "outputs before running enhancement.",
            Path(args.output_dir) / "doc",
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive logging
        _LOGGER.error("Research enhancement failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
