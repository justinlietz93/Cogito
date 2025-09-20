from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import model_config


CACHED_FUNCTIONS = [
    model_config.get_primary_provider,
    model_config.get_api_config,
    model_config.get_anthropic_config,
    model_config.get_deepseek_config,
    model_config.get_openai_config,
    model_config.get_gemini_config,
]


def _clear_cache(func: object) -> None:
    """Clear the internal cache used by :func:`cache_result` wrappers."""

    closure = getattr(func, "__closure__", None) or ()
    for cell in closure:
        contents = getattr(cell, "cell_contents", None)
        if isinstance(contents, dict):
            contents.clear()


@pytest.fixture(autouse=True)
def reset_model_config_cache() -> None:
    """Ensure each test observes a fresh cache state."""

    for function in CACHED_FUNCTIONS:
        _clear_cache(function)
    yield
    for function in CACHED_FUNCTIONS:
        _clear_cache(function)


def test_get_openai_config_defaults_to_accessible_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no configuration or env override exists, prefer gpt-4o-mini."""

    monkeypatch.setattr(model_config.config_loader, "get_api_config", lambda: {})
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_DEFAULT_MODEL", raising=False)

    config = model_config.get_openai_config()

    assert config["model"] == "gpt-4o-mini"
    assert config["max_tokens"] == 8192
    assert config["temperature"] == pytest.approx(0.2)


def test_get_openai_config_prefers_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should take precedence over template defaults."""

    monkeypatch.setattr(model_config.config_loader, "get_api_config", lambda: {})
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.delenv("OPENAI_DEFAULT_MODEL", raising=False)

    config = model_config.get_openai_config()

    assert config["model"] == "gpt-4o"


def test_get_openai_config_preserves_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit configuration should not be overridden by environment defaults."""

    monkeypatch.setattr(
        model_config.config_loader,
        "get_api_config",
        lambda: {"openai": {"model": "custom-model"}},
    )
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    config = model_config.get_openai_config()

    assert config["model"] == "custom-model"


def test_get_openai_config_uses_default_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENAI_DEFAULT_MODEL should act as a secondary override."""

    monkeypatch.setattr(model_config.config_loader, "get_api_config", lambda: {})
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_DEFAULT_MODEL", "gpt-4o")

    config = model_config.get_openai_config()

    assert config["model"] == "gpt-4o"


def test_get_primary_provider_prefers_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loader should return any configured primary provider value."""

    monkeypatch.setattr(
        model_config.config_loader,
        "get",
        lambda section, key, default=None: "anthropic",
    )

    assert model_config.get_primary_provider() == "anthropic"


def test_get_primary_provider_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing configuration should return the documented default."""

    def fake_get(section: str, key: str, default: str | None = None) -> str | None:
        assert section == "api"
        assert key == "primary_provider"
        return default

    monkeypatch.setattr(model_config.config_loader, "get", fake_get)

    assert model_config.get_primary_provider() == "openai"


def test_get_api_config_caches_loader_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cached accessor should only call the loader once per test."""

    calls: list[str] = []

    def fake_get_api_config() -> dict[str, str]:
        calls.append("called")
        return {"value": "data"}

    monkeypatch.setattr(model_config.config_loader, "get_api_config", fake_get_api_config)

    first = model_config.get_api_config()
    second = model_config.get_api_config()

    assert first is second
    assert calls == ["called"]


def test_get_anthropic_config_reads_api_section(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anthropic configuration should be returned from the API section."""

    monkeypatch.setattr(
        model_config.config_loader,
        "get_api_config",
        lambda: {"anthropic": {"model": "claude"}},
    )

    assert model_config.get_anthropic_config() == {"model": "claude"}


def test_get_deepseek_config_supplies_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model name and base URL defaults should populate missing values."""

    monkeypatch.setattr(
        model_config.config_loader,
        "get_api_config",
        lambda: {"deepseek": {}},
    )

    config = model_config.get_deepseek_config()

    assert config["model_name"] == "deepseek-reasoner"
    assert config["base_url"] == "https://api.deepseek.com/v1"


def test_get_deepseek_config_respects_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit settings should be preserved without alteration."""

    monkeypatch.setattr(
        model_config.config_loader,
        "get_api_config",
        lambda: {"deepseek": {"model_name": "chat", "base_url": "http://example"}},
    )

    config = model_config.get_deepseek_config()

    assert config["model_name"] == "chat"
    assert config["base_url"] == "http://example"


def test_get_gemini_config_injects_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Gemini accessor should fill in sensible defaults."""

    monkeypatch.setattr(
        model_config.config_loader,
        "get_api_config",
        lambda: {"gemini": {}},
    )

    config = model_config.get_gemini_config()

    assert config["model_name"] == "gemini-2.5-pro-exp-03-25"
    assert config["max_output_tokens"] == 8192
    assert config["temperature"] == pytest.approx(0.6)

