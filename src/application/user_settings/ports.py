"""Ports for user settings persistence."""

from __future__ import annotations

from typing import Protocol

from ...domain.user_settings.models import UserSettings


class SettingsRepository(Protocol):
    """Abstraction for persisting :class:`UserSettings`."""

    def load(self) -> UserSettings:
        """Retrieve stored user settings."""

    def save(self, settings: UserSettings) -> None:
        """Persist updated user settings."""


__all__ = ["SettingsRepository"]
