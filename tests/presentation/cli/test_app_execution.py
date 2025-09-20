"""Execution-path tests for the CLI application."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.application.critique.exceptions import ConfigurationError, MissingApiKeyError
from src.application.user_settings.services import SettingsPersistenceError
from src.pipeline_input import PipelineInput

from .helpers import FakeSettings, FakeSettingsService, make_app


def test_run_requires_input_file() -> None:
    app, messages, _service, runner, _prompts = make_app()

    args = SimpleNamespace(
        input_file=None,
        output_dir=None,
        peer_review=None,
        scientific_mode=None,
        latex=False,
        latex_compile=False,
        latex_output_dir=None,
        latex_scientific_level="high",
        direct_latex=False,
        remember_output=False,
    )

    app.run(args, interactive=False)

    assert "No input file provided" in messages[0]
    runner.run.assert_not_called()


def test_run_executes_full_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_input = PipelineInput(
        content="body",
        metadata={"source_path": str(tmp_path / "input.md"), "fallback_reason": "file_not_found"},
    )
    service = FakeSettingsService(FakeSettings())
    runner = MagicMock()
    result = SimpleNamespace(
        critique_report="critique",
        peer_review_enabled=True,
        scientific_mode_enabled=True,
        module_config={"level": "high"},
    )
    runner.run.return_value = result
    app, messages, service, runner, _prompts = make_app(
        settings_service=service,
        critique_runner=runner,
    )

    fixed_now = datetime(2024, 1, 2, 3, 4, 5)
    monkeypatch.setattr("src.presentation.cli.app.datetime", SimpleNamespace(now=lambda: fixed_now))
    latex_dir = tmp_path / "latex"
    tex_path = latex_dir / "output.tex"
    pdf_path = latex_dir / "output.pdf"
    monkeypatch.setattr(
        "src.presentation.cli.app.handle_latex_output",
        lambda *args, **kwargs: (True, tex_path, pdf_path),
    )
    monkeypatch.setattr(
        "src.presentation.cli.app.format_scientific_peer_review",
        lambda **kwargs: "scientific",
    )

    args = SimpleNamespace(
        input_file=pipeline_input,
        output_dir=str(tmp_path),
        peer_review=True,
        scientific_mode=True,
        latex=True,
        latex_compile=True,
        latex_output_dir=str(latex_dir),
        latex_scientific_level="medium",
        direct_latex=True,
        remember_output=True,
    )

    app.run(args, interactive=False)

    timestamp = fixed_now.strftime("%Y%m%d_%H%M%S")
    critique_path = tmp_path / f"input_critique_{timestamp}.md"
    peer_path = tmp_path / f"input_peer_review_{timestamp}.md"

    assert critique_path.read_text(encoding="utf-8") == "critique"
    assert peer_path.read_text(encoding="utf-8") == "scientific"
    assert any("Input file not found; treating value as literal text." in msg for msg in messages)
    assert any("LaTeX document saved" in msg for msg in messages)
    assert any("PDF document saved" in msg for msg in messages)
    assert ("set_default_output_dir", str(tmp_path)) in service.actions


@pytest.mark.parametrize(
    "raised, expected",
    [
        (MissingApiKeyError("missing"), "Error: missing"),
        (ConfigurationError("config"), "Configuration error: config"),
    ],
)
def test_execute_run_handles_known_errors(
    raised: Exception, expected: str, tmp_path: Path
) -> None:
    pipeline_input = PipelineInput(content="body")
    app, messages, _service, runner, _prompts = make_app()
    runner.run.side_effect = raised

    app._execute_run(
        pipeline_input,
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=False,
    )

    assert expected in messages[-1]


def test_execute_run_handles_unexpected_exception(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pipeline_input = PipelineInput(content="body")
    app, messages, _service, runner, _prompts = make_app()
    runner.run.side_effect = RuntimeError("boom")

    with caplog.at_level("ERROR"):
        app._execute_run(
            pipeline_input,
            tmp_path,
            peer_review=None,
            scientific_mode=None,
            latex_args=None,
            remember_output=False,
        )

    assert "Critique execution failed" in caplog.text
    assert "Critique failed: boom" in messages[-1]


def test_execute_run_handles_missing_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.txt"
    app, messages, _service, runner, _prompts = make_app()
    runner.run.return_value = SimpleNamespace(
        critique_report="report",
        peer_review_enabled=False,
        scientific_mode_enabled=False,
        module_config={},
    )

    app._execute_run(
        missing_path,
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=False,
    )

    assert any("Input file not found" in msg for msg in messages)


def test_execute_run_handles_mapping_input(tmp_path: Path) -> None:
    app, messages, _service, runner, _prompts = make_app()
    runner.run.return_value = SimpleNamespace(
        critique_report="report",
        peer_review_enabled=False,
        scientific_mode_enabled=False,
        module_config={},
    )

    payload = {"content": "value", "source": "paper.md", "meta": "x"}

    app._execute_run(
        payload,
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=False,
    )

    critique_files = list(tmp_path.glob("*_critique_*.md"))
    assert critique_files, "Expected critique file to be written"
    assert messages


def test_execute_run_handles_output_dir_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, messages, _service, runner, _prompts = make_app()
    runner.run.return_value = SimpleNamespace(
        critique_report="report",
        peer_review_enabled=False,
        scientific_mode_enabled=False,
        module_config={},
    )

    def failing_mkdir(self: Path, *args, **kwargs) -> None:
        raise OSError("denied")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir, raising=False)

    app._execute_run(
        PipelineInput(content="body"),
        tmp_path / "out",
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=False,
    )

    assert any("Failed to prepare output directory" in msg for msg in messages)


def test_execute_run_handles_settings_persistence_error(tmp_path: Path) -> None:
    service = FakeSettingsService(FakeSettings())
    service.failures["set_default_output_dir"] = SettingsPersistenceError("nope")
    runner = MagicMock()
    runner.run.return_value = SimpleNamespace(
        critique_report="report",
        peer_review_enabled=False,
        scientific_mode_enabled=False,
        module_config={},
    )
    app, messages, _service, _runner, _prompts = make_app(
        settings_service=service,
        critique_runner=runner,
    )

    app._execute_run(
        PipelineInput(content="body"),
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=True,
    )

    assert any("Failed to remember output directory" in msg for msg in messages)
