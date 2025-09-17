"""Integration-style tests for the o3-mini pathway."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import openai_client


def test_run_openai_client_composes_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The high-level runner should stitch together messages for o3-mini models."""

    captured: Dict[str, Any] = {}

    def fake_get_openai_config() -> Dict[str, Any]:
        return {"model": "o3-mini", "max_tokens": 256, "temperature": 0.1}

    def fake_call_openai_with_retry(prompt_template: str, context: Dict[str, Any], config: Dict[str, Any], is_structured: bool) -> tuple[str, str]:
        captured["template"] = prompt_template
        captured["context"] = context
        captured["config"] = config
        captured["structured"] = is_structured
        return "Result from provider", "o3-mini"

    monkeypatch.setattr(openai_client, "get_openai_config", fake_get_openai_config)
    monkeypatch.setattr(openai_client, "call_openai_with_retry", fake_call_openai_with_retry)

    response = openai_client.run_openai_client(
        messages=[
            {"role": "system", "content": "Act carefully."},
            {"role": "user", "content": "First part."},
            {"role": "user", "content": "Second part."},
        ],
    )

    assert response == "Result from provider"
    assert captured["template"] == "{content}"
    assert captured["context"]["content"].strip() == "First part.\nSecond part."
    assert captured["config"]["api"]["openai"]["model"] == "o3-mini"
    assert captured["config"]["api"]["openai"]["system_message"] == "Act carefully."
    assert captured["structured"] is False


def test_run_openai_client_returns_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any provider failures should be converted into readable error strings."""

    def fake_get_openai_config() -> Dict[str, Any]:
        return {"model": "o3-mini"}

    def fake_call_openai_with_retry(*_: Any, **__: Any) -> tuple[str, str]:  # pragma: no cover - signature only
        raise RuntimeError("boom")

    monkeypatch.setattr(openai_client, "get_openai_config", fake_get_openai_config)
    monkeypatch.setattr(openai_client, "call_openai_with_retry", fake_call_openai_with_retry)

    response = openai_client.run_openai_client([
        {"role": "user", "content": "Hello"},
    ])

    assert response.startswith("ERROR from OpenAI: ")
    assert "boom" in response


def test_run_openai_client_supports_custom_model_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit model arguments should override configuration defaults."""

    captured_models: List[str] = []

    def fake_get_openai_config() -> Dict[str, Any]:
        return {"model": "o3-mini", "max_tokens": 123, "temperature": 0.9}

    def fake_call_openai_with_retry(prompt_template: str, context: Dict[str, Any], config: Dict[str, Any], is_structured: bool) -> tuple[str, str]:
        captured_models.append(config["api"]["openai"]["model"])
        return "ok", config["api"]["openai"]["model"]

    monkeypatch.setattr(openai_client, "get_openai_config", fake_get_openai_config)
    monkeypatch.setattr(openai_client, "call_openai_with_retry", fake_call_openai_with_retry)

    openai_client.run_openai_client(
        messages=[{"role": "user", "content": "Ping"}],
        model_name="o3-mini-high",
        max_tokens=42,
        temperature=0.33,
    )

    assert captured_models == ["o3-mini-high"]
