from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import anthropic_client


def make_chunk(event_type: str, **attributes: Any) -> SimpleNamespace:
    """Create a simple namespace mimicking Anthropic streaming chunks."""

    return SimpleNamespace(type=event_type, **attributes)


def test_configure_client_uses_provided_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing an explicit key should configure the SDK with that value."""

    captured: dict[str, Any] = {}

    class DummyAnthropic:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(anthropic_client.anthropic, "Anthropic", DummyAnthropic)

    client = anthropic_client.configure_client("secret")

    assert isinstance(client, DummyAnthropic)
    assert captured["api_key"] == "secret"


def test_configure_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client should raise when no API key can be resolved."""

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(anthropic_client.AnthropicClientError):
        anthropic_client.configure_client()


def test_configure_client_wraps_sdk_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceptions from the SDK initialiser should be wrapped consistently."""

    class DummyAnthropic:
        def __init__(self, api_key: str) -> None:  # noqa: D401 - interface requirement
            raise RuntimeError("boom")

    monkeypatch.setattr(anthropic_client.anthropic, "Anthropic", DummyAnthropic)

    with pytest.raises(anthropic_client.AnthropicClientError) as excinfo:
        anthropic_client.configure_client("key")

    assert "Failed to configure Anthropic client" in str(excinfo.value)


def test_generate_content_streams_text_and_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Streaming responses should concatenate text while skipping thinking."""

    captured: dict[str, Any] = {}

    def fake_configure_client(api_key: str | None = None) -> Any:
        class FakeMessages:
            def create(self, **params: Any) -> list[SimpleNamespace]:
                captured["params"] = params
                return [
                    make_chunk("message_start"),
                    make_chunk(
                        "content_block_start",
                        index=0,
                        content_block=SimpleNamespace(type="thinking"),
                    ),
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(type="thinking_delta", thinking="analysis"),
                    ),
                    make_chunk("content_block_stop"),
                    make_chunk(
                        "content_block_start",
                        index=1,
                        content_block=SimpleNamespace(type="text"),
                    ),
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text="Hello "),
                    ),
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text="World"),
                    ),
                    make_chunk("content_block_stop"),
                    make_chunk("message_stop"),
                ]

        return SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(anthropic_client, "configure_client", fake_configure_client)

    response = anthropic_client.generate_content(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "prompt"},
        ],
        max_tokens=1500,
        enable_thinking=True,
    )

    params = captured["params"]
    assert response == "Hello World"
    assert params["system"] == "system"
    assert params["messages"] == [{"role": "user", "content": "prompt"}]
    assert params["temperature"] == pytest.approx(1.0)
    assert params["thinking"]["budget_tokens"] == 1024


def test_generate_content_preserves_temperature_when_thinking_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling thinking should keep the provided temperature and omit budgets."""

    captured: dict[str, Any] = {}

    def fake_configure_client(api_key: str | None = None) -> Any:
        class FakeMessages:
            def create(self, **params: Any) -> list[SimpleNamespace]:
                captured["params"] = params
                return [
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text="Hi"),
                    ),
                    make_chunk("message_stop"),
                ]

        return SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(anthropic_client, "configure_client", fake_configure_client)

    result = anthropic_client.generate_content(
        [{"role": "user", "content": "Hi"}],
        enable_thinking=False,
        temperature=0.7,
    )

    assert result == "Hi"
    assert captured["params"]["temperature"] == pytest.approx(0.7)
    assert "thinking" not in captured["params"]


def test_generate_content_clamps_supplied_thinking_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom budgets should be limited to the documented maximum."""

    captured: dict[str, Any] = {}

    def fake_configure_client(api_key: str | None = None) -> Any:
        class FakeMessages:
            def create(self, **params: Any) -> list[SimpleNamespace]:
                captured["params"] = params
                return [make_chunk("message_stop")]

        return SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(anthropic_client, "configure_client", fake_configure_client)

    anthropic_client.generate_content(
        [{"role": "user", "content": "Hi"}],
        max_tokens=2000,
        enable_thinking=True,
        thinking_budget=5000,
    )

    assert captured["params"]["thinking"]["budget_tokens"] == 1900


def test_generate_content_wraps_configuration_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors during configuration should surface as AnthropicClientError."""

    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("explode")

    monkeypatch.setattr(anthropic_client, "configure_client", boom)

    with pytest.raises(anthropic_client.AnthropicClientError):
        anthropic_client.generate_content([{"role": "user", "content": "Hi"}])


def test_run_anthropic_client_passes_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The high-level helper should forward the resolved API key."""

    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    captured: dict[str, Any] = {}

    def fake_generate_content(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(anthropic_client, "generate_content", fake_generate_content)

    response = anthropic_client.run_anthropic_client(
        messages=[{"role": "user", "content": "Hi"}],
        enable_thinking=True,
    )

    assert response == "ok"
    assert captured["api_key"] == "env-key"
    assert captured["enable_thinking"] is True


def test_run_anthropic_client_returns_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failures should be converted into a human-readable error string."""

    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

    def boom(**_: Any) -> str:
        raise anthropic_client.AnthropicClientError("bad things")

    monkeypatch.setattr(anthropic_client, "generate_content", boom)

    result = anthropic_client.run_anthropic_client([{"role": "user", "content": "Hi"}])

    assert result.startswith("ERROR from Anthropic: ")
