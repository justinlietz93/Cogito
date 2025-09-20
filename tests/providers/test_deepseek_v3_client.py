"""Unit tests for the synchronous DeepSeek v3 fallback client."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import deepseek_v3_client
from src.providers.exceptions import ApiCallError, ApiKeyError, ApiResponseError, JsonParsingError


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure stateful globals start fresh for each test."""

    monkeypatch.setattr(deepseek_v3_client, "_deepseek_api_key", None)
    monkeypatch.setattr(deepseek_v3_client, "_deepseek_base_url", None)
    monkeypatch.setattr(deepseek_v3_client, "_deepseek_configured", False)


def test_configure_client_sets_state() -> None:
    """Configuring with an API key should mark the client as ready."""

    deepseek_v3_client.configure_client("key", base_url="http://host")

    assert deepseek_v3_client._deepseek_api_key == "key"
    assert deepseek_v3_client._deepseek_base_url == "http://host"
    assert deepseek_v3_client._deepseek_configured is True


def test_configure_client_requires_api_key() -> None:
    """Missing API keys should raise ``ApiKeyError``."""

    with pytest.raises(ApiKeyError):
        deepseek_v3_client.configure_client("")


def test_generate_content_requires_configuration() -> None:
    """Calls should fail if the client has not been configured."""

    with pytest.raises(ApiCallError):
        deepseek_v3_client.generate_content("Prompt", {"deepseek": {}})


def test_generate_content_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful requests should return trimmed content and model name."""

    deepseek_v3_client.configure_client("token", base_url="http://api")

    def fake_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: int) -> Any:
        assert url == "http://api/chat/completions"
        assert headers["Authorization"] == "Bearer token"
        assert json["messages"][0]["content"] == "Prompt"

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return {
                    "choices": [
                        {"message": {"content": "  Result  "}}
                    ]
                }

        return Response()

    monkeypatch.setattr(requests, "post", fake_post)

    config = {"deepseek": {"model_name": "deepseek-chat"}}
    result, model = deepseek_v3_client.generate_content("Prompt", config)

    assert result == "Result"
    assert model == "DeepSeek: deepseek-chat"


def test_generate_content_json_decode_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON decoding failures should include the raw ``response.text`` in logs."""

    deepseek_v3_client.configure_client("token", base_url="http://api")

    class Response:
        text = "not-json"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            raise json.JSONDecodeError("bad", self.text, 0)

    monkeypatch.setattr(requests, "post", lambda *_, **__: Response())

    with pytest.raises(JsonParsingError):
        deepseek_v3_client.generate_content("Prompt", {"deepseek": {}})


def test_generate_content_missing_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Responses without content should raise ``ApiResponseError``."""

    deepseek_v3_client.configure_client("token", base_url="http://api")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {}}]}

    monkeypatch.setattr(requests, "post", lambda *_, **__: Response())

    with pytest.raises(ApiCallError):
        deepseek_v3_client.generate_content("Prompt", {"deepseek": {}})


def test_generate_content_wraps_request_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network failures should be wrapped in ``ApiCallError``."""

    deepseek_v3_client.configure_client("token", base_url="http://api")

    monkeypatch.setattr(
        requests,
        "post",
        lambda *_, **__: (_ for _ in ()).throw(requests.exceptions.RequestException("boom")),
    )

    with pytest.raises(ApiCallError):
        deepseek_v3_client.generate_content("Prompt", {"deepseek": {}})


def test_generate_structured_content_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured helper should clean code fences and parse JSON."""

    monkeypatch.setattr(
        deepseek_v3_client,
        "generate_content",
        lambda prompt, config: ("```json\n{\"value\": 2}\n```", "DeepSeek: deepseek-chat"),
    )

    parsed, model = deepseek_v3_client.generate_structured_content("Prompt", {"deepseek": {}})

    assert parsed == {"value": 2}
    assert model == "DeepSeek: deepseek-chat"


def test_generate_structured_content_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty payloads should raise ``ApiResponseError``."""

    monkeypatch.setattr(
        deepseek_v3_client,
        "generate_content",
        lambda *_: ("```\n\n```", "DeepSeek: deepseek-chat"),
    )

    with pytest.raises(ApiResponseError):
        deepseek_v3_client.generate_structured_content("Prompt", {"deepseek": {}})


def test_generate_structured_content_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON should raise ``JsonParsingError``."""

    monkeypatch.setattr(
        deepseek_v3_client,
        "generate_content",
        lambda *_: ("{" , "DeepSeek: deepseek-chat"),
    )

    with pytest.raises(JsonParsingError):
        deepseek_v3_client.generate_structured_content("Prompt", {"deepseek": {}})


def test_generate_structured_content_handles_unexpected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected errors should be wrapped in ``JsonParsingError``."""

    monkeypatch.setattr(
        deepseek_v3_client,
        "generate_content",
        lambda *_: (None, "DeepSeek: deepseek-chat"),
    )

    with pytest.raises(JsonParsingError):
        deepseek_v3_client.generate_structured_content("Prompt", {"deepseek": {}})
