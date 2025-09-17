"""Application workflow for the Syncretic Catalyst CLI."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Sequence

from ..ai_clients import AIOrchestrator
from ..domain import FrameworkStep, ProjectFile
from ..infrastructure import ProjectFileRepository


class WorkflowAbort(Exception):
    """Raised when the user opts to abort the workflow."""


@dataclass
class WorkflowIO:
    """Abstraction over user-interaction primitives."""

    display: Callable[[str], None]
    prompt: Callable[[str], str]


class BreakthroughWorkflow:
    """Coordinates the end-to-end breakthrough workflow."""

    def __init__(
        self,
        orchestrator: AIOrchestrator,
        repository: ProjectFileRepository,
        steps: Sequence[FrameworkStep],
        io: WorkflowIO,
    ) -> None:
        self.orchestrator = orchestrator
        self.repository = repository
        self.steps = list(steps)
        self.io = io

    # Public API ------------------------------------------------------------
    def run(self, initial_vision: str = "", auto_yes: bool = False) -> None:
        self._warn_platform()

        user_vision = self._resolve_initial_vision(initial_vision, auto_yes)
        user_vision = self._maybe_collect_follow_ups(user_vision, auto_yes)

        for message in self.repository.prepare_workspace():
            self.io.display(message)

        file_map = self.repository.load()
        step_outputs: Dict[int, str] = {}

        for step in self.steps:
            self._execute_step(step, user_vision, step_outputs, file_map, auto_yes)

        self.io.display("\n=== Breakthrough Idea Process Completed ===")
        self.io.display("You can check 'some_project/doc/' for your breakthrough blueprint files.")

    # Internal helpers ------------------------------------------------------
    def _warn_platform(self) -> None:
        if sys.platform == "win32":
            self.io.display("INFO: Running on Windows. Using platform-compatible path handling.")
            self.io.display(
                "NOTE: When viewing file paths in the AI's response, paths may use forward slashes,"
            )
            self.io.display(
                "      but they will be converted to Windows backslashes when saving files.\n"
            )

    def _resolve_initial_vision(self, initial_vision: str, auto_yes: bool) -> str:
        user_vision = initial_vision
        prompt_file = Path("user_prompt.txt")
        if not user_vision and prompt_file.exists():
            try:
                file_content = prompt_file.read_text(encoding="utf-8").strip()
            except Exception as exc:  # pragma: no cover - defensive logging
                self.io.display(f"Error reading user_prompt.txt: {exc}")
                file_content = ""
            if file_content:
                self.io.display("\n=== FOUND USER_PROMPT.TXT ===")
                self.io.display("Preview of user_prompt.txt:")
                self.io.display("---")
                preview = file_content[:200] + ("..." if len(file_content) > 200 else "")
                self.io.display(preview)
                self.io.display("---")

                if auto_yes:
                    self.io.display("Auto-yes enabled: Using user_prompt.txt as domain/challenge.")
                    user_vision = file_content
                else:
                    use_file = self.io.prompt("Use this content as your domain/challenge? (y/n): ").strip().lower()
                    if use_file == "y":
                        user_vision = file_content
                        self.io.display("Using user_prompt.txt as domain/challenge.")

        if not user_vision:
            self.io.display("=== INITIAL DOMAIN OR CHALLENGE ===")
            user_vision = self.io.prompt(
                "Describe the domain or challenge you want breakthrough ideas for (a line or paragraph): "
            )
        return user_vision

    def _maybe_collect_follow_ups(self, user_vision: str, auto_yes: bool) -> str:
        if auto_yes:
            self.io.display("Auto-yes enabled: Skipping follow-up questions.")
            ask_q = "n"
        else:
            ask_q = self.io.prompt(
                "Should the AI ask follow-up questions about your domain/challenge? (y/n): "
            ).strip().lower()

        if ask_q != "y":
            return user_vision

        conversation: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI that clarifies the user's domain or challenge. "
                    "Ask short follow-up questions to fully understand the user's needs."
                ),
            },
            {"role": "user", "content": user_vision},
        ]

        while True:
            question = self._generate_follow_up_question(conversation)
            self.io.display("\nAI asks:\n " + question)
            user_ans = self.io.prompt("Your answer (type 'done' to finish Q&A): ")
            if user_ans.strip().lower() == "done":
                break
            conversation.append({"role": "assistant", "content": question})
            conversation.append({"role": "user", "content": user_ans})

        additions = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in conversation if msg["role"] == "user"
        )
        return user_vision + "\n\nAdditional Clarifications:\n" + additions

    def _generate_follow_up_question(self, conversation: List[Dict[str, str]]) -> str:
        system_prompt = conversation[0]["content"]
        history = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in conversation[1:]
        )
        return self.orchestrator.call_llm(
            system_prompt,
            history,
            max_tokens=20000,
            step_number=0,
        )

    def _execute_step(
        self,
        step: FrameworkStep,
        user_vision: str,
        step_outputs: Dict[int, str],
        file_map: Dict[str, ProjectFile],
        auto_yes: bool,
    ) -> None:
        while True:
            self.io.display(f"\n=== {step.phase_name} ===")
            if auto_yes:
                self.io.display("Auto-yes enabled: Proceeding with this step.")
                decision = "y"
            else:
                decision = self.io.prompt(
                    "Proceed with this step? (y = proceed, s = skip, q = quit): "
                ).strip().lower()

            if decision == "q":
                self.io.display("Exiting.")
                raise WorkflowAbort()
            if decision == "s":
                self.io.display(f"Skipping {step.phase_name}.")
                return
            if decision != "y":
                self.io.display("Invalid choice. Please enter 'y', 's', or 'q'.")
                continue

            user_prompt = self._build_user_prompt(step, user_vision, step_outputs)
            ai_response = self.orchestrator.call_llm(
                step.system_prompt,
                user_prompt,
                max_tokens=30000,
                step_number=step.index,
            )
            self.io.display("\nAI Response:\n" + ai_response)

            if auto_yes:
                self.io.display("Auto-yes enabled: Applying changes.")
                apply_choice = "y"
            else:
                apply_choice = self.io.prompt(
                    "Apply changes (create/update files in some_project)? (y = apply, r = retry step, n = skip step): "
                ).strip().lower()

            if apply_choice == "r":
                self.io.display("Repeating this step...\n")
                continue

            if apply_choice == "y":
                for message in self.repository.apply_ai_response(ai_response, file_map):
                    self.io.display(message)

                if step.output_file:
                    self.io.display(
                        f"DIRECT WRITE: Creating {step.output_file} regardless of file markers..."
                    )
                    file_map[step.output_file] = ProjectFile(
                        step.output_file,
                        f"# {step.phase_name}\n\n{ai_response}",
                    )

                for message in self.repository.save_all(file_map):
                    self.io.display(message)

            else:
                self.io.display("Skipping file changes.")

            step_outputs[step.index] = ai_response
            return

    def _build_user_prompt(
        self,
        step: FrameworkStep,
        user_vision: str,
        step_outputs: Dict[int, str],
    ) -> str:
        prompt = step.user_prompt_template.replace("{vision}", user_vision)
        for idx in range(1, step.index):
            placeholder = f"{{step{idx}}}"
            prompt = prompt.replace(placeholder, step_outputs.get(idx, "(No output)"))
        return prompt
