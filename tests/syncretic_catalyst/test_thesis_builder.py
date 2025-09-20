from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from syncretic_catalyst import thesis_builder
from syncretic_catalyst.domain import AgentProfile, ResearchPaper, ThesisResearchResult


def make_result() -> ThesisResearchResult:
    return ThesisResearchResult(
        concept="Quantum",
        research_id="20240101_000000",
        timestamp=datetime(2024, 1, 1, 0, 0, 0),
        papers=[ResearchPaper(identifier="p1", title="Paper", authors=("Ada",))],
        agent_outputs=(),
        thesis="Synthesis",
    )


def test_build_thesis_wires_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
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
            created["repository"] = base_dir

    class FakeClock:
        def __init__(self) -> None:
            created["clock"] = True

    class FakeService:
        def __init__(
            self,
            *,
            reference_service: FakeReferenceService,
            output_repository: FakeRepository,
            content_generator: FakeGenerator,
            clock: FakeClock,
            agent_profiles: tuple[AgentProfile, ...],
        ) -> None:
            created["service_args"] = (
                reference_service,
                output_repository,
                content_generator,
                clock,
                agent_profiles,
            )

        def build_thesis(self, concept: str, *, max_papers: int) -> ThesisResearchResult:
            created["build_args"] = (concept, max_papers)
            return make_result()

    monkeypatch.setattr(thesis_builder, "AIOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(thesis_builder, "OrchestratorContentGenerator", FakeGenerator)
    monkeypatch.setattr(thesis_builder, "ArxivReferenceService", FakeReferenceService)
    monkeypatch.setattr(thesis_builder, "FileSystemThesisOutputRepository", FakeRepository)
    monkeypatch.setattr(thesis_builder, "SystemClock", FakeClock)
    monkeypatch.setattr(thesis_builder, "ThesisBuilderService", FakeService)

    result = thesis_builder.build_thesis(
        "Quantum Advantage",
        model="openai",
        force_fallback=True,
        output_dir="outputs",
        max_papers=5,
    )

    assert result == make_result()
    assert created["model"] == "openai"
    assert created["reference"] == (Path("storage"), True)
    assert created["repository"] == Path("outputs")
    assert created["build_args"] == ("Quantum Advantage", 5)


def test_main_invokes_build(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_build(**kwargs):  # type: ignore[no-untyped-def]
        called.update(kwargs)
        return make_result()

    monkeypatch.setattr(thesis_builder, "build_thesis", fake_build)

    exit_code = thesis_builder.main(
        [
            "Concept",
            "--model",
            "gemini",
            "--force-fallback",
            "--output-dir",
            "syncretic",
            "--max-papers",
            "9",
        ]
    )

    assert exit_code == 0
    assert called["concept"] == "Concept"
    assert called["model"] == "gemini"
    assert called["force_fallback"] is True
    assert called["output_dir"] == "syncretic"
    assert called["max_papers"] == 9
