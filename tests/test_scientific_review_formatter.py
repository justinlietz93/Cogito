"""Tests for the scientific peer review formatter."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src import scientific_review_formatter as formatter


def _dummy_review_response(*_: Any, **__: Any) -> Tuple[str, str]:
    return "Review body", "DummyModel"


def test_format_scientific_peer_review_respects_configured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config: Dict[str, Any] = {}

    def _capture_call(prompt_template: str, context: Dict[str, Any], config: Dict[str, Any], is_structured: bool) -> Tuple[str, str]:
        captured_config["prompt"] = prompt_template
        captured_config["context"] = context
        captured_config["config"] = config
        captured_config["is_structured"] = is_structured
        return _dummy_review_response()

    monkeypatch.setattr(formatter, "call_with_retry", _capture_call)

    config = {
        "api": {
            "primary_provider": "Anthropic",
            "providers": {
                "anthropic": {
                    "model": "claude-3-7-sonnet",
                    "temperature": 0.1,
                }
            },
        }
    }
    original_config_snapshot = deepcopy(config)

    review = formatter.format_scientific_peer_review(
        original_content="Original manuscript",
        critique_report="Critique findings",
        config=config,
        scientific_mode=True,
    )

    assert "Scientific Peer Review Report" in review
    assert captured_config["config"]["api"]["primary_provider"] == "anthropic"
    assert captured_config["is_structured"] is False

    provider_cfg = captured_config["config"]["api"]["providers"]["anthropic"]
    assert provider_cfg["system_message"].strip().startswith(
        "You are an expert academic peer reviewer"
    )

    # Ensure we did not mutate the original configuration in place
    assert config == original_config_snapshot


def test_format_scientific_peer_review_handles_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_api_key_error(*_: Any, **__: Any) -> Tuple[str, str]:
        raise formatter.ApiKeyError("API key missing")

    monkeypatch.setattr(formatter, "call_with_retry", _raise_api_key_error)

    output = formatter.format_scientific_peer_review(
        original_content="Original",
        critique_report="Critique",
        config={"api": {"primary_provider": "gemini"}},
    )

    assert "no API key was available" in output
    assert "Gemini" in output
