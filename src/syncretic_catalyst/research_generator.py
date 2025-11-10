"""Research Proposal Generator CLI

Purpose:
- Provide a CLI workflow to generate an academic research proposal from project documents.
- Enforce ingestion ONLY from the repository INPUT/ directory and support an arbitrary number of files by aggregating them into the project workspace.
- Materialize the aggregated INPUT/ corpus into project_dir/doc/INPUT_AGGREGATED.md for downstream components (repositories/services) to consume.

External dependencies:
- CLI (argparse)
- File system access
- Providers are configured in higher layers (orchestrator/services) and may depend on environment keys

Fallback semantics:
- If INPUT/ contains no files, the command exits with error status (policy enforcement).
- If writing the aggregated file fails, the command exits with error status.

Timeout strategy:
- This module itself performs local orchestration; network timeouts are handled by provider gateways/services.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

# Orchestration and services
from .ai_clients import AIOrchestrator
from .application.research_generation import ResearchProposalGenerationService
from .application.research_generation.exceptions import ProjectDocumentsNotFound
from .infrastructure.research_generation import FileSystemResearchGenerationRepository
from .infrastructure.thesis.ai_client import OrchestratorContentGenerator

# Centralized ingestion utilities (INPUT-only, arbitrary file count)
from src.input_reader import find_all_input_files, concatenate_inputs

_DEFAULT_MAX_TOKENS = 20_000


def _aggregate_input_to_project(project_dir: Path) -> Path:
    """Aggregate all files from repository INPUT/ (recursive) into project_dir/doc/INPUT_AGGREGATED.md.

    This enforces that pipelines ingest only from INPUT/ and supports an arbitrary number
    of files via concatenation with file headers. The materialized file lives under the
    standard doc/ folder to align with repository expectations.

    Args:
        project_dir: The project workspace directory receiving artefacts and the aggregated INPUT corpus.

    Returns:
        Path to the materialized aggregated corpus file.

    Raises:
        FileNotFoundError: If INPUT/ does not exist or contains no files.
        OSError: If writing the aggregated file fails.
    """
    cogito_root = Path(__file__).resolve().parents[2]
    input_dir = cogito_root / "INPUT"
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"INPUT directory does not exist at {input_dir}")

    candidates = find_all_input_files(
        base_dir=str(cogito_root), input_dir_name="INPUT", recursive=True
    )
    if not candidates:
        raise FileNotFoundError(f"No input files found under {input_dir}")

    combined = concatenate_inputs(candidates)

    doc_dir = project_dir / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    out_path = doc_dir / "INPUT_AGGREGATED.md"
    out_path.write_text(combined, encoding="utf-8")
    return out_path


def build_service(
    project_dir: Path, *, model: str | None = None, default_max_tokens: int = _DEFAULT_MAX_TOKENS
) -> tuple[ResearchProposalGenerationService, FileSystemResearchGenerationRepository]:
    """Compose the generation service and its dependencies.

    Args:
        project_dir: Project workspace directory (contains doc/ and receives outputs).
        model: Optional provider override for the orchestrator.
        default_max_tokens: Default response token budget used by generator/service.

    Returns:
        A tuple of (service, repository) ready for proposal generation.
    """
    orchestrator = AIOrchestrator(model)
    generator = OrchestratorContentGenerator(
        orchestrator, default_max_tokens=default_max_tokens
    )
    repository = FileSystemResearchGenerationRepository(project_dir)
    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=repository,
        content_generator=generator,
        max_tokens=default_max_tokens,
    )
    return service, repository


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate an academic research proposal (INPUT-only ingestion; arbitrary file count supported)."
    )
    parser.add_argument(
        "--model",
        help=(
            "Optional provider override. If omitted the configured primary provider will be used."
        ),
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("some_project"),
        help="Project workspace containing the doc/ directory and output artefacts.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional override for the response token budget.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the research proposal generation workflow.

    Behaviour:
    - Aggregates INPUT/ content into project_dir/doc/INPUT_AGGREGATED.md (enforces INPUT-only ingestion).
    - Composes services/repositories and generates the proposal artefacts.
    """
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_dir: Path = args.project_dir
    project_dir.mkdir(parents=True, exist_ok=True)

    # Enforce INPUT-only ingestion and prepare unified corpus
    try:
        aggregated_path = _aggregate_input_to_project(project_dir)
        print(f"INGEST: Materialized aggregated INPUT corpus to {aggregated_path}")
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 2
    except OSError as exc:
        print(f"Error: Failed to write aggregated INPUT corpus: {exc}")
        return 2

    # Build and execute workflow
    try:
        service, repository = build_service(project_dir, model=args.model)
    except OSError as exc:
        print(f"Error: Failed to prepare project directory '{project_dir}': {exc}")
        return 1

    try:
        result = service.generate_proposal(max_tokens=args.max_tokens)
    except ProjectDocumentsNotFound as exc:
        print(f"Error: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1
    except OSError as exc:
        print(f"Error: Failed to write proposal artefacts: {exc}")
        return 1

    # Best-effort: print known output paths if repository exposes them
    try:
        if hasattr(repository, "prompt_path"):
            print(f"Prompt saved to {repository.prompt_path}")
        if hasattr(repository, "proposal_path"):
            print(f"Research proposal saved to {repository.proposal_path}")
    except Exception:
        # Avoid failing after successful generation for display-only paths
        pass

    # Report derived metadata if available
    try:
        print(f"Project title: {result.project_title}")
    except Exception:
        pass

    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
