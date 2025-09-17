"""File-based repository for persisting user settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ...application.user_settings.ports import SettingsRepository
from ...domain.user_settings.models import UserSettings, user_settings_from_dict, user_settings_to_dict


def default_settings_path() -> Path:
    """Return the default settings file path under the user's config directory."""

    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        base_dir = Path(xdg_config)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / "cogito" / "settings.json"


class JsonFileSettingsRepository(SettingsRepository):
    """Persist settings as JSON on disk."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or default_settings_path()

    def load(self) -> UserSettings:
        try:
            if not self._path.exists():
                return UserSettings()
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return UserSettings()
        except json.JSONDecodeError as exc:  # noqa: BLE001 - surface as higher-level error
            raise ValueError(f"Settings file {self._path} contains invalid JSON.") from exc

        return user_settings_from_dict(data)

    def save(self, settings: UserSettings) -> None:
        payload = user_settings_to_dict(settings)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)


__all__ = ["JsonFileSettingsRepository", "default_settings_path"]
