from __future__ import annotations

from pathlib import Path

import pytest

from syncretic_catalyst import research_enhancer
from syncretic_catalyst.application.research_enhancement.exceptions import ProjectDocumentsNotFound
from syncretic_catalyst.domain import (
    EnhancedProposal,
    KeyConcept,
    ResearchEnhancementResult,
    ResearchGapAnalysis,
)
from syncretic_catalyst.domain.thesis import ResearchPaper


@pytest.fixture
def sample_result() -> ResearchEnhancementResult:
    return ResearchEnhancementResult(
        project_title="Catalyst",
        key_concepts=[KeyConcept("Concept")],
        papers=[ResearchPaper(identifier="p1", title="Paper", authors=("Ada",))],
        gap_analysis=ResearchGapAnalysis("Gap"),
        enhanced_proposal=EnhancedProposal("Proposal"),
    )


def test_enhance_research_composes_dependencies(
    monkeypatch: pytest.MonkeyPatch, sample_result: ResearchEnhancementResult
) -> None:
    created: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, model_name: str | None) -> None:
            created["model"] = model_name

    class FakeGenerator:
        def __init__(self, orchestrator: FakeOrchestrator) -> None:
            created["generator_orchestrator"] = orchestrator

    class FakeReferenceService:
        def __init__(self, cache_root: Path, force_fallback: bool) -> None:
            created["reference"] = (cache_root, force_fallback)

    class FakeRepository:
        def __init__(self, base_dir: Path) -> None:
            created["repository_base"] = base_dir

    class FakeService:
        def __init__(
            self,
            *,
            reference_service: FakeReferenceService,
            project_repository: FakeRepository,
            content_generator: FakeGenerator,
        ) -> None:
            created["service_args"] = (reference_service, project_repository, content_generator)

        def enhance(self, *, max_papers: int, max_concepts: int | None) -> ResearchEnhancementResult:
            created["enhance_args"] = (max_papers, max_concepts)
            return sample_result

    monkeypatch.setattr(research_enhancer, "AIOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(research_enhancer, "OrchestratorContentGenerator", FakeGenerator)
    monkeypatch.setattr(research_enhancer, "ArxivReferenceService", FakeReferenceService)
    monkeypatch.setattr(
        research_enhancer, "FileSystemResearchEnhancementRepository", FakeRepository
    )
    monkeypatch.setattr(research_enhancer, "ResearchEnhancementService", FakeService)

    result = research_enhancer.enhance_research(
        model="claude", force_fallback=True, output_dir="workspace", max_papers=4, max_concepts=7
    )

    assert result is sample_result
    assert created["model"] == "claude"
    assert created["reference"] == (Path("storage"), True)
    assert created["repository_base"] == Path("workspace")
    assert created["enhance_args"] == (4, 7)


def test_main_invokes_enhancement(monkeypatch: pytest.MonkeyPatch, sample_result: ResearchEnhancementResult) -> None:
    captured: dict[str, object] = {}

    def fake_enhance(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return sample_result

    monkeypatch.setattr(research_enhancer, "enhance_research", fake_enhance)

    exit_code = research_enhancer.main(
        [
            "--model",
            "gemini",
            "--force-fallback",
            "--output-dir",
            "workspace",
            "--max-papers",
            "3",
            "--max-concepts",
            "5",
        ]
    )

    assert exit_code == 0
    assert captured["model"] == "gemini"
    assert captured["force_fallback"] is True
    assert captured["output_dir"] == "workspace"
    assert captured["max_papers"] == 3
    assert captured["max_concepts"] == 5


def test_main_logs_when_documents_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_enhance(**kwargs):  # type: ignore[no-untyped-def]
        raise ProjectDocumentsNotFound("missing docs")

    monkeypatch.setattr(research_enhancer, "enhance_research", fake_enhance)
    logged: list[tuple[str, tuple[object, ...]]] = []

    def capture(message, *args):  # type: ignore[no-untyped-def]
        logged.append((str(message), args))

    monkeypatch.setattr(research_enhancer._LOGGER, "error", capture)
    exit_code = research_enhancer.main(["--output-dir", "workspace"])

    assert exit_code == 1
    assert any(
        "missing docs" in " ".join(str(arg) for arg in args) for _, args in logged
    )
    assert any("Populate the directory" in message for message, _ in logged)
