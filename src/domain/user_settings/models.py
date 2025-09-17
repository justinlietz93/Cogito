"""Domain models for user settings management."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class UserSettings:
    """Represents persisted user preferences for the CLI experience."""

    default_input_path: Optional[str] = None
    default_output_dir: Optional[str] = None
    preferred_provider: Optional[str] = None
    peer_review_default: bool = False
    scientific_mode_default: bool = False
    theme: str = "system"
    api_keys: Dict[str, str] = field(default_factory=dict)
    recent_files: List[str] = field(default_factory=list)
    config_path: Optional[str] = None


def user_settings_to_dict(settings: UserSettings) -> Dict[str, Any]:
    """Serialise :class:`UserSettings` into a JSON-friendly mapping."""

    return asdict(settings)


def user_settings_from_dict(raw: Optional[Mapping[str, Any]]) -> UserSettings:
    """Create a :class:`UserSettings` instance from persisted data."""

    if not raw:
        return UserSettings()

    known_fields = {
        "default_input_path": raw.get("default_input_path"),
        "default_output_dir": raw.get("default_output_dir"),
        "preferred_provider": raw.get("preferred_provider"),
        "peer_review_default": bool(raw.get("peer_review_default", False)),
        "scientific_mode_default": bool(raw.get("scientific_mode_default", False)),
        "theme": raw.get("theme", "system"),
        "api_keys": dict(raw.get("api_keys", {})),
        "recent_files": list(raw.get("recent_files", [])),
        "config_path": raw.get("config_path"),
    }

    return UserSettings(**known_fields)


__all__ = ["UserSettings", "user_settings_to_dict", "user_settings_from_dict"]
