from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List

import pytest

from syncretic_catalyst.application.workflow import (
    BreakthroughWorkflow,
    WorkflowAbort,
    WorkflowIO,
)
from syncretic_catalyst.domain import FrameworkStep, ProjectFile
from syncretic_catalyst.infrastructure.file_repository import ProjectFileRepository


class StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.responses: dict[int, str] = {}

    def set_response(self, step_number: int, response: str) -> None:
        self.responses[step_number] = response

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        step_number: int,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
                "step_number": step_number,
            }
        )
        return self.responses.get(step_number, f"question-{step_number}")


class StubRepository:
    def __init__(self) -> None:
        self.apply_calls: list[str] = []
        self.saved_maps: list[Dict[str, ProjectFile]] = []

    def prepare_workspace(self) -> list[str]:
        return []

    def load(self) -> Dict[str, ProjectFile]:
        return {}

    def apply_ai_response(self, response: str, file_map: Dict[str, ProjectFile]) -> list[str]:
        self.apply_calls.append(response)
        return []

    def save_all(self, file_map: Dict[str, ProjectFile]) -> list[str]:
        self.saved_maps.append({path: ProjectFile(pf.path, pf.content) for path, pf in file_map.items()})
        return []


class StubIO:
    def __init__(self, responses: Iterable[str] | None = None) -> None:
        self.messages: list[str] = []
        self.prompt_history: list[str] = []
        self._responses = iter(responses or [])

    def display(self, message: str) -> None:
        self.messages.append(message)

    def prompt(self, prompt: str) -> str:
        self.prompt_history.append(prompt)
        try:
            return next(self._responses)
        except StopIteration:  # pragma: no cover - indicates test misconfiguration
            raise AssertionError(f"Unexpected prompt: {prompt}")


def workflow_io(io: StubIO) -> WorkflowIO:
    return WorkflowIO(display=io.display, prompt=io.prompt)


def test_run_auto_yes_executes_full_workflow(tmp_path: Path) -> None:
    orchestrator = StubOrchestrator()
    orchestrator.set_response(1, "=== File: doc/STEP1.md ===\nFirst output")
    orchestrator.set_response(2, "=== File: doc/STEP2.md ===\nSecond output")

    repository = ProjectFileRepository(tmp_path / "project")
    io = StubIO()
    steps = [
        FrameworkStep(
            index=1,
            phase_name="Phase One",
            system_prompt="sys-1",
            user_prompt_template="Vision: {vision}",
            output_file="doc/STEP1.md",
        ),
        FrameworkStep(
            index=2,
            phase_name="Phase Two",
            system_prompt="sys-2",
            user_prompt_template="Prev step: {step1}",
            output_file="doc/STEP2.md",
        ),
    ]

    workflow = BreakthroughWorkflow(orchestrator, repository, steps, workflow_io(io))
    workflow.run("Initial vision", auto_yes=True)

    assert [call["step_number"] for call in orchestrator.calls] == [1, 2]
    assert "Initial vision" in orchestrator.calls[0]["user_prompt"]
    assert orchestrator.calls[1]["user_prompt"].startswith("Prev step:")
    project_root = tmp_path / "project"
    step1_content = (project_root / "doc" / "STEP1.md").read_text(encoding="utf-8")
    assert step1_content.startswith("# Phase One\n\n=== File")
    step2_content = (project_root / "doc" / "STEP2.md").read_text(encoding="utf-8")
    assert step2_content.startswith("# Phase Two\n\n=== File")
    assert any("Breakthrough Idea Process Completed" in msg for msg in io.messages)
    assert "Auto-yes enabled: Skipping follow-up questions." in io.messages
    assert io.prompt_history == []


def test_resolve_initial_vision_prefers_prompt_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "user_prompt.txt"
    file_path.write_text("Vision from file", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO(responses=["y"])
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    resolved = workflow._resolve_initial_vision("", auto_yes=False)

    assert resolved == "Vision from file"
    assert io.prompt_history[-1].startswith("Use this content")
    assert any("FOUND USER_PROMPT.TXT" in message for message in io.messages)


def test_resolve_initial_vision_auto_yes_reads_prompt_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "user_prompt.txt"
    file_path.write_text("Auto vision", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO()
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    resolved = workflow._resolve_initial_vision("", auto_yes=True)

    assert resolved == "Auto vision"
    assert "Auto-yes enabled: Using user_prompt.txt as domain/challenge." in io.messages


def test_resolve_initial_vision_prompts_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO(responses=["Manual vision"])

    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))
    resolved = workflow._resolve_initial_vision("", auto_yes=False)

    assert resolved == "Manual vision"
    assert "Describe the domain" in io.prompt_history[-1]


def test_maybe_collect_follow_ups_collects_until_done() -> None:
    orchestrator = StubOrchestrator()
    orchestrator.set_response(0, "What else do you need?")
    repository = StubRepository()
    io = StubIO(responses=["y", "Follow-up detail", "done"])
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    result = workflow._maybe_collect_follow_ups("Initial", auto_yes=False)

    assert "Additional Clarifications" in result
    assert "Follow-up detail" in result
    assert orchestrator.calls[0]["step_number"] == 0


def test_execute_step_handles_invalid_retry_and_skip() -> None:
    orchestrator = StubOrchestrator()
    orchestrator.set_response(1, "Step output")
    repository = StubRepository()
    io = StubIO(responses=["maybe", "y", "r", "y", "n"])
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    step = FrameworkStep(
        index=1,
        phase_name="Phase",
        system_prompt="system",
        user_prompt_template="Use {vision}",
    )
    step_outputs: Dict[int, str] = {}

    workflow._execute_step(step, "Vision", step_outputs, {}, auto_yes=False)

    assert any("Invalid choice" in message for message in io.messages)
    assert repository.apply_calls == []
    assert step_outputs[1] == "Step output"


def test_execute_step_skip_returns_without_llm() -> None:
    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO(responses=["s"])
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    step = FrameworkStep(
        index=1,
        phase_name="Phase",
        system_prompt="system",
        user_prompt_template="template",
    )

    workflow._execute_step(step, "Vision", {}, {}, auto_yes=False)

    assert orchestrator.calls == []


def test_execute_step_quit_raises_abort() -> None:
    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO(responses=["q"])
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    step = FrameworkStep(
        index=1,
        phase_name="Phase",
        system_prompt="system",
        user_prompt_template="template",
    )

    with pytest.raises(WorkflowAbort):
        workflow._execute_step(step, "Vision", {}, {}, auto_yes=False)


def test_warn_platform_emits_windows_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO()
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    workflow._warn_platform()

    assert any("Running on Windows" in message for message in io.messages)


def test_build_user_prompt_includes_prior_step_outputs() -> None:
    orchestrator = StubOrchestrator()
    repository = StubRepository()
    io = StubIO()
    workflow = BreakthroughWorkflow(orchestrator, repository, [], workflow_io(io))

    step = FrameworkStep(
        index=3,
        phase_name="Third",
        system_prompt="sys",
        user_prompt_template="Step1: {step1}\nStep2: {step2}\nVision: {vision}",
    )

    prompt = workflow._build_user_prompt(
        step,
        user_vision="Idea",
        step_outputs={1: "First", 2: "Second"},
    )

    assert "Step1: First" in prompt
    assert "Step2: Second" in prompt
    assert prompt.endswith("Vision: Idea")
