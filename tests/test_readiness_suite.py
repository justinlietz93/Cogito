"""Readiness validation ensuring the project builds and its tests pass."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

import pytest

pytestmark = pytest.mark.readiness_suite

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_command(description: str, command: Sequence[str], env: Mapping[str, str]) -> None:
    """Execute a command and fail the test with detailed output on error."""
    result = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        failure_details = (
            f"{description} failed with exit code {result.returncode}.\n"
            f"Command: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        pytest.fail(failure_details)


def test_application_builds_and_test_sweep_passes() -> None:
    """Ensure the codebase compiles and the full pytest sweep passes."""
    if os.environ.get("COGITO_SKIP_FULL_SWEEP") == "1":
        pytest.skip("Skipping readiness validation within nested pytest execution.")

    base_env = os.environ.copy()

    _run_command(
        "Python bytecode compilation",
        [sys.executable, "-m", "compileall", "src"],
        base_env,
    )

    sweep_env = base_env.copy()
    sweep_env["COGITO_SKIP_FULL_SWEEP"] = "1"

    _run_command(
        "Full pytest sweep",
        [sys.executable, "-m", "pytest", "--maxfail=1"],
        sweep_env,
    )
