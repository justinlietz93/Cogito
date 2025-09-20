from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import deepseek_client


@pytest.fixture(autouse=True)
def reset_deepseek_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure global client state is reset before each test."""

    monkeypatch.setattr(deepseek_client, "_deepseek_api_key", None)
    monkeypatch.setattr(deepseek_client, "_deepseek_base_url", None)
    monkeypatch.setattr(deepseek_client, "_deepseek_configured", False)


def test_configure_client_sets_global_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuring the client should store the key and resolved URL."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    deepseek_client.configure_client(api_key="secret")

    assert deepseek_client._deepseek_api_key == "secret"
    assert deepseek_client._deepseek_base_url == "http://cfg"
    assert deepseek_client._deepseek_configured is True


def test_configure_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing API keys should raise an ``ApiKeyError``."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {})
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(deepseek_client.ApiKeyError):
        deepseek_client.configure_client()


def test_generate_content_invokes_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful responses should return the content and reasoning flag."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    captured: dict[str, Any] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            captured["status_checked"] = True

        def json(self) -> dict[str, Any]:
            captured["json_called"] = True
            return {"choices": [{"message": {"content": "Reply"}}]}

    def fake_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: int) -> DummyResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(deepseek_client.requests, "post", fake_post)

    content, has_reasoning = deepseek_client.generate_content(
        messages=[{"role": "user", "content": "Share reasoning"}],
        model_name="deepseek-reasoner",
        max_tokens=1234,
        temperature=0.4,
        api_key="provided",
    )

    assert content == "Reply"
    assert has_reasoning is True
    assert captured["url"] == "http://cfg/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer provided"
    assert captured["payload"]["max_tokens"] == 1234
    assert captured["payload"]["messages"][0]["content"] == "Share reasoning"
    assert captured["timeout"] == 60


def test_generate_content_uses_chat_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chat models should still post to the chat completions endpoint."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    class DummyResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": "Reply"}}]}

    captured: dict[str, Any] = {}

    def fake_post(url: str, *_, **__) -> DummyResponse:
        captured["url"] = url
        return DummyResponse()

    monkeypatch.setattr(deepseek_client.requests, "post", fake_post)

    deepseek_client.generate_content(
        messages=[{"role": "user", "content": "Hi"}],
        model_name="deepseek-chat",
        api_key="token",
    )

    assert captured["url"] == "http://cfg/chat/completions"


def test_generate_content_raises_on_invalid_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Responses without choices should raise ``DeepseekClientError``."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    class DummyResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"choices": []}

    monkeypatch.setattr(deepseek_client.requests, "post", lambda *_, **__: DummyResponse())

    with pytest.raises(deepseek_client.DeepseekClientError) as excinfo:
        deepseek_client.generate_content([{"role": "user", "content": "hi"}], api_key="k")

    assert "response structure invalid" in str(excinfo.value)


def test_generate_content_wraps_request_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network errors should surface as ``DeepseekClientError``."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})
    monkeypatch.setattr(
        deepseek_client.requests,
        "post",
        lambda *_, **__: (_ for _ in ()).throw(requests.exceptions.RequestException("boom")),
    )

    with pytest.raises(deepseek_client.DeepseekClientError) as excinfo:
        deepseek_client.generate_content([{"role": "user", "content": "hi"}], api_key="k")

    assert "Error during DeepSeek API call" in str(excinfo.value)


def test_generate_content_wraps_json_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed JSON responses should raise ``DeepseekClientError``."""

    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    class DummyResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            raise json.JSONDecodeError("bad", "doc", 0)

    monkeypatch.setattr(deepseek_client.requests, "post", lambda *_, **__: DummyResponse())

    with pytest.raises(deepseek_client.DeepseekClientError) as excinfo:
        deepseek_client.generate_content([{"role": "user", "content": "hi"}], api_key="k")

    assert "not valid JSON" in str(excinfo.value)


def test_generate_structured_content_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured helper should strip fences and parse JSON."""

    monkeypatch.setattr(
        deepseek_client,
        "generate_content",
        lambda **_: ("```json\n{\"value\": 1}\n```", False),
    )

    parsed, model_used = deepseek_client.generate_structured_content("Prompt", model_name="deepseek-reasoner")

    assert parsed == {"value": 1}
    assert model_used == "DeepSeek: deepseek-reasoner"


def test_generate_structured_content_handles_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty cleaned responses should raise ``DeepseekClientError``."""

    monkeypatch.setattr(deepseek_client, "generate_content", lambda **_: ("``` ```", False))

    with pytest.raises(deepseek_client.DeepseekClientError):
        deepseek_client.generate_structured_content("Prompt")


def test_generate_structured_content_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON should trigger ``JsonParsingError``."""

    monkeypatch.setattr(deepseek_client, "generate_content", lambda **_: ("not-json", False))

    with pytest.raises(deepseek_client.JsonParsingError):
        deepseek_client.generate_structured_content("Prompt")


def test_run_deepseek_client_uses_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """High-level helper should forward environment credentials."""

    monkeypatch.setenv("DEEPSEEK_API_KEY", "env")
    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    captured: dict[str, Any] = {}

    def fake_generate_content(**kwargs: Any) -> tuple[str, bool]:
        captured.update(kwargs)
        return "ok", False

    monkeypatch.setattr(deepseek_client, "generate_content", fake_generate_content)

    result = deepseek_client.run_deepseek_client([{"role": "user", "content": "hi"}], model_name="chat")

    assert result == "ok"
    assert captured["api_key"] == "env"
    assert captured["model_name"] == "chat"


def test_run_deepseek_client_returns_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors should be logged and returned as strings."""

    monkeypatch.setenv("DEEPSEEK_API_KEY", "env")
    monkeypatch.setattr(deepseek_client, "get_deepseek_config", lambda: {"base_url": "http://cfg"})

    fake_traceback = SimpleNamespace(print_exc=lambda: None)
    monkeypatch.setitem(sys.modules, "traceback", fake_traceback)

    def boom(**_: Any) -> tuple[str, bool]:
        raise deepseek_client.DeepseekClientError("bad")

    monkeypatch.setattr(deepseek_client, "generate_content", boom)

    result = deepseek_client.run_deepseek_client([{"role": "user", "content": "hi"}])

    assert result.startswith("ERROR from DeepSeek: ")
