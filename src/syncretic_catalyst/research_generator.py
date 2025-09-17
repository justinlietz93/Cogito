"""CLI entrypoint for the research proposal generation workflow."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .ai_clients import AIOrchestrator
from .application.research_generation import ResearchProposalGenerationService
from .application.research_generation.exceptions import ProjectDocumentsNotFound
from .infrastructure.research_generation import FileSystemResearchGenerationRepository
from .infrastructure.thesis.ai_client import OrchestratorContentGenerator

_DEFAULT_MAX_TOKENS = 20_000


def build_service(
    project_dir: Path, *, model: str | None = None, default_max_tokens: int = _DEFAULT_MAX_TOKENS
) -> tuple[ResearchProposalGenerationService, FileSystemResearchGenerationRepository]:
    """Compose the generation service and its dependencies."""

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


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the research generation workflow."""

    parser = argparse.ArgumentParser(
        description="Generate an academic research proposal from project documents."
    )
    parser.add_argument(
        "--model",
        help=(
            "Optional provider override. If omitted the configured primary provider "
            "will be used."
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

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        service, repository = build_service(args.project_dir, model=args.model)
    except OSError as exc:
        print(
            f"Error: Failed to prepare project directory '{args.project_dir}': {exc}"
        )
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

    print(f"Prompt saved to {repository.prompt_path}")
    print(f"Research proposal saved to {repository.proposal_path}")
    print(f"Project title: {result.project_title}")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
