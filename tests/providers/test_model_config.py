from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.providers import model_config


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

    _clear_cache(model_config.get_openai_config)
    _clear_cache(model_config.get_api_config)
    yield
    _clear_cache(model_config.get_openai_config)
    _clear_cache(model_config.get_api_config)


def test_get_openai_config_defaults_to_accessible_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no configuration or env override exists, prefer gpt-4o-mini."""

    monkeypatch.setattr(model_config.config_loader, "get_api_config", lambda: {})
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_DEFAULT_MODEL", raising=False)

    config = model_config.get_openai_config()

    assert config["model"] == "gpt-4o-mini"
    assert config["max_tokens"] == 8192


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

