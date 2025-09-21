"""Directory input configuration defaults for the CLI.

Purpose:
    Store configurable defaults that influence directory ingestion argument handling for the CLI.
External Dependencies:
    Python standard library only.
Fallback Semantics:
    Missing configuration values fall back to class defaults.
Timeout Strategy:
    Not applicable at this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

__all__ = ["DirectoryInputDefaults"]


@dataclass(frozen=True)
class DirectoryInputDefaults:
    """Configuration defaults applied when building directory requests."""

    include: Tuple[str, ...] = ("**/*.md", "**/*.txt")
    exclude: Tuple[str, ...] = ("**/.git/**", "**/node_modules/**")
    recursive: bool = True
    max_files: Optional[int] = 200
    max_chars: Optional[int] = 1_000_000
    section_separator: str = "\n\n---\n\n"
    label_sections: bool = True
    enabled: bool = True

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "DirectoryInputDefaults":
        """Construct defaults from a configuration mapping."""

        defaults = cls()
        include = cls._coerce_patterns(config.get("include"), defaults.include)
        exclude = cls._coerce_patterns(config.get("exclude"), defaults.exclude)
        recursive = cls._coerce_bool(config.get("recursive"), defaults.recursive)
        max_files = cls._coerce_optional_int(config.get("max_files"), defaults.max_files)
        max_chars = cls._coerce_optional_int(config.get("max_chars"), defaults.max_chars)
        section_separator = (
            str(config.get("section_separator"))
            if isinstance(config.get("section_separator"), str)
            else defaults.section_separator
        )
        label_sections = cls._coerce_bool(config.get("label_sections"), defaults.label_sections)
        enabled = cls._coerce_bool(config.get("enabled"), defaults.enabled)
        return cls(
            include=include,
            exclude=exclude,
            recursive=recursive,
            max_files=max_files,
            max_chars=max_chars,
            section_separator=section_separator,
            label_sections=label_sections,
            enabled=enabled,
        )

    @staticmethod
    def _coerce_patterns(value: Any, default: Tuple[str, ...]) -> Tuple[str, ...]:
        """Normalise pattern configuration into a tuple of strings."""

        if value is None:
            return default
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(parts or default)
        if isinstance(value, (list, tuple, set)):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return tuple(parts or default)
        return default

    @staticmethod
    def _coerce_optional_int(value: Any, default: Optional[int]) -> Optional[int]:
        """Convert configuration values to optional integers."""

        if value is None:
            return default
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return default
        return numeric

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        """Convert configuration values to booleans while preserving default."""

        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
            return default
        return bool(value)
