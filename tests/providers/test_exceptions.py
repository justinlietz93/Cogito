from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers.exceptions import ApiBlockedError


def test_api_blocked_error_includes_reason_and_ratings() -> None:
    """String representation should include reason and rating metadata."""

    error = ApiBlockedError("Blocked", reason="SAFETY", ratings=[{"score": "high"}])

    text = str(error)
    assert "Blocked" in text
    assert "SAFETY" in text
    assert "Safety Ratings" in text


def test_api_blocked_error_defaults_when_missing_metadata() -> None:
    """When no metadata is supplied, default text should be shown."""

    error = ApiBlockedError("Blocked")

    assert "No reason provided" in str(error)
