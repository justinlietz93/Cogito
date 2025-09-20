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


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "openai"),
        ("Claude", "anthropic"),
        ("claude-3-7-sonnet", "anthropic"),
        ("google-ai", "gemini"),
        ("custom", "custom"),
    ],
)
def test_normalise_provider(value: Any, expected: str) -> None:
    assert formatter._normalise_provider(value) == expected


def test_prepare_formatter_config_handles_non_mapping() -> None:
    config, provider = formatter._prepare_formatter_config(None, "SYSTEM")
    assert provider == "openai"
    assert config["api"]["primary_provider"] == "openai"
    assert config["api"]["providers"]["openai"]["system_message"] == "SYSTEM"


def test_prepare_formatter_config_coerces_non_mapping_api_section() -> None:
    original = {"api": "unexpected"}

    config, provider = formatter._prepare_formatter_config(original, "SYS")

    assert provider == "openai"
    assert config["api"]["primary_provider"] == "openai"


def test_prepare_formatter_config_coerces_invalid_sections() -> None:
    original = {
        "api": {
            "primary_provider": "openai",
            "providers": "bad",  # triggers fallback to {}
            "openai": "unexpected",  # triggers merge fallback
        }
    }

    config, provider = formatter._prepare_formatter_config(original, "SYS")

    assert provider == "openai"
    assert isinstance(config["api"]["providers"], dict)
    assert config["api"]["providers"]["openai"]["system_message"] == "SYS"
    assert isinstance(config["api"]["openai"], dict)


def test_prepare_formatter_config_merges_existing_entries() -> None:
    original = {
        "api": {
            "primary_provider": "google",
            "providers": {
                "gemini": {"temperature": 0.5},
            },
            "gemini": {"max_tokens": 1024},
        }
    }

    config, provider = formatter._prepare_formatter_config(original, "SYS")

    assert provider == "gemini"
    provider_cfg = config["api"]["providers"]["gemini"]
    assert provider_cfg["temperature"] == 0.5
    assert provider_cfg["system_message"] == "SYS"
    assert config["api"]["gemini"]["max_tokens"] == 1024


def test_format_scientific_peer_review_non_scientific_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_prompt: Dict[str, Any] = {}

    def _capture(prompt_template: str, context: Dict[str, Any], config: Dict[str, Any], is_structured: bool):
        captured_prompt["prompt"] = prompt_template
        captured_prompt["context"] = context
        return "Rendered", "model"

    monkeypatch.setattr(formatter, "call_with_retry", _capture)

    config = {"api": {"primary_provider": "openai"}}
    output = formatter.format_scientific_peer_review(
        original_content="Manuscript",
        critique_report="Report",
        config=config,
        scientific_mode=False,
    )

    assert "Perspective-specific contributions" in captured_prompt["prompt"]
    assert "Manuscript" in captured_prompt["prompt"]
    assert output.startswith("# Scientific Peer Review Report")


def test_format_scientific_peer_review_handles_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_provider_error(*_: Any, **__: Any) -> Tuple[str, str]:
        raise formatter.ProviderError("provider unavailable")

    monkeypatch.setattr(formatter, "call_with_retry", _raise_provider_error)

    result = formatter.format_scientific_peer_review(
        original_content="Original",
        critique_report="Critique",
        config={"api": {"primary_provider": "openai"}},
    )

    assert "provider unavailable" in result


def test_format_scientific_peer_review_logs_jargon_failures(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(formatter, "call_with_retry", lambda *_, **__: ("Body", "model"))

    class BrokenProcessor:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def process(self, content: str) -> str:
            raise RuntimeError("jargon failure")

    monkeypatch.setattr(
        "src.latex.processors.jargon_processor.JargonProcessor",
        BrokenProcessor,
    )

    with caplog.at_level("WARNING"):
        result = formatter.format_scientific_peer_review(
            original_content="Original",
            critique_report="Critique",
            config={"api": {"primary_provider": "openai"}},
            scientific_mode=True,
        )

    assert "Failed to apply jargon processor" in caplog.text
    assert result.startswith("# Scientific Peer Review Report")


def test_format_scientific_peer_review_handles_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(formatter, "call_with_retry", lambda *_, **__: (_ for _ in ()).throw(RuntimeError("explode")))

    output = formatter.format_scientific_peer_review(
        original_content="Original",
        critique_report="Critique",
        config={"api": {"primary_provider": "openai"}},
    )

    assert "Scientific Peer Review Formatting Failed" in output
    assert "explode" in output
