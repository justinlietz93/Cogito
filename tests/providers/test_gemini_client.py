"""Tests for the Gemini provider wrapper and fallback orchestration."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import gemini_client
from src.providers import deepseek_v3_client
from src.providers.exceptions import (
    ApiBlockedError,
    ApiCallError,
    ApiResponseError,
    JsonProcessingError,
)


@pytest.fixture(autouse=True)
def reset_gemini_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset cached client state before every test."""

    monkeypatch.setattr(gemini_client, "_gemini_model", None)
    monkeypatch.setattr(gemini_client, "_gemini_model_name", None)
    monkeypatch.setattr(gemini_client, "_client_configured", False)
    monkeypatch.setattr(gemini_client, "_deepseek_fallback_enabled", False)


def test_configure_client_configures_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing a key should configure the underlying SDK exactly once."""

    captured: dict[str, Any] = {}

    def fake_configure(api_key: str) -> None:
        captured.setdefault("keys", []).append(api_key)

    monkeypatch.setattr(gemini_client.genai, "configure", fake_configure)

    gemini_client.configure_client("secret")

    assert gemini_client._client_configured is True
    assert captured["keys"] == ["secret"]


def test_configure_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing API keys should raise an ``ApiKeyError``."""

    with pytest.raises(gemini_client.ApiKeyError):
        gemini_client.configure_client("")


def test_configure_client_logs_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors from the SDK should be wrapped in ``ApiKeyError``."""

    monkeypatch.setattr(gemini_client.genai, "configure", lambda **_: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(gemini_client.ApiKeyError):
        gemini_client.configure_client("key")


def test_configure_deepseek_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supplying DeepSeek credentials should enable the fallback."""

    captured: dict[str, Any] = {}

    def fake_configure_client(api_key: str, base_url: str) -> None:
        captured["api_key"] = api_key
        captured["base_url"] = base_url

    monkeypatch.setattr(deepseek_v3_client, "configure_client", fake_configure_client)

    enabled = gemini_client.configure_deepseek_fallback({"deepseek": {"api_key": "k", "base_url": "http://d"}})

    assert enabled is True
    assert gemini_client._deepseek_fallback_enabled is True
    assert captured == {"api_key": "k", "base_url": "http://d"}

    disabled = gemini_client.configure_deepseek_fallback({"deepseek": {}})
    assert disabled is False


def test_configure_deepseek_fallback_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected errors should disable the fallback."""

    monkeypatch.setattr(deepseek_v3_client, "configure_client", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))

    enabled = gemini_client.configure_deepseek_fallback({"deepseek": {"api_key": "k"}})

    assert enabled is False
    assert gemini_client._deepseek_fallback_enabled is False


def test_get_gemini_model_caches_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model instances should be cached based on the configured name."""

    captured: dict[str, Any] = {}

    class DummyModel:
        def __init__(self, model_name: str, generation_config: dict[str, Any], safety_settings: List[dict[str, str]]) -> None:
            captured["model_name"] = model_name
            captured["generation_config"] = generation_config
            captured["safety_settings"] = safety_settings
            self.model_name = model_name

    monkeypatch.setattr(gemini_client.genai, "configure", lambda **_: None)
    monkeypatch.setattr(gemini_client.genai, "GenerativeModel", DummyModel)

    config = {"api": {"resolved_key": "env", "gemini": {"model_name": "gemini-pro", "temperature": 0.8}}}
    model = gemini_client.get_gemini_model(config)
    cached = gemini_client.get_gemini_model(config)

    assert model is cached
    assert captured["model_name"] == "gemini-pro"
    assert captured["generation_config"]["temperature"] == 0.8


def test_get_gemini_model_handles_initialisation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors from GenerativeModel should be raised as ``ApiCallError``."""

    monkeypatch.setattr(gemini_client.genai, "configure", lambda **_: None)
    monkeypatch.setattr(gemini_client.genai, "GenerativeModel", lambda **_: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(gemini_client.ApiCallError):
        gemini_client.get_gemini_model({"api": {"resolved_key": "k"}})


def test_generate_content_returns_concatenated_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Responses with multiple text parts should be concatenated."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            assert "Prompt" in prompt
            part1 = SimpleNamespace(text="Hello ")
            part2 = SimpleNamespace(text="World")
            candidate = SimpleNamespace(content=SimpleNamespace(parts=[part1, part2]))
            return SimpleNamespace(candidates=[candidate])

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda config: DummyModel())

    text, model_name = gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})

    assert text == "Hello World"
    assert model_name == "Gemini: gemini-pro"


def test_generate_content_handles_empty_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Candidates without parts should raise an ``ApiResponseError``."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            candidate = SimpleNamespace(content=SimpleNamespace(parts=[]), finish_reason="SAFETY", safety_ratings=[{"score": 1}])
            return SimpleNamespace(candidates=[candidate])

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(gemini_client.ApiBlockedError):
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})


def test_generate_content_handles_stop_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop exceptions should convert into ``ApiBlockedError``."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            StopCandidateException = type("StopCandidateException", (Exception,), {})
            raise StopCandidateException("Stopped")

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(gemini_client.ApiBlockedError):
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})


def test_generate_content_raises_on_blocked_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty candidate lists should raise an ``ApiBlockedError``."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            feedback = SimpleNamespace(block_reason=SimpleNamespace(name="SAFETY"), safety_ratings=[{"score": 1}])
            return SimpleNamespace(candidates=[], prompt_feedback=feedback)

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(ApiBlockedError):
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})


def test_generate_content_handles_prompt_feedback_attribute_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing feedback attributes should not raise additional errors."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            feedback = SimpleNamespace()
            return SimpleNamespace(candidates=[], prompt_feedback=feedback)

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(ApiBlockedError) as excinfo:
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})

    assert excinfo.value.reason == "Unknown"


def test_generate_content_reports_block_reason_without_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block reasons without a ``name`` attribute should be stringified."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            feedback = SimpleNamespace(block_reason="QUOTA", safety_ratings=None)
            return SimpleNamespace(candidates=[], prompt_feedback=feedback)

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(ApiBlockedError) as excinfo:
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})

    assert excinfo.value.reason == "QUOTA"


def test_generate_content_handles_non_safety_finish_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-SAFETY finish reasons should raise ``ApiResponseError``."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            candidate = SimpleNamespace(
                content=SimpleNamespace(parts=[]),
                finish_reason="STOP",
                safety_ratings=None,
            )
            return SimpleNamespace(candidates=[candidate])

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(ApiResponseError):
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})


def test_generate_content_wraps_generic_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected exceptions from the SDK should surface as ``ApiCallError``."""

    class DummyModel:
        model_name = "gemini-pro"

        def generate_content(self, prompt: str) -> Any:
            raise RuntimeError("boom")

    monkeypatch.setattr(gemini_client, "get_gemini_model", lambda _: DummyModel())

    with pytest.raises(ApiCallError):
        gemini_client.generate_content("Prompt", {"api": {"gemini": {}}})


def test_generate_structured_content_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured helper should parse JSON after removing code fences."""

    monkeypatch.setattr(gemini_client, "generate_content", lambda prompt, config: ("```json\n{\"value\": 3}\n```", "Gemini: g"))

    parsed, model = gemini_client.generate_structured_content("Prompt", {"api": {"gemini": {}}})

    assert parsed == {"value": 3}
    assert model == "Gemini: g"


def test_generate_structured_content_handles_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty structured responses should raise ``ApiResponseError``."""

    monkeypatch.setattr(gemini_client, "generate_content", lambda *_: ("", "Gemini: g"))

    with pytest.raises(gemini_client.ApiResponseError):
        gemini_client.generate_structured_content("Prompt", {"api": {"gemini": {}}})


def test_generate_structured_content_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON should raise ``JsonParsingError``."""

    monkeypatch.setattr(gemini_client, "generate_content", lambda *_: ("{", "Gemini: g"))

    with pytest.raises(gemini_client.JsonParsingError):
        gemini_client.generate_structured_content("Prompt", {"api": {"gemini": {}}})


def test_generate_structured_content_handles_processing_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected processing issues should raise ``JsonProcessingError``."""

    monkeypatch.setattr(gemini_client, "generate_content", lambda *_: ('{"value": 1}', "Gemini: g"))
    monkeypatch.setattr(gemini_client.json, "loads", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(JsonProcessingError):
        gemini_client.generate_structured_content("Prompt", {"api": {"gemini": {}}})


def test_is_rate_limit_error_detects_keywords() -> None:
    """Rate limit helper should detect common 429 keywords."""

    assert gemini_client.is_rate_limit_error(Exception("429 Too many requests")) is True
    assert gemini_client.is_rate_limit_error(Exception("network error")) is False


def test_call_gemini_with_retry_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry loop should back off before eventually succeeding."""

    attempts: list[str] = []

    def flaky_structured(prompt: str, config: dict[str, Any]) -> tuple[dict[str, Any], str]:
        attempts.append(prompt)
        if len(attempts) < 3:
            raise ApiCallError("temporary")
        return {"value": 1}, "Gemini: gemini-pro"

    sleeps: list[float] = []

    monkeypatch.setattr(gemini_client, "generate_structured_content", flaky_structured)
    monkeypatch.setattr(gemini_client.time, "sleep", sleeps.append)

    config = {"api": {"gemini": {"retries": 3}}}
    result, model = gemini_client.call_gemini_with_retry("{prompt}", {"prompt": "Ask"}, config, is_structured=True)

    assert result == {"value": 1}
    assert model == "Gemini: gemini-pro"
    assert sleeps == [1, 2]


def test_call_gemini_with_retry_configures_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing DeepSeek credentials should trigger fallback configuration."""

    calls: list[dict[str, Any]] = []

    def fake_configure(config: dict[str, Any]) -> bool:
        calls.append(config)
        return False

    monkeypatch.setattr(gemini_client, "configure_deepseek_fallback", fake_configure)
    monkeypatch.setattr(gemini_client, "generate_structured_content", lambda *_: ({"ok": True}, "Gemini: g"))

    config = {"api": {"gemini": {"retries": 1}}, "deepseek": {"api_key": "k"}}
    gemini_client.call_gemini_with_retry("{prompt}", {"prompt": "Ask"}, config, is_structured=True)

    assert calls == [config]


def test_call_gemini_with_retry_uses_deepseek_text_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When retries exhaust, the DeepSeek text fallback should be used."""

    config_calls: list[dict[str, Any]] = []

    def fake_configure(config: dict[str, Any]) -> bool:
        config_calls.append(config)
        gemini_client._deepseek_fallback_enabled = True
        return True

    def failing_content(*args: Any, **kwargs: Any) -> tuple[str, str]:
        raise ApiCallError("429 rate limit")

    monkeypatch.setattr(gemini_client, "configure_deepseek_fallback", fake_configure)
    monkeypatch.setattr(gemini_client, "generate_content", failing_content)
    monkeypatch.setattr(deepseek_v3_client, "generate_content", lambda *_, **__: ("fallback", "DeepSeek: chat"))

    config = {"api": {"gemini": {"retries": 1}}, "deepseek": {"api_key": "fallback-key"}}
    result, model = gemini_client.call_gemini_with_retry("{prompt}", {"prompt": "Ask"}, config, is_structured=False)

    assert result == "fallback"
    assert model == "DeepSeek: chat"
    assert config_calls == [config]


def test_call_gemini_with_retry_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rate-limit errors should trigger the DeepSeek fallback when enabled."""

    gemini_client._deepseek_fallback_enabled = True

    def failing_structured(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], str]:
        raise ApiCallError("rate limit")

    monkeypatch.setattr(gemini_client, "generate_structured_content", failing_structured)
    monkeypatch.setattr(gemini_client, "is_rate_limit_error", lambda exc: True)
    monkeypatch.setattr(deepseek_v3_client, "generate_structured_content", lambda *_, **__: ({"fallback": True}, "DeepSeek: chat"))

    config = {"api": {"gemini": {"retries": 1}}, "deepseek": {}}
    result, model = gemini_client.call_gemini_with_retry("{prompt}", {"prompt": "Ask"}, config, is_structured=True)

    assert result == {"fallback": True}
    assert model == "DeepSeek: chat"


def test_call_gemini_with_retry_fallback_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the fallback also fails, ``ApiCallError`` should be raised."""

    gemini_client._deepseek_fallback_enabled = True

    monkeypatch.setattr(gemini_client, "generate_structured_content", lambda *_: (_ for _ in ()).throw(ApiCallError("rate")))
    monkeypatch.setattr(gemini_client, "is_rate_limit_error", lambda exc: True)
    monkeypatch.setattr(deepseek_v3_client, "generate_structured_content", lambda *_, **__: (_ for _ in ()).throw(RuntimeError("boom")))

    config = {"api": {"gemini": {"retries": 1}}, "deepseek": {}}

    with pytest.raises(ApiCallError):
        gemini_client.call_gemini_with_retry("{prompt}", {"prompt": "Ask"}, config, is_structured=True)


def test_call_gemini_with_retry_raises_when_no_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero retry budgets should raise the final unexpected failure error."""

    calls: list[Any] = []

    monkeypatch.setattr(gemini_client, "generate_content", lambda *_: calls.append("called"))

    config = {"api": {"gemini": {"retries": 0}}}

    with pytest.raises(ApiCallError):
        gemini_client.call_gemini_with_retry("{prompt}", {"prompt": "Ask"}, config, is_structured=False)

    assert calls == []


def test_run_gemini_client_formats_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """High-level helper should stitch together system and user messages."""

    captured: dict[str, Any] = {}

    def fake_call(prompt_template: str, context: dict[str, Any], config: dict[str, Any], is_structured: bool) -> tuple[str, str]:
        captured["prompt_template"] = prompt_template
        captured["context"] = context
        captured["config"] = config
        captured["structured"] = is_structured
        return "response", "Gemini: gemini-pro"

    monkeypatch.setattr(gemini_client, "call_gemini_with_retry", fake_call)

    result = gemini_client.run_gemini_client([
        {"role": "system", "content": "Guide"},
        {"role": "user", "content": "Question"},
    ])

    assert result == "response"
    assert captured["prompt_template"] == "{content}"
    assert "Guide" in captured["context"]["content"]
    assert "Question" in captured["context"]["content"]
    assert captured["structured"] is False


def test_run_gemini_client_without_system_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a system message, the prompt should equal user content."""

    captured: dict[str, Any] = {}

    def fake_call(*args: Any, **kwargs: Any) -> tuple[str, str]:
        captured.update({"args": args, "kwargs": kwargs})
        return "ok", "Gemini: g"

    monkeypatch.setattr(gemini_client, "call_gemini_with_retry", fake_call)

    gemini_client.run_gemini_client([
        {"role": "user", "content": "Question"},
    ])

    assert captured["kwargs"]["context"]["content"].strip() == "Question"


def test_run_gemini_client_handles_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors from the lower-level call should return an error string."""

    monkeypatch.setattr(gemini_client, "call_gemini_with_retry", lambda *_, **__: (_ for _ in ()).throw(RuntimeError("boom")))

    result = gemini_client.run_gemini_client([
        {"role": "user", "content": "Hello"},
    ])

    assert result.startswith("ERROR from Gemini:")
