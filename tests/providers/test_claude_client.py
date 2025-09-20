from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import logging

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import claude_client


def make_chunk(event_type: str, **attributes: Any) -> SimpleNamespace:
    """Create a faux Claude streaming chunk for the tests."""

    return SimpleNamespace(type=event_type, **attributes)


def test_configure_client_uses_provided_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supplying a key should pass it directly to the SDK constructor."""

    captured: dict[str, Any] = {}

    class DummyAnthropic:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(claude_client.anthropic, "Anthropic", DummyAnthropic)

    client = claude_client.configure_client("secret")

    assert isinstance(client, DummyAnthropic)
    assert captured["api_key"] == "secret"


def test_configure_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper should raise when no API key is discoverable."""

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(claude_client.ClaudeClientError):
        claude_client.configure_client()


def test_configure_client_wraps_sdk_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors during SDK initialisation should be wrapped."""

    class DummyAnthropic:
        def __init__(self, api_key: str) -> None:  # noqa: D401 - interface requirement
            raise RuntimeError("boom")

    monkeypatch.setattr(claude_client.anthropic, "Anthropic", DummyAnthropic)

    with pytest.raises(claude_client.ClaudeClientError) as excinfo:
        claude_client.configure_client("key")

    assert "Failed to configure Anthropic client" in str(excinfo.value)


def test_generate_content_handles_streaming_without_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When thinking is disabled, the original temperature should remain."""

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

    monkeypatch.setattr(claude_client, "configure_client", fake_configure_client)

    result = claude_client.generate_content(
        [{"role": "user", "content": "Hi"}],
        enable_thinking=False,
        temperature=0.4,
    )

    assert result == "Hi"
    assert captured["params"]["temperature"] == pytest.approx(0.4)
    assert "thinking" not in captured["params"]


def test_generate_content_enables_thinking_and_clamps_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thinking mode should clamp the supplied budget and include the system prompt."""

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
                    make_chunk("content_block_stop"),
                    make_chunk(
                        "content_block_start",
                        index=1,
                        content_block=SimpleNamespace(type="text"),
                    ),
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text="Hello"),
                    ),
                    make_chunk("content_block_stop"),
                    make_chunk("message_stop"),
                ]

        return SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(claude_client, "configure_client", fake_configure_client)

    result = claude_client.generate_content(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "Hi"},
        ],
        max_tokens=1200,
        enable_thinking=True,
        thinking_budget=3000,
    )

    params = captured["params"]
    assert result == "Hello"
    assert params["system"] == "system"
    assert params["messages"] == [{"role": "user", "content": "Hi"}]
    assert params["temperature"] == pytest.approx(1.0)
    assert params["thinking"]["budget_tokens"] == 1100


def test_generate_content_wraps_configuration_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration failures should surface as ClaudeClientError."""

    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("explode")

    monkeypatch.setattr(claude_client, "configure_client", boom)

    with pytest.raises(claude_client.ClaudeClientError):
        claude_client.generate_content([{"role": "user", "content": "Hi"}])


def test_generate_content_defaults_thinking_budget_and_logs_thinking(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When no budget is provided the helper should derive one and log thinking deltas."""

    captured: dict[str, Any] = {}

    def fake_configure_client(api_key: str | None = None) -> Any:
        class FakeMessages:
            def create(self, **params: Any) -> list[SimpleNamespace]:
                captured["params"] = params
                return [
                    make_chunk(
                        "content_block_start",
                        index=0,
                        content_block=SimpleNamespace(type="thinking"),
                    ),
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(
                            type="thinking_delta", thinking="deliberating"
                        ),
                    ),
                    make_chunk(
                        "content_block_delta",
                        delta=SimpleNamespace(type="text_delta", text="Answer"),
                    ),
                    make_chunk("message_stop"),
                ]

        return SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(claude_client, "configure_client", fake_configure_client)

    caplog.set_level(logging.DEBUG, logger=claude_client.logger.name)

    result = claude_client.generate_content(
        [{"role": "user", "content": "Explain"}],
        max_tokens=1500,
        enable_thinking=True,
    )

    assert result == "Answer"
    params = captured["params"]
    assert params["thinking"]["budget_tokens"] == 1024
    assert any("Thinking: deliberating" in record.getMessage() for record in caplog.records)
