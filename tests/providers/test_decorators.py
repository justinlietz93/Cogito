"""Tests for the provider helper decorators."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import importlib

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import decorators
from src.providers.exceptions import (  # noqa: WPS347
    ApiCallError,
    ApiResponseError,
    JsonParsingError,
    MaxRetriesExceededError,
)


def test_with_retry_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient ``ApiCallError`` should trigger a retry before succeeding."""

    sleep_calls: list[float] = []
    monkeypatch.setattr(decorators.time, "sleep", sleep_calls.append)

    attempts: list[str] = []

    @decorators.with_retry(max_attempts=3, delay_base=2.0)
    def flaky() -> str:
        attempts.append("called")
        if len(attempts) == 1:
            raise ApiCallError("temporary")
        return "ok"

    assert flaky() == "ok"
    assert len(attempts) == 2
    assert sleep_calls == [1.0]


def test_with_retry_without_attempts_raises() -> None:
    """When no attempts are permitted, an ``ApiCallError`` should surface."""

    @decorators.with_retry(max_attempts=0)
    def impossible() -> None:
        pytest.fail("Function should never execute")

    with pytest.raises(ApiCallError):
        impossible()


def test_with_retry_raises_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent ``ApiResponseError`` should escalate after exhausting retries."""

    monkeypatch.setattr(decorators.time, "sleep", lambda *_: None)

    @decorators.with_retry(max_attempts=2, delay_base=3.0)
    def always_fail() -> None:
        raise ApiResponseError("nope")

    with pytest.raises(MaxRetriesExceededError) as excinfo:
        always_fail()

    assert "nope" in str(excinfo.value)


def test_with_retry_propagates_unexpected_exception() -> None:
    """Errors outside the retry whitelist should propagate immediately."""

    @decorators.with_retry(max_attempts=2)
    def bad_call() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        bad_call()


def test_with_error_handling_wraps_unknown_exception() -> None:
    """Unexpected exceptions should be wrapped in ``ApiCallError``."""

    @decorators.with_error_handling
    def faulty() -> None:
        raise RuntimeError("explode")

    with pytest.raises(ApiCallError) as excinfo:
        faulty()

    assert "Unexpected error" in str(excinfo.value)


def test_with_error_handling_preserves_known_exceptions() -> None:
    """Provider errors should surface unchanged for callers."""

    @decorators.with_error_handling
    def raise_response_error() -> None:
        raise JsonParsingError("bad json")

    with pytest.raises(JsonParsingError):
        raise_response_error()


def test_with_error_handling_logs_api_call_error() -> None:
    """Existing ``ApiCallError`` instances should propagate unchanged."""

    @decorators.with_error_handling
    def raise_api_error() -> None:
        raise ApiCallError("boom")

    with pytest.raises(ApiCallError):
        raise_api_error()


def test_with_error_handling_logs_json_error() -> None:
    """JSON parsing errors should be logged and re-raised directly."""

    @decorators.with_error_handling
    def raise_json_error() -> None:
        raise JsonParsingError("invalid")

    with pytest.raises(JsonParsingError):
        raise_json_error()


def test_with_error_handling_catches_custom_json_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dedicated JSON branch should run even if the class is patched."""

    class CustomJsonParsingError(Exception):
        pass

    monkeypatch.setattr(decorators, "JsonParsingError", CustomJsonParsingError)

    @decorators.with_error_handling
    def raise_custom_json() -> None:
        raise CustomJsonParsingError("broken")

    with pytest.raises(CustomJsonParsingError):
        raise_custom_json()


@pytest.mark.parametrize(
    ("fallback", "attribute"),
    [
        ("openai", "run_openai_client"),
        ("anthropic", "run_anthropic_client"),
        ("deepseek", "run_deepseek_client"),
        ("gemini", "run_gemini_client"),
    ],
)
def test_with_fallback_delegates_to_provider(
    fallback: str,
    attribute: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the primary implementation fails, the decorator should delegate."""

    recorded: dict[str, Any] = {}

    def fake_provider(*args: Any, **kwargs: Any) -> str:
        recorded["args"] = args
        recorded["kwargs"] = kwargs
        return f"fallback-from-{fallback}"

    module = importlib.import_module(f"src.providers.{fallback}_client")
    monkeypatch.setattr(module, attribute, fake_provider)

    @decorators.with_fallback(fallback)
    def primary(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("boom")

    result = primary("value", keyword=True)

    assert result == f"fallback-from-{fallback}"
    assert recorded["args"] == ("value",)
    assert recorded["kwargs"] == {"keyword": True}


def test_with_fallback_unknown_provider_re_raises() -> None:
    """Unknown fallbacks should simply re-raise the original exception."""

    @decorators.with_fallback("unsupported")
    def primary() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        primary()


def test_cache_result_returns_cached_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Subsequent calls with identical arguments should hit the cache."""

    calls: list[int] = []

    @decorators.cache_result(maxsize=4, ttl=60)
    def compute(value: int) -> int:
        calls.append(value)
        return value * 2

    assert compute(3) == 6
    assert compute(3) == 6
    assert calls == [3]


def test_cache_result_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the TTL elapses, the cached value should be recomputed."""

    times = iter([0.0, 10.0])
    monkeypatch.setattr(decorators.time, "time", lambda: next(times))

    calls: list[int] = []

    @decorators.cache_result(maxsize=4, ttl=5)
    def compute(value: int) -> int:
        calls.append(value)
        return value

    assert compute(1) == 1
    assert compute(1) == 1
    assert calls == [1, 1]


def test_cache_result_evicts_oldest_entry() -> None:
    """When the cache is full, the least-recent item should be removed."""

    calls: list[int] = []

    @decorators.cache_result(maxsize=1, ttl=60)
    def compute(value: int) -> int:
        calls.append(value)
        return value

    assert compute(1) == 1
    assert compute(2) == 2
    assert compute(1) == 1
    assert calls == [1, 2, 1]
