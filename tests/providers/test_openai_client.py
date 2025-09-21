"""Regression tests for the OpenAI provider client."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import openai_client
from src.providers.exceptions import ApiCallError, ModelCallError

def _build_o3_response(payload: str) -> SimpleNamespace:
    """Return a minimal object that mimics the responses.create structure."""

    return SimpleNamespace(
        output=[
            SimpleNamespace(
                role="assistant",
                content=[SimpleNamespace(text=payload)],
            )
        ]
    )


def test_call_openai_with_retry_parses_structured_o3(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured JSON from o3-mini should be parsed and returned as a dictionary."""

    captured: Dict[str, Any] = {}
    payload = json.dumps({"points": [{"id": "point-1", "point": "From o3"}]})

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.responses = SimpleNamespace(create=self._create)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

        def _create(self, **kwargs: Any) -> SimpleNamespace:
            captured["responses_kwargs"] = kwargs
            return _build_o3_response(payload)

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, model = openai_client.call_openai_with_retry(
        prompt_template="Prompt with {value}",
        context={"value": 5},
        config={"api": {"openai": {"model": "o3-mini", "resolved_key": "test-key", "system_message": "System"}}},
        is_structured=True,
    )

    assert model == "o3-mini"
    assert result == {"points": [{"id": "point-1", "point": "From o3"}]}
    assert captured["api_key"] == "test-key"
    input_payload = captured["responses_kwargs"]["input"][0]["content"][0]["text"]
    assert "System instruction: System" in input_payload
    assert "Prompt with 5" in input_payload


def test_call_openai_with_retry_repairs_truncated_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """o3-mini responses with missing braces should be repaired automatically."""

    truncated_payload = '{"points": [{"id": "point-1", "point": "First"}]'  # Missing closing braces

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: _build_o3_response(truncated_payload))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, _ = openai_client.call_openai_with_retry(
        prompt_template="Anything",
        context={},
        config={"api": {"openai": {"model": "o3-mini", "resolved_key": "key"}}},
        is_structured=True,
    )

    assert isinstance(result, dict)
    assert result["points"][0]["id"] == "point-1"


def test_call_openai_with_retry_sets_o1_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """O1 parameters should include ``max_output_tokens`` when provided."""

    captured: dict[str, Any] = {}

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=self._create)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

        def _create(self, **kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return _build_o3_response("{}")

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "o3", "resolved_key": "k"}}},
        is_structured=True,
        max_tokens=256,
    )

    assert captured["max_output_tokens"] == 256


def test_call_openai_with_retry_returns_text_for_chat_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non o1/o3 models should go through the chat completions API and return raw text."""

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: None)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="Plain response"))]
                    )
                )
            )

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, model = openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "gpt-4o-mini", "resolved_key": "key"}}},
        is_structured=False,
    )

    assert model == "gpt-4o-mini"
    assert result == "Plain response"


def test_call_openai_with_retry_sets_chat_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chat completions should forward the ``max_tokens`` argument."""

    captured: Dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resp"))])

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: None)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "gpt-4o-mini", "resolved_key": "key"}}},
        is_structured=False,
        max_tokens=321,
    )

    assert captured["max_tokens"] == 321


def test_call_openai_with_retry_sets_chat_max_completion_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reasoning chat models should forward the ``max_completion_tokens`` argument."""

    captured: Dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resp"))])

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: None)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "gpt-4.1-mini", "resolved_key": "key"}}},
        is_structured=False,
        max_tokens=222,
    )

    assert captured["max_completion_tokens"] == 222
    assert "max_tokens" not in captured


def test_call_openai_with_retry_uses_configured_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured ``max_tokens`` values should be forwarded to chat completions."""

    captured: Dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resp"))])

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: None)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "gpt-4o-mini", "resolved_key": "key", "max_tokens": 654}}},
        is_structured=False,
    )

    assert captured["max_tokens"] == 654


def test_call_openai_with_retry_direct_access_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback extraction should return content when the first pass fails."""

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=self._create)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

        def _create(self, **kwargs: Any) -> SimpleNamespace:
            alt_content = SimpleNamespace(text="Alternate")
            return SimpleNamespace(output=[SimpleNamespace(content=[]), SimpleNamespace(content=[alt_content])])

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, _ = openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "o3", "resolved_key": "k"}}},
        is_structured=False,
    )

    assert result == "Alternate"


def test_call_openai_with_retry_direct_access_json_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured fallback should surface raw text when JSON parsing fails."""

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            alt_content = SimpleNamespace(text="{invalid")
            response = SimpleNamespace(output=[SimpleNamespace(content=[]), SimpleNamespace(content=[alt_content])])
            self.responses = SimpleNamespace(create=lambda **_: response)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, _ = openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "o3", "resolved_key": "k"}}},
        is_structured=True,
    )

    assert result == "{invalid"


def test_call_openai_with_retry_direct_access_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured fallback should parse JSON when the payload is valid."""

    payload = json.dumps({"value": 3})

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            alt_content = SimpleNamespace(text=payload)
            response = SimpleNamespace(output=[SimpleNamespace(content=[]), SimpleNamespace(content=[alt_content])])
            self.responses = SimpleNamespace(create=lambda **_: response)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, model = openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"model": "o3", "resolved_key": "k"}}},
        is_structured=True,
    )

    assert model == "o3"
    assert result == {"value": 3}


def test_call_openai_with_retry_handles_response_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors from the responses API should propagate as ``ApiCallError``."""

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(RuntimeError("boom")))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    with pytest.raises(ApiCallError):
        openai_client.call_openai_with_retry(
            prompt_template="Prompt",
            context={},
            config={"api": {"openai": {"model": "o3", "resolved_key": "k"}}},
            is_structured=False,
        )


def test_call_openai_with_retry_wraps_processing_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Processing failures inside the responses branch should raise ``ApiCallError``."""

    class ExplodingResponse:
        @property
        def output(self) -> Any:  # pragma: no cover - property executed for coverage
            raise RuntimeError("explode")

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: ExplodingResponse())
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    with pytest.raises(ApiCallError):
        openai_client.call_openai_with_retry(
            prompt_template="Prompt",
            context={},
            config={"api": {"openai": {"model": "o3", "resolved_key": "k"}}},
            is_structured=False,
        )


def test_call_openai_with_retry_handles_chat_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected chat response shapes should raise ``ApiCallError``."""

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.responses = SimpleNamespace(create=lambda **_: pytest.fail("Should not hit responses API"))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: SimpleNamespace(choices=[])))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    with pytest.raises(ApiCallError):
        openai_client.call_openai_with_retry(
            prompt_template="Prompt",
            context={},
            config={"api": {"openai": {"model": "gpt-4o-mini", "resolved_key": "k"}}},
            is_structured=False,
        )


def test_call_openai_with_retry_handles_chat_json_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chat responses should surface invalid JSON as ``ApiCallError``."""

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            content = SimpleNamespace(message=SimpleNamespace(content="not-json"))
            response = SimpleNamespace(choices=[content])
            self.responses = SimpleNamespace(create=lambda **_: pytest.fail("Should not hit responses API"))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    with pytest.raises(ApiCallError):
        openai_client.call_openai_with_retry(
            prompt_template="Prompt",
            context={},
            config={"api": {"openai": {"model": "gpt-4o-mini", "resolved_key": "k"}}},
            is_structured=True,
        )
def test_call_openai_with_retry_defaults_to_configurable_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no model is supplied, prefer the flexible gpt-4o-mini default."""

    captured: Dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured["chat_kwargs"] = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Default response"))]
        )

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.responses = SimpleNamespace(create=lambda **_: pytest.fail("Should use chat API"))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)

    result, model = openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"resolved_key": "config-key"}}},
        is_structured=False,
    )

    assert captured["api_key"] == "config-key"
    assert captured["chat_kwargs"]["model"] == "gpt-4o-mini"
    assert model == "gpt-4o-mini"
    assert result == "Default response"


def test_call_openai_with_retry_prefers_env_model_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment model overrides should apply when config omits a model."""

    captured: Dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured["chat_kwargs"] = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Env response"))]
        )

    class DummyClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.responses = SimpleNamespace(create=lambda **_: pytest.fail("Should use chat API"))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    monkeypatch.setattr(openai_client, "OpenAI", DummyClient)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.delenv("OPENAI_DEFAULT_MODEL", raising=False)

    result, model = openai_client.call_openai_with_retry(
        prompt_template="Prompt",
        context={},
        config={"api": {"openai": {"resolved_key": "config-key"}}},
        is_structured=False,
    )

    assert captured["chat_kwargs"]["model"] == "gpt-4o"
    assert model == "gpt-4o"
    assert result == "Env response"


def test_call_openai_with_retry_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing API keys should surface as a user-facing configuration error."""

    monkeypatch.setattr(openai_client, "OpenAI", lambda *_, **__: pytest.fail("OpenAI should not be instantiated"))
    monkeypatch.setattr(openai_client.os, "getenv", lambda *_: None)

    with pytest.raises(ApiCallError, match="OpenAI API key not found"):
        openai_client.call_openai_with_retry(
            prompt_template="Prompt",
            context={},
            config={"api": {"openai": {}}},
            is_structured=False,
        )
