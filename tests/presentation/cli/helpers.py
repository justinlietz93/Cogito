"""Shared helpers for CLI presentation layer tests."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Tuple

from unittest.mock import MagicMock

from src.presentation.cli.app import CliApp, DirectoryInputDefaults
from src.presentation.cli.preflight import PreflightCliDefaults


class FakeSettings:
    """Minimal settings object used to satisfy the CLI app interactions."""

    def __init__(self) -> None:
        self.default_input_path: str | None = None
        self.default_output_dir: str | None = None
        self.preferred_provider: str | None = None
        self.peer_review_default: bool = False
        self.scientific_mode_default: bool = False
        self.config_path: str | None = None
        self.recent_files: List[str] = []
        self.api_keys: Dict[str, str] = {}


class FakeSettingsService:
    """In-memory settings service that records mutations for assertions."""

    def __init__(self, settings: FakeSettings | None = None) -> None:
        self._settings = settings or FakeSettings()
        self.actions: List[Tuple[str, object]] = []
        self.failures: Dict[str, Exception] = {}

    def get_settings(self) -> FakeSettings:
        return self._settings

    def set_default_input_path(self, value: str | None) -> None:
        self._maybe_raise("set_default_input_path")
        self._settings.default_input_path = value
        self.actions.append(("set_default_input_path", value))

    def set_default_output_dir(self, value: str | None) -> None:
        self._maybe_raise("set_default_output_dir")
        self._settings.default_output_dir = value
        self.actions.append(("set_default_output_dir", value))

    def set_preferred_provider(self, value: str | None) -> None:
        self._maybe_raise("set_preferred_provider")
        self._settings.preferred_provider = value or None
        self.actions.append(("set_preferred_provider", self._settings.preferred_provider))

    def set_peer_review_default(self, value: bool) -> None:
        self._maybe_raise("set_peer_review_default")
        self._settings.peer_review_default = value
        self.actions.append(("set_peer_review_default", value))

    def set_scientific_mode_default(self, value: bool) -> None:
        self._maybe_raise("set_scientific_mode_default")
        self._settings.scientific_mode_default = value
        self.actions.append(("set_scientific_mode_default", value))

    def set_config_path(self, value: str | None) -> None:
        self._maybe_raise("set_config_path")
        self._settings.config_path = value
        self.actions.append(("set_config_path", value))

    def clear_recent_files(self) -> None:
        self._maybe_raise("clear_recent_files")
        self._settings.recent_files = []
        self.actions.append(("clear_recent_files", None))

    def list_api_keys(self) -> Dict[str, str]:
        return dict(self._settings.api_keys)

    def set_api_key(self, provider: str, key: str) -> None:
        self._maybe_raise("set_api_key")
        normalised = provider.strip().lower()
        self._settings.api_keys[normalised] = key
        self.actions.append(("set_api_key", normalised))

    def remove_api_key(self, provider: str) -> None:
        self._maybe_raise("remove_api_key")
        self._settings.api_keys.pop(provider, None)
        self.actions.append(("remove_api_key", provider))

    def _maybe_raise(self, key: str) -> None:
        exc = self.failures.get(key)
        if exc:
            raise exc


def make_input(values: Iterable[str], prompts: List[str]) -> Callable[[str], str]:
    """Create an ``input`` replacement that iterates over predefined responses."""

    iterator = iter(values)

    def _input(prompt: str) -> str:
        prompts.append(prompt)
        try:
            return next(iterator)
        except StopIteration as exc:
            raise AssertionError(f"Unexpected prompt: {prompt}") from exc

    return _input


def make_app(
    *,
    input_values: Iterable[str] | None = None,
    settings_service: FakeSettingsService | None = None,
    critique_runner: MagicMock | None = None,
    directory_defaults: DirectoryInputDefaults | None = None,
    preflight_defaults: PreflightCliDefaults | None = None,
) -> Tuple[CliApp, List[str], FakeSettingsService, MagicMock, List[str]]:
    """Create a :class:`CliApp` wired with fake dependencies for testing."""

    prompts: List[str] = []
    messages: List[str] = []
    service = settings_service or FakeSettingsService()
    runner = critique_runner or MagicMock()
    input_func = make_input(input_values or [], prompts)
    app = CliApp(
        service,
        runner,
        directory_defaults=directory_defaults,
        preflight_defaults=preflight_defaults,
        input_func=input_func,
        output_func=messages.append,
    )
    return app, messages, service, runner, prompts


__all__ = [
    "FakeSettings",
    "FakeSettingsService",
    "make_app",
    "make_input",
]
