"""Settings and preference management tests for the CLI app."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest
from unittest.mock import MagicMock

from src.application.user_settings.services import InvalidPreferenceError, SettingsPersistenceError
from src.presentation.cli.app import CliApp

from .helpers import FakeSettings, FakeSettingsService, make_app


def test_preferences_menu_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = FakeSettings()
    settings.recent_files = ["a.md"]
    inputs = ["1", "2", "3", "4", "5", "6", "7", "x", "b"]
    app, messages, service, _runner, _prompts = make_app(
        input_values=inputs, settings_service=FakeSettingsService(settings)
    )
    calls: List[str] = []
    monkeypatch.setattr(app, "_handle_set_default_input", lambda: calls.append("input"))
    monkeypatch.setattr(app, "_handle_set_default_output", lambda: calls.append("output"))
    monkeypatch.setattr(app, "_handle_set_provider", lambda: calls.append("provider"))
    monkeypatch.setattr(app, "_prompt_bool", lambda message, default: calls.append(message) or True)
    monkeypatch.setattr(app, "_handle_set_config_path", lambda: calls.append("config"))

    app._preferences_menu()

    assert calls == [
        "input",
        "output",
        "provider",
        "Enable peer review by default",
        "Enable scientific methodology by default",
        "config",
    ]
    assert ("clear_recent_files", None) in service.actions
    assert any("Unrecognised option." in msg for msg in messages)


def test_preferences_menu_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    app, messages, _service, _runner, _prompts = make_app(input_values=["2", "b"])
    monkeypatch.setattr(
        app,
        "_handle_set_default_output",
        lambda: (_ for _ in ()).throw(SettingsPersistenceError("fail")),
    )

    app._preferences_menu()

    assert any("Failed to update preferences: fail" in msg for msg in messages)


def test_handle_set_default_input_updates_settings() -> None:
    app, _messages, service, _runner, _prompts = make_app(input_values=["~/doc.md"])

    app._handle_set_default_input()

    assert service.get_settings().default_input_path == "~/doc.md"


def test_handle_set_default_output_validates_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("", encoding="utf-8")
    app, _messages, _service, _runner, _prompts = make_app(input_values=[str(file_path)])

    with pytest.raises(InvalidPreferenceError):
        app._handle_set_default_output()


def test_handle_set_default_output_accepts_clear() -> None:
    app, _messages, service, _runner, _prompts = make_app(input_values=[""])
    service.get_settings().default_output_dir = "value"

    app._handle_set_default_output()

    assert service.get_settings().default_output_dir is None


def test_handle_set_provider_records_value() -> None:
    app, messages, service, _runner, _prompts = make_app(input_values=["anthropic"])

    app._handle_set_provider()

    assert service.get_settings().preferred_provider == "anthropic"
    assert "Preferred provider set to 'anthropic'." in messages[-1]


def test_handle_set_provider_clears_when_blank() -> None:
    app, messages, service, _runner, _prompts = make_app(input_values=[""])
    service.get_settings().preferred_provider = "openai"

    app._handle_set_provider()

    assert service.get_settings().preferred_provider is None
    assert "Preferred provider cleared." in messages[-1]


def test_handle_set_config_path_requires_existing_file(tmp_path: Path) -> None:
    app, _messages, _service, _runner, _prompts = make_app(
        input_values=[str(tmp_path / "missing.cfg")]
    )

    with pytest.raises(InvalidPreferenceError):
        app._handle_set_config_path()


def test_handle_set_config_path_updates_value(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("", encoding="utf-8")
    app, _messages, service, _runner, _prompts = make_app(input_values=[str(config_path)])

    app._handle_set_config_path()

    assert service.get_settings().config_path == str(config_path)


def test_api_keys_menu_manages_keys() -> None:
    settings = FakeSettings()
    settings.api_keys = {"openai": "abcdefghi"}
    inputs = ["1", "Anthropic", "key123", "2", "anthropic", "b"]
    app, messages, service, _runner, _prompts = make_app(
        input_values=inputs, settings_service=FakeSettingsService(settings)
    )

    app._api_keys_menu()

    assert service.get_settings().api_keys == {"openai": "abcdefghi"}
    assert any("Stored key for anthropic." in msg for msg in messages)
    assert any("Removed key for anthropic." in msg for msg in messages)
    assert any("abc***hi" in msg for msg in messages)


def test_api_keys_menu_handles_errors() -> None:
    settings = FakeSettings()
    service = FakeSettingsService(settings)
    service.failures["set_api_key"] = SettingsPersistenceError("fail")
    inputs = ["1", "anthropic", "key", "b"]
    app, messages, _service, _runner, _prompts = make_app(
        input_values=inputs, settings_service=service
    )

    app._api_keys_menu()

    assert any("Failed to update API keys: fail" in msg for msg in messages)


def test_display_settings_outputs_summary() -> None:
    settings = FakeSettings()
    settings.default_input_path = "input.md"
    settings.default_output_dir = "out"
    settings.preferred_provider = "anthropic"
    settings.peer_review_default = True
    settings.scientific_mode_default = False
    settings.config_path = "cfg.yml"
    settings.recent_files = ["file1", "file2"]
    settings.api_keys = {"openai": "abcdefghi"}

    messages: List[str] = []
    app = CliApp(
        FakeSettingsService(settings),
        MagicMock(),
        input_func=lambda _: "",
        output_func=messages.append,
    )

    app._display_settings()

    combined = "\n".join(messages)
    assert "Default input path: input.md" in combined
    assert "Preferred provider: anthropic" in combined
    assert "abc***hi" in combined
