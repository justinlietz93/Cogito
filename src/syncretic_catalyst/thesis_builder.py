"""Command line entrypoint for the thesis builder workflow."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Sequence

from .ai_clients import AIOrchestrator
from .application.thesis import ThesisBuilderService
from .domain import DEFAULT_AGENT_PROFILES, ThesisResearchResult
from .infrastructure import (
    ArxivReferenceService,
    FileSystemThesisOutputRepository,
    OrchestratorContentGenerator,
    SystemClock,
)

_LOGGER = logging.getLogger(__name__)


def build_thesis(
    concept: str,
    *,
    model: str | None = None,
    force_fallback: bool = False,
    output_dir: str = "syncretic_output",
    max_papers: int = 50,
) -> ThesisResearchResult:
    """Run the thesis builder workflow for the provided concept."""

    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.info("Starting Syncretic Catalyst Thesis Builder")

    orchestrator = AIOrchestrator(model_name=model)
    generator = OrchestratorContentGenerator(orchestrator)
    reference_service = ArxivReferenceService(
        cache_root=Path("storage"), force_fallback=force_fallback
    )
    repository = FileSystemThesisOutputRepository(Path(output_dir))
    clock = SystemClock()

    service = ThesisBuilderService(
        reference_service=reference_service,
        output_repository=repository,
        content_generator=generator,
        clock=clock,
        agent_profiles=DEFAULT_AGENT_PROFILES,
    )

    start = time.time()
    result = service.build_thesis(concept, max_papers=max_papers)
    duration = time.time() - start

    _LOGGER.info("Research completed in %.2f seconds", duration)
    _LOGGER.info("Retrieved %s papers", len(result.papers))
    _LOGGER.info("Generated outputs for %s agents", len(result.agent_outputs))
    _LOGGER.info("Output files saved to %s", output_dir)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a comprehensive thesis from a concept using multi-agent research",
    )
    parser.add_argument("concept", help="The concept, theory, or hypothesis to research")
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
        default="syncretic_output",
        help="Directory for output files",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=50,
        help="Maximum number of papers to retrieve",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        build_thesis(
            concept=args.concept,
            model=args.model,
            force_fallback=args.force_fallback,
            output_dir=args.output_dir,
            max_papers=args.max_papers,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        _LOGGER.error("Thesis builder failed: %s", exc)
        raise
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
