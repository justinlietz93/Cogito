"""Command-line interface for the Syncretic Catalyst orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from ..ai_clients import AIOrchestrator
from ..application import (
    BreakthroughWorkflow,
    WorkflowAbort,
    WorkflowIO,
    build_breakthrough_steps,
)
from ..infrastructure import ProjectFileRepository


USAGE = (
    "Usage: python orchestrator.py [--auto-yes|-y] <claude37sonnet|deepseekr1> [domain_challenge_description]"
)


def main(argv: Sequence[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])

    auto_yes = False
    for flag in ("--auto-yes", "-y"):
        if flag in args:
            auto_yes = True
            args.remove(flag)

    if not args:
        print(USAGE)
        print("  --auto-yes, -y : Automatically answer 'yes' to all prompts")
        return

    model_name = args[0].lower()
    user_vision = " ".join(args[1:]) if len(args) > 1 else ""

    orchestrator = AIOrchestrator(model_name)
    repository = ProjectFileRepository(Path("some_project"))
    steps = build_breakthrough_steps()
    io = WorkflowIO(display=print, prompt=input)
    workflow = BreakthroughWorkflow(orchestrator, repository, steps, io)

    try:
        workflow.run(initial_vision=user_vision, auto_yes=auto_yes)
    except WorkflowAbort:
        return


if __name__ == "__main__":  # pragma: no cover - manual execution path
    main()
