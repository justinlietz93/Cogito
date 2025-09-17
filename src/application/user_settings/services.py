"""Business logic for managing user settings."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Dict, Optional

from ...domain.user_settings.models import UserSettings
from .ports import SettingsRepository


class SettingsServiceError(Exception):
    """Base error raised for settings operations."""


class SettingsPersistenceError(SettingsServiceError):
    """Raised when settings cannot be persisted to storage."""


class InvalidPreferenceError(SettingsServiceError):
    """Raised when a provided preference value is invalid."""


class UserSettingsService:
    """Service responsible for orchestrating user preference management."""

    def __init__(self, repository: SettingsRepository, recent_limit: int = 5) -> None:
        self._repository = repository
        self._recent_limit = max(1, recent_limit)

        try:
            loaded = repository.load()
        except Exception as exc:  # noqa: BLE001 - infrastructure exceptions are normalised.
            raise SettingsPersistenceError("Failed to load user settings.") from exc

        if not isinstance(loaded, UserSettings):
            loaded = UserSettings()

        self._settings = self._normalise_loaded_settings(loaded)

    def get_settings(self) -> UserSettings:
        """Return a defensive copy of the current settings."""

        return deepcopy(self._settings)

    def set_default_input_path(self, path: Optional[str]) -> None:
        """Persist the default path used when prompting for critique input."""

        self._settings = replace(self._settings, default_input_path=self._normalise_path(path))
        self._save()

    def set_default_output_dir(self, directory: Optional[str]) -> None:
        """Persist the directory where critique reports should be stored."""

        self._settings = replace(
            self._settings,
            default_output_dir=self._normalise_path(directory),
        )
        self._save()

    def set_config_path(self, config_path: Optional[str]) -> None:
        """Persist a preferred configuration file path."""

        self._settings = replace(self._settings, config_path=self._normalise_path(config_path))
        self._save()

    def set_preferred_provider(self, provider: Optional[str]) -> None:
        """Persist the preferred LLM provider for critiques."""

        normalised = self._normalise_provider_name(provider)
        if provider and normalised is None:
            raise InvalidPreferenceError("Provider name cannot be empty.")

        self._settings = replace(self._settings, preferred_provider=normalised)
        self._save()

    def set_peer_review_default(self, enabled: bool) -> None:
        self._settings = replace(self._settings, peer_review_default=bool(enabled))
        self._save()

    def set_scientific_mode_default(self, enabled: bool) -> None:
        self._settings = replace(self._settings, scientific_mode_default=bool(enabled))
        self._save()

    def set_theme(self, theme: str) -> None:
        if not theme:
            raise InvalidPreferenceError("Theme name cannot be empty.")
        self._settings = replace(self._settings, theme=theme)
        self._save()

    def set_api_key(self, provider: str, api_key: str) -> None:
        provider_key = provider.strip().lower()
        if not provider_key:
            raise InvalidPreferenceError("Provider name cannot be empty.")
        if not api_key.strip():
            raise InvalidPreferenceError("API key cannot be empty.")

        api_keys = dict(self._settings.api_keys)
        api_keys[provider_key] = api_key.strip()
        self._settings = replace(self._settings, api_keys=api_keys)
        self._save()

    def remove_api_key(self, provider: str) -> None:
        provider_key = provider.strip().lower()
        if not provider_key:
            raise InvalidPreferenceError("Provider name cannot be empty.")

        api_keys = dict(self._settings.api_keys)
        api_keys.pop(provider_key, None)
        self._settings = replace(self._settings, api_keys=api_keys)
        self._save()

    def list_api_keys(self) -> Dict[str, str]:
        """Return a copy of the stored API keys."""

        return dict(self._settings.api_keys)

    def clear_recent_files(self) -> None:
        self._settings = replace(self._settings, recent_files=[])
        self._save()

    def record_recent_file(self, file_path: str) -> None:
        if not file_path:
            return

        absolute_path = self._normalise_path(file_path)
        existing = [entry for entry in self._settings.recent_files if self._normalise_path(entry) != absolute_path]
        updated = [absolute_path, *existing][: self._recent_limit]
        self._settings = replace(self._settings, recent_files=updated)
        self._save()

    def _save(self) -> None:
        try:
            self._repository.save(self._settings)
        except Exception as exc:  # noqa: BLE001 - infrastructure exceptions are normalised.
            raise SettingsPersistenceError("Failed to persist user settings.") from exc

    @staticmethod
    def _normalise_path(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        return str(Path(path).expanduser().resolve())

    def _normalise_loaded_settings(self, settings: UserSettings) -> UserSettings:
        preferred = self._normalise_provider_name(settings.preferred_provider)
        if preferred != settings.preferred_provider:
            settings = replace(settings, preferred_provider=preferred)
        return settings

    @staticmethod
    def _normalise_provider_name(provider: Optional[str]) -> Optional[str]:
        if provider is None:
            return None
        candidate = provider.strip()
        if not candidate:
            return None
        return candidate.lower()


__all__ = [
    "InvalidPreferenceError",
    "SettingsPersistenceError",
    "SettingsServiceError",
    "UserSettingsService",
]
