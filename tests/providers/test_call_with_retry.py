import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import ProviderError, call_with_retry


def test_call_with_retry_defaults_to_openai(monkeypatch):
    recorded = {}

    def fake_openai(*, prompt_template, context, config, is_structured):
        recorded["prompt_template"] = prompt_template
        recorded["context"] = context
        recorded["config"] = config
        recorded["is_structured"] = is_structured
        return "ok", "openai-model"

    monkeypatch.setattr(
        "src.providers.openai_client.call_openai_with_retry",
        fake_openai,
    )

    result, model = call_with_retry("Hello {name}", {"name": "World"}, {})

    assert recorded["prompt_template"] == "Hello {name}"
    assert recorded["context"] == {"name": "World"}
    assert recorded["config"] == {}
    assert recorded["is_structured"] is False
    assert (result, model) == ("ok", "openai-model")


def test_call_with_retry_uses_configured_gemini(monkeypatch):
    recorded = {}

    def fake_gemini(*, prompt_template, context, config, is_structured):
        recorded["prompt_template"] = prompt_template
        recorded["context"] = context
        recorded["config"] = config
        recorded["is_structured"] = is_structured
        return {"status": "ok"}, "gemini-pro"

    monkeypatch.setattr(
        "src.providers.gemini_client.call_gemini_with_retry",
        fake_gemini,
    )

    config = {
        "api": {
            "primary_provider": "gemini",
            "providers": {"gemini": {"resolved_key": "abc"}},
            "gemini": {"resolved_key": "abc"},
        }
    }

    result, model = call_with_retry(
        "Describe {topic}",
        {"topic": "stars"},
        config,
        is_structured=True,
    )

    assert recorded["prompt_template"] == "Describe {topic}"
    assert recorded["context"] == {"topic": "stars"}
    assert recorded["is_structured"] is True
    assert recorded["config"]["api"]["primary_provider"] == "gemini"
    assert result == {"status": "ok"}
    assert model == "gemini-pro"


def test_call_with_retry_handles_anthropic_json(monkeypatch):
    captured = {}

    def fake_generate_content(*, messages, model_name, max_tokens, temperature, enable_thinking, api_key):
        captured["messages"] = messages
        captured["model_name"] = model_name
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        captured["enable_thinking"] = enable_thinking
        captured["api_key"] = api_key
        return '{"answer": "ok"}'

    monkeypatch.setattr(
        "src.providers.anthropic_client.generate_content",
        fake_generate_content,
    )

    config = {
        "api": {
            "primary_provider": "anthropic",
            "providers": {
                "anthropic": {
                    "resolved_key": "anth-key",
                    "model": "claude-3-sonnet",
                    "max_tokens": 500,
                    "temperature": 0.4,
                }
            },
            "anthropic": {
                "resolved_key": "anth-key",
                "model": "claude-3-sonnet",
                "max_tokens": 500,
                "temperature": 0.4,
            },
            "resolved_key": "anth-key",
        }
    }

    payload, model = call_with_retry(
        "Explain {topic}",
        {"topic": "science"},
        config,
        is_structured=True,
    )

    assert payload == {"answer": "ok"}
    assert model == "Anthropic: claude-3-sonnet"
    assert captured["messages"][0]["role"] == "system"
    assert "Respond strictly in valid JSON format." in captured["messages"][0]["content"]
    assert captured["messages"][1]["content"].endswith("science")
    assert captured["model_name"] == "claude-3-sonnet"
    assert captured["max_tokens"] == 500
    assert pytest.approx(captured["temperature"]) == 0.4
    assert captured["enable_thinking"] is False
    assert captured["api_key"] == "anth-key"


def test_call_with_retry_unknown_provider():
    with pytest.raises(ProviderError):
        call_with_retry("Prompt", {}, {"api": {"primary_provider": "unknown"}})
