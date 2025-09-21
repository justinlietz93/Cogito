"""Interactive navigation and prompt tests for the CLI app."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest
from unittest.mock import MagicMock

from src.application.critique.requests import FileInputRequest
from src.presentation.cli.app import CliApp

from .helpers import FakeSettings, FakeSettingsService, make_app, make_input


def test_run_interactive_routes_to_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = ["1", "2", "3", "4", "q"]
    app, messages, _service, _runner, _prompts = make_app(input_values=inputs)
    called: List[str] = []
    monkeypatch.setattr(app._interactive, "_interactive_run_flow", lambda: called.append("run"))
    monkeypatch.setattr(app._interactive, "_preferences_menu", lambda: called.append("prefs"))
    monkeypatch.setattr(app._interactive, "_api_keys_menu", lambda: called.append("keys"))
    monkeypatch.setattr(app._interactive, "_display_settings", lambda: called.append("display"))

    app._run_interactive()

    assert called == ["run", "prefs", "keys", "display"]
    assert messages[-1] == "Goodbye!"


def test_interactive_run_flow_uses_prompts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service = FakeSettingsService(FakeSettings())
    app = CliApp(service, MagicMock(), input_func=lambda _: "", output_func=lambda _: None)

    input_path = tmp_path / "input.md"
    monkeypatch.setattr(app._interactive, "_prompt_for_input_path", lambda _settings: input_path)
    monkeypatch.setattr(app._interactive, "_prompt_for_output_directory", lambda _settings: tmp_path)
    monkeypatch.setattr(app._interactive, "_prompt_bool", lambda message, default: True)
    latex_args = SimpleNamespace(latex=True)
    monkeypatch.setattr(app._interactive, "_prompt_latex_options", lambda _output_dir: latex_args)
    calls: List[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        app._interactive,
        "execute_run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    app._interactive_run_flow()

    assert calls
    args, kwargs = calls[0]
    assert isinstance(args[0], FileInputRequest)
    assert args[0].path == input_path
    assert kwargs["latex_args"] is latex_args


def test_prompt_for_input_path_remembers_recent(tmp_path: Path) -> None:
    file_path = tmp_path / "paper.md"
    file_path.write_text("data", encoding="utf-8")
    settings = FakeSettings()
    settings.recent_files = [str(file_path)]
    settings.default_input_path = str(file_path)
    service = FakeSettingsService(settings)
    prompts: List[str] = []
    app = CliApp(
        service,
        MagicMock(),
        input_func=make_input(["1", "y"], prompts),
        output_func=lambda _: None,
    )

    result = app._prompt_for_input_path(settings)

    assert result == file_path
    assert settings.default_input_path == str(file_path)


def test_prompt_for_input_path_handles_missing(tmp_path: Path) -> None:
    settings = FakeSettings()
    service = FakeSettingsService(settings)
    prompts: List[str] = []
    messages: List[str] = []
    app = CliApp(
        service,
        MagicMock(),
        input_func=make_input([str(tmp_path / "missing.txt")], prompts),
        output_func=messages.append,
    )

    result = app._prompt_for_input_path(settings)

    assert result is None
    assert any("Input file not found" in msg for msg in messages)


def test_prompt_for_output_directory_validates_file(tmp_path: Path) -> None:
    file_path = tmp_path / "not_a_dir"
    file_path.write_text("", encoding="utf-8")
    settings = FakeSettings()
    service = FakeSettingsService(settings)
    messages: List[str] = []
    app = CliApp(
        service,
        MagicMock(),
        input_func=make_input([str(file_path), "y"], []),
        output_func=messages.append,
    )

    result = app._prompt_for_output_directory(settings)

    assert result.name == "critiques"
    assert any("not a directory" in msg for msg in messages)
    assert ("set_default_output_dir", str(result)) in service.actions


def test_prompt_bool_retries_until_valid() -> None:
    values = ["maybe", "y"]
    prompts: List[str] = []
    messages: List[str] = []
    app = CliApp(
        FakeSettingsService(FakeSettings()),
        MagicMock(),
        input_func=make_input(values, prompts),
        output_func=messages.append,
    )

    result = app._prompt_bool("Continue", False)

    assert result is True
    assert messages[-1] == "Please respond with 'y' or 'n'."


def test_prompt_latex_options_collects_configuration(tmp_path: Path) -> None:
    inputs = ["y", "n", "", "medium", "y"]
    app = CliApp(
        FakeSettingsService(FakeSettings()),
        MagicMock(),
        input_func=make_input(inputs, []),
        output_func=lambda _: None,
    )

    result = app._prompt_latex_options(tmp_path)

    assert result.latex is True
    assert result.latex_compile is False
    assert result.latex_output_dir == str(tmp_path / "latex_output")
    assert result.latex_scientific_level == "medium"
    assert result.direct_latex is True


def test_prompt_latex_options_can_decline(tmp_path: Path) -> None:
    app = CliApp(
        FakeSettingsService(FakeSettings()),
        MagicMock(),
        input_func=make_input(["n"], []),
        output_func=lambda _: None,
    )

    assert app._prompt_latex_options(tmp_path) is None
