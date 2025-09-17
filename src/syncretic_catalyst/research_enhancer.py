"""Command-line entrypoint for the research enhancement workflow."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Sequence

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

_LOGGER = logging.getLogger(__name__)


def enhance_research(
    *,
    model: str | None = None,
    force_fallback: bool = False,
    output_dir: str = "some_project",
    max_papers: int = 20,
    max_concepts: int | None = None,
) -> ResearchEnhancementResult:
    """Run the research enhancement workflow and return the resulting artefacts."""

    base_dir = Path(output_dir)
    orchestrator = AIOrchestrator(model_name=model)
    generator = OrchestratorContentGenerator(orchestrator)
    reference_service = ArxivReferenceService(
        cache_root=Path("storage"), force_fallback=force_fallback
    )
    repository = FileSystemResearchEnhancementRepository(base_dir)

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
    parser = argparse.ArgumentParser(
        description="Enhance research proposals using vector search and LLM analysis",
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
        help="Directory that contains the project documents and receives outputs",
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
            "No project documents were found in %%s. Populate the directory with Syncretic Catalyst"
            " outputs before running enhancement.",
            Path(args.output_dir) / "doc",
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive logging
        _LOGGER.error("Research enhancement failed: %s", exc)
        return 1
    return 0

