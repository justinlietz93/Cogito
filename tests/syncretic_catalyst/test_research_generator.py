from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace

import pytest

from syncretic_catalyst import research_generator
from syncretic_catalyst.application.research_generation.exceptions import ProjectDocumentsNotFound


def test_build_service_wires_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    class FakeOrchestrator:
        def __init__(self, model: str | None) -> None:
            created["model"] = model

    class FakeGenerator:
        def __init__(self, orchestrator: FakeOrchestrator, *, default_max_tokens: int) -> None:
            created["generator_tokens"] = default_max_tokens
            created["generator_orchestrator"] = orchestrator

    class FakeRepository:
        def __init__(self, project_dir: Path) -> None:
            created["repository_dir"] = project_dir
            self.prompt_path = project_dir / "prompt.txt"
            self.proposal_path = project_dir / "proposal.md"

    class FakeService:
        def __init__(
            self,
            *,
            project_repository: FakeRepository,
            output_repository: FakeRepository,
            content_generator: FakeGenerator,
            max_tokens: int,
        ) -> None:
            created["service_args"] = (
                project_repository,
                output_repository,
                content_generator,
                max_tokens,
            )
            self.generate_calls: list[int | None] = []

        def generate_proposal(self, *, max_tokens: int | None) -> SimpleNamespace:
            self.generate_calls.append(max_tokens)
            return SimpleNamespace(project_title="Title")

    monkeypatch.setattr(research_generator, "AIOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(research_generator, "OrchestratorContentGenerator", FakeGenerator)
    monkeypatch.setattr(
        research_generator, "FileSystemResearchGenerationRepository", FakeRepository
    )
    monkeypatch.setattr(research_generator, "ResearchProposalGenerationService", FakeService)

    service, repository = research_generator.build_service(
        Path("project"), model="deepseek", default_max_tokens=2048
    )

    assert isinstance(service, FakeService)
    assert repository is created["service_args"][0]
    assert created["generator_tokens"] == 2048
    assert created["service_args"][3] == 2048


def test_main_runs_generation(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeRepository:
        def __init__(self) -> None:
            self.prompt_path = Path("prompt.txt")
            self.proposal_path = Path("proposal.md")

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[int | None] = []

        def generate_proposal(self, *, max_tokens: int | None) -> SimpleNamespace:
            self.calls.append(max_tokens)
            return SimpleNamespace(project_title="Generated Title")

    fake_service = FakeService()
    fake_repository = FakeRepository()

    def fake_build(project_dir: Path, *, model: str | None) -> tuple[FakeService, FakeRepository]:
        assert project_dir == Path("workspace")
        assert model == "anthropic"
        return fake_service, fake_repository

    monkeypatch.setattr(research_generator, "build_service", fake_build)

    exit_code = research_generator.main(
        ["--model", "anthropic", "--project-dir", "workspace", "--max-tokens", "4096"]
    )

    assert exit_code == 0
    assert fake_service.calls == [4096]
    captured = capsys.readouterr()
    assert "Prompt saved to" in captured.out
    assert "Project title: Generated Title" in captured.out


def test_main_reports_build_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def failing_build(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("disk error")

    monkeypatch.setattr(research_generator, "build_service", failing_build)

    exit_code = research_generator.main(["--project-dir", "workspace"])

    assert exit_code == 1
    assert "Failed to prepare project directory" in capsys.readouterr().out


@pytest.mark.parametrize(
    "raised, expected",
    [
        (ProjectDocumentsNotFound("missing"), "Error: missing"),
        (RuntimeError("bad state"), "Error: bad state"),
        (OSError("write failure"), "Failed to write proposal artefacts"),
    ],
)
def test_main_handles_generation_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    raised: Exception,
    expected: str,
) -> None:
    class FakeRepository:
        prompt_path = Path("prompt")
        proposal_path = Path("proposal")

    class FakeService:
        def generate_proposal(self, *, max_tokens: int | None) -> SimpleNamespace:
            raise raised

    def fake_build(*args, **kwargs):  # type: ignore[no-untyped-def]
        return FakeService(), FakeRepository()

    monkeypatch.setattr(research_generator, "build_service", fake_build)

    exit_code = research_generator.main([])

    assert exit_code == 1
    assert expected in capsys.readouterr().out
