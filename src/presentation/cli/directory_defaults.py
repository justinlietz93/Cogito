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
    order: Tuple[str, ...] = ()
    order_file: Optional[str] = None

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "DirectoryInputDefaults":
        """Construct defaults from a configuration mapping.

        Args:
            config: Mapping containing configuration values, typically loaded
                from ``config.json`` or ``config.yaml``.

        Returns:
            Instance populated with values from ``config`` overriding the
            dataclass defaults when provided.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable.
        """

        defaults = cls()
        include = cls._coerce_patterns(config.get("include"), defaults.include)
        exclude = cls._coerce_patterns(config.get("exclude"), defaults.exclude)
        recursive = cls._coerce_bool(config.get("recursive"), defaults.recursive)
        max_files = cls._coerce_optional_int(config.get("max_files"), defaults.max_files)
        max_chars = cls._coerce_optional_int(config.get("max_chars"), defaults.max_chars)
        section_separator_raw = config.get("section_separator")
        if isinstance(section_separator_raw, str):
            section_separator = section_separator_raw
        else:
            section_separator = defaults.section_separator
        label_sections = cls._coerce_bool(config.get("label_sections"), defaults.label_sections)
        enabled = cls._coerce_bool(config.get("enabled"), defaults.enabled)
        order = cls._coerce_patterns(config.get("order"), defaults.order)
        order_file_raw = config.get("order_file")
        if isinstance(order_file_raw, str) and order_file_raw.strip():
            order_file = order_file_raw.strip()
        else:
            order_file = defaults.order_file

        return cls(
            include=include,
            exclude=exclude,
            recursive=recursive,
            max_files=max_files,
            max_chars=max_chars,
            section_separator=section_separator,
            label_sections=label_sections,
            enabled=enabled,
            order=order,
            order_file=order_file,
        )

    def with_overrides(self, overrides: Mapping[str, Any]) -> "DirectoryInputDefaults":
        """Return a copy of the defaults with override values applied.

        Args:
            overrides: Mapping containing override values. Recognised keys mirror
                the dataclass fields (``include``, ``exclude``, ``recursive``,
                ``max_files``, ``max_chars``, ``section_separator``,
                ``label_sections``, ``enabled``, ``order``, ``order_file``).

        Returns:
            New instance with the supplied overrides applied. Keys missing from
            ``overrides`` fall back to the receiver's values.

        Raises:
            None.

        Side Effects:
            None; the method is pure.

        Timeout:
            Not applicable.
        """

        if not isinstance(overrides, Mapping):
            return self

        section_separator_raw = overrides.get("section_separator")
        if isinstance(section_separator_raw, str):
            section_separator = section_separator_raw
        else:
            section_separator = self.section_separator

        order = self._coerce_patterns(overrides.get("order"), self.order)
        order_file_raw = overrides.get("order_file")
        if isinstance(order_file_raw, str) and order_file_raw.strip():
            order_file = order_file_raw.strip()
        else:
            order_file = self.order_file

        return DirectoryInputDefaults(
            include=self._coerce_patterns(overrides.get("include"), self.include),
            exclude=self._coerce_patterns(overrides.get("exclude"), self.exclude),
            recursive=self._coerce_bool(overrides.get("recursive"), self.recursive),
            max_files=self._coerce_optional_int(overrides.get("max_files"), self.max_files),
            max_chars=self._coerce_optional_int(overrides.get("max_chars"), self.max_chars),
            section_separator=section_separator,
            label_sections=self._coerce_bool(overrides.get("label_sections"), self.label_sections),
            enabled=self._coerce_bool(overrides.get("enabled"), self.enabled),
            order=order,
            order_file=order_file,
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
