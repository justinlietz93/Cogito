from __future__ import annotations

from types import SimpleNamespace

import pytest

from syncretic_catalyst.application import WorkflowAbort
from syncretic_catalyst.presentation import cli as orchestrator_cli


def test_main_displays_usage_when_no_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    orchestrator_cli.main([])

    captured = capsys.readouterr()
    assert orchestrator_cli.USAGE in captured.out
    assert "Automatically answer" in captured.out


def test_main_runs_workflow_with_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, orchestrator, repository, steps, io) -> None:  # type: ignore[no-untyped-def]
            captured["orchestrator"] = orchestrator
            captured["repository"] = repository
            captured["steps"] = steps
            captured["io"] = io

        def run(self, *, initial_vision: str, auto_yes: bool) -> None:  # type: ignore[no-untyped-def]
            captured["run_args"] = (initial_vision, auto_yes)

    class FakeRepository:
        def __init__(self, base_path) -> None:  # type: ignore[no-untyped-def]
            captured["repository_base"] = base_path

    def fake_build_steps():  # type: ignore[no-untyped-def]
        return [SimpleNamespace(name="step")]

    class FakeOrchestrator:
        def __init__(self, model_name: str) -> None:
            captured["model"] = model_name

    monkeypatch.setattr(orchestrator_cli, "AIOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(orchestrator_cli, "ProjectFileRepository", FakeRepository)
    monkeypatch.setattr(orchestrator_cli, "build_breakthrough_steps", fake_build_steps)
    monkeypatch.setattr(orchestrator_cli, "BreakthroughWorkflow", FakeWorkflow)

    orchestrator_cli.main([
        "--auto-yes",
        "claude37sonnet",
        "Build",
        "Breakthrough",
    ])

    assert captured["model"] == "claude37sonnet"
    assert captured["repository_base"] == orchestrator_cli.Path("some_project")
    assert captured["run_args"] == ("Build Breakthrough", True)


def test_main_respects_short_auto_yes_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def run(self, *, initial_vision: str, auto_yes: bool) -> None:  # type: ignore[no-untyped-def]
            captured["auto_yes"] = auto_yes
            captured["vision"] = initial_vision

    monkeypatch.setattr(orchestrator_cli, "BreakthroughWorkflow", FakeWorkflow)
    monkeypatch.setattr(orchestrator_cli, "AIOrchestrator", lambda model: object())
    monkeypatch.setattr(orchestrator_cli, "ProjectFileRepository", lambda path: object())
    monkeypatch.setattr(orchestrator_cli, "build_breakthrough_steps", lambda: [])

    orchestrator_cli.main(["-y", "deepseek", "Solve", "AI"])

    assert captured["auto_yes"] is True
    assert captured["vision"] == "Solve AI"


def test_main_swallows_workflow_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeWorkflow:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def run(self, *, initial_vision: str, auto_yes: bool) -> None:  # type: ignore[no-untyped-def]
            raise WorkflowAbort()

    monkeypatch.setattr(orchestrator_cli, "BreakthroughWorkflow", FakeWorkflow)
    monkeypatch.setattr(orchestrator_cli, "AIOrchestrator", lambda model: object())
    monkeypatch.setattr(orchestrator_cli, "ProjectFileRepository", lambda path: object())
    monkeypatch.setattr(orchestrator_cli, "build_breakthrough_steps", lambda: [])

    orchestrator_cli.main(["claude37sonnet"])
