"""Tests for helper utilities defined in :mod:`src.providers`."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import (
    DEFAULT_SYSTEM_MESSAGE,
    JsonParsingError,
    _call_anthropic_with_retry,
    _coerce_float,
    _coerce_int,
    _coerce_str,
    _extract_api_key,
    _get_api_section,
    _get_provider_config,
    _normalise_provider,
)
from src.providers import anthropic_client


def test_normalise_provider_aliases() -> None:
    """Provider aliases should map to the canonical identifiers."""

    assert _normalise_provider("claude") == "anthropic"
    assert _normalise_provider("google-ai") == "gemini"
    assert _normalise_provider(None) == "openai"
    assert _normalise_provider("Custom") == "custom"


def test_get_api_section_handles_non_mapping() -> None:
    """Invalid configuration structures should return an empty mapping."""

    assert _get_api_section([1, 2, 3]) == {}


def test_get_provider_config_prefers_nested_mapping() -> None:
    """The helper should first look under the ``providers`` section."""

    api_section = {"providers": {"anthropic": {"temperature": 0.6}}}
    assert _get_provider_config(api_section, "anthropic") == {"temperature": 0.6}


def test_get_provider_config_falls_back_to_direct_key() -> None:
    """Direct provider keys should be used when nested config is absent."""

    api_section = {"anthropic": {"model": "claude"}}
    assert _get_provider_config(api_section, "anthropic") == {"model": "claude"}


def test_get_provider_config_returns_empty_when_missing() -> None:
    """Missing provider settings should return an empty mapping."""

    api_section = {"providers": {}, "gemini": None}
    assert _get_provider_config(api_section, "gemini") == {}


def test_extract_api_key_uses_primary_fallback() -> None:
    """When no explicit key is present, fall back to the resolved key."""

    api_section = {"primary_provider": "anthropic", "resolved_key": "primary"}
    assert _extract_api_key("anthropic", api_section, {}) == "primary"


def test_coerce_helpers_return_defaults() -> None:
    """The coercion helpers should return defaults on invalid input."""

    assert _coerce_int("not-int", 3) == 3
    assert _coerce_float("not-float", 0.1) == pytest.approx(0.1)
    assert _coerce_str(42, "default") == "42"


def test_call_anthropic_with_retry_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-structured requests should return the raw provider text."""

    captured: dict[str, Any] = {}

    def fake_generate_content(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "Response"

    monkeypatch.setattr(anthropic_client, "generate_content", fake_generate_content)

    payload, model = _call_anthropic_with_retry(
        prompt_template="Hi {name}",
        context={"name": "Alice"},
        config={"api": {"providers": {"anthropic": {"model": "claude", "temperature": 0.4}}}},
        is_structured=False,
    )

    assert payload == "Response"
    assert model == "Anthropic: claude"
    assert captured["messages"][0]["content"].startswith(DEFAULT_SYSTEM_MESSAGE)


def test_call_anthropic_with_retry_raises_on_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured requests should raise :class:`JsonParsingError` on bad JSON."""

    monkeypatch.setattr(anthropic_client, "generate_content", lambda **_: "not-json")

    with pytest.raises(JsonParsingError):
        _call_anthropic_with_retry(
            prompt_template="Prompt",
            context=None,
            config={},
            is_structured=True,
        )
