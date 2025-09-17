"""Application-level exceptions for critique coordination."""

from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when the critique configuration cannot be constructed."""


class MissingApiKeyError(ConfigurationError):
    """Raised when the primary provider lacks an API key."""


__all__ = ["ConfigurationError", "MissingApiKeyError"]
