"""Tests for the interactive CLI application helpers."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline_input import PipelineInput
from src.presentation.cli.app import CliApp


@pytest.fixture
def cli_result() -> SimpleNamespace:
    return SimpleNamespace(
        critique_report="report",
        peer_review_enabled=False,
        scientific_mode_enabled=False,
        module_config={},
    )


def test_execute_run_handles_write_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cli_result: SimpleNamespace) -> None:
    settings_service = MagicMock()
    critique_runner = MagicMock()
    critique_runner.run.return_value = cli_result
    messages = []
    app = CliApp(settings_service, critique_runner, input_func=lambda _: "", output_func=messages.append)

    def failing_write_text(self: Path, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "write_text", failing_write_text, raising=False)

    app._execute_run(
        PipelineInput(content="body"),
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=False,
    )

    assert any(msg.startswith("Warning: Could not write critique report") for msg in messages)


def test_execute_run_handles_latex_exceptions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cli_result: SimpleNamespace) -> None:
    settings_service = MagicMock()
    critique_runner = MagicMock()
    critique_runner.run.return_value = cli_result
    messages = []
    app = CliApp(settings_service, critique_runner, input_func=lambda _: "", output_func=messages.append)

    latex_args = SimpleNamespace(
        latex=True,
        latex_compile=False,
        latex_output_dir=str(tmp_path / "latex"),
        latex_scientific_level="high",
        direct_latex=False,
    )

    def exploding_handler(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.presentation.cli.app.handle_latex_output", exploding_handler)

    app._execute_run(
        PipelineInput(content="body"),
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=latex_args,
        remember_output=False,
    )

    assert any("LaTeX generation failed" in msg for msg in messages)
