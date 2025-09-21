"""Execution-path tests for the CLI application."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.application.critique.exceptions import ConfigurationError, MissingApiKeyError
from src.application.user_settings.services import SettingsPersistenceError
from src.pipeline_input import EmptyPipelineInputError, PipelineInput
from src.presentation.cli.app import DirectoryInputDefaults

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

    assert "No input selected" in messages[0]
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
        pipeline_input=pipeline_input,
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
    assert any("LaTeX document saved" in msg for msg in messages)
    assert any("PDF document saved" in msg for msg in messages)
    assert ("set_default_output_dir", str(tmp_path)) in service.actions


def test_run_falls_back_to_literal_when_file_missing() -> None:
    app, messages, _service, runner, _prompts = make_app()
    literal_result = SimpleNamespace(
        critique_report="report",
        peer_review_enabled=False,
        scientific_mode_enabled=False,
        module_config={},
        pipeline_input=PipelineInput(content="missing.txt"),
    )
    runner.run.return_value = literal_result

    args = SimpleNamespace(
        input_file="missing.txt",
        input_dir=None,
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

    assert any("Input file not found; treating value as literal text." in msg for msg in messages)
    invoked_descriptor = runner.run.call_args.args[0]
    assert invoked_descriptor.text == "missing.txt"


def test_directory_request_uses_configuration_defaults(tmp_path: Path) -> None:
    """Ensure CLI directory requests inherit defaults from configuration.

    Args:
        tmp_path: Pytest-provided temporary directory used to simulate roots.

    Returns:
        None.

    Raises:
        AssertionError: If resolved request values differ from the configured defaults.

    Side Effects:
        None. The test only instantiates DTOs.

    Timeout:
        Not applicable.
    """

    defaults = DirectoryInputDefaults(
        include=("**/*.rst",),
        exclude=("**/skip/**",),
        recursive=False,
        max_files=5,
        max_chars=2500,
        section_separator="\n==\n",
        label_sections=False,
        enabled=True,
    )
    app, _messages, _service, _runner, _prompts = make_app(directory_defaults=defaults)

    args = SimpleNamespace(
        input_file=None,
        input_dir=str(tmp_path),
        include=None,
        exclude=None,
        order=None,
        order_from=None,
        recursive=None,
        label_sections=None,
        max_files=None,
        max_chars=None,
        section_separator=None,
    )

    descriptor, warning = app._build_cli_input(args)

    assert warning is None
    assert descriptor is not None
    assert descriptor.include == defaults.include
    assert descriptor.exclude == defaults.exclude
    assert descriptor.recursive is defaults.recursive
    assert descriptor.max_files == defaults.max_files
    assert descriptor.max_chars == defaults.max_chars
    assert descriptor.section_separator == defaults.section_separator
    assert descriptor.label_sections is defaults.label_sections



def test_directory_input_disabled_emits_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Verify disabling directory ingestion surfaces a user-friendly message.

    Args:
        caplog: Pytest fixture capturing log output for assertions.

    Returns:
        None.

    Raises:
        AssertionError: If the CLI proceeds despite directory ingestion being disabled.

    Side Effects:
        Writes to the captured logging fixture and appends to the fake message list.

    Timeout:
        Not applicable.
    """

    defaults = DirectoryInputDefaults(enabled=False)
    app, messages, _service, runner, _prompts = make_app(directory_defaults=defaults)
    runner.run.side_effect = AssertionError("Runner should not be invoked")

    args = SimpleNamespace(
        input_file=None,
        input_dir="/tmp/docs",
        include=None,
        exclude=None,
        order=None,
        order_from=None,
        recursive=None,
        label_sections=None,
        max_files=None,
        max_chars=None,
        section_separator=None,
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

    with caplog.at_level("WARNING"):
        app.run(args, interactive=False)

    assert any("Directory input has been disabled" in msg for msg in messages)
    assert "disabled via configuration" in caplog.text
    runner.run.assert_not_called()


def test_execute_run_reports_pipeline_input_errors(tmp_path: Path) -> None:
    """Surface pipeline input errors with a user-friendly message."""

    app, messages, _service, runner, _prompts = make_app()
    runner.run.side_effect = EmptyPipelineInputError('empty')

    app._execute_run(
        PipelineInput(content='data'),
        tmp_path,
        peer_review=None,
        scientific_mode=None,
        latex_args=None,
        remember_output=False,
    )

    assert messages[-1] == 'Failed to load input: empty'

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
    runner.run.side_effect = FileNotFoundError("missing.txt")

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
        pipeline_input=PipelineInput(content="value", source="paper.md", metadata={"meta": "x"}),
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
        pipeline_input=PipelineInput(content="body"),
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
        pipeline_input=PipelineInput(content="body"),
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
