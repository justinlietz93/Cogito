import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.application.critique.configuration import ModuleConfigBuilder
from src.application.critique.exceptions import ConfigurationError, MissingApiKeyError
from src.application.user_settings.services import UserSettingsService
from src.domain.user_settings.models import UserSettings


class InMemoryRepository:
    def __init__(self, initial: UserSettings | None = None) -> None:
        self._settings = initial or UserSettings()

    def load(self) -> UserSettings:
        return self._settings

    def save(self, settings: UserSettings) -> None:
        self._settings = settings


def build_service(initial: UserSettings | None = None) -> UserSettingsService:
    return UserSettingsService(InMemoryRepository(initial))


def test_builder_uses_stored_api_keys() -> None:
    service = build_service(UserSettings(api_keys={"openai": "stored-key"}))
    base_config = {
        "api": {
            "primary_provider": "openai",
            "openai": {"model": "o3"},
        }
    }

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    config = builder.build()

    assert config["api"]["primary_provider"] == "openai"
    assert config["api"]["resolved_key"] == "stored-key"
    assert config["api"]["providers"]["openai"]["resolved_key"] == "stored-key"


def test_builder_includes_additional_providers() -> None:
    service = build_service(UserSettings(api_keys={"anthropic": "secret"}))
    base_config = {"api": {"primary_provider": "anthropic"}}

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    config = builder.build()

    assert "anthropic" in config["api"]["providers"]
    assert config["api"]["resolved_key"] == "secret"


def test_builder_reads_nested_provider_section() -> None:
    service = build_service(UserSettings())
    base_config = {
        "api": {
            "primary_provider": "openai",
            "providers": {"openai": {"model": "gpt-4o"}},
        }
    }

    builder = ModuleConfigBuilder(
        base_config,
        service,
        lambda key: "env-key" if key == "OPENAI_API_KEY" else None,
    )
    config = builder.build()

    assert config["api"]["providers"]["openai"]["model"] == "gpt-4o"
    assert config["api"]["resolved_key"] == "env-key"


def test_builder_merges_nested_and_top_level_provider_config() -> None:
    service = build_service(UserSettings())
    base_config = {
        "api": {
            "primary_provider": "openai",
            "providers": {"openai": {"model": "gpt-4o", "temperature": 0}},
            "openai": {"temperature": 1},
        }
    }

    builder = ModuleConfigBuilder(
        base_config,
        service,
        lambda key: "api-key" if key == "OPENAI_API_KEY" else None,
    )
    config = builder.build()

    assert config["api"]["providers"]["openai"]["model"] == "gpt-4o"
    assert config["api"]["providers"]["openai"]["temperature"] == 1


def test_builder_prefers_env_when_no_stored_key() -> None:
    service = build_service()
    base_config = {
        "api": {
            "primary_provider": "gemini",
            "gemini": {"model_name": "foo"},
        }
    }

    builder = ModuleConfigBuilder(base_config, service, lambda key: "env-key" if key == "GEMINI_API_KEY" else None)
    config = builder.build()

    assert config["api"]["resolved_key"] == "env-key"
    assert config["api"]["providers"]["gemini"]["resolved_key"] == "env-key"


def test_missing_primary_key_raises() -> None:
    service = build_service()
    base_config = {"api": {"primary_provider": "openai", "openai": {}}}

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    with pytest.raises(MissingApiKeyError):
        builder.build()


def test_builder_prefers_user_selected_provider() -> None:
    settings = UserSettings(
        api_keys={"anthropic": "pref-key", "openai": "ignored"},
        preferred_provider="anthropic",
    )
    service = build_service(settings)
    base_config = {
        "api": {
            "primary_provider": "openai",
            "openai": {"api_key": "from-openai"},
            "providers": {"anthropic": {"model": "claude"}},
        }
    }

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    config = builder.build()

    assert config["api"]["primary_provider"] == "anthropic"
    assert config["api"]["resolved_key"] == "pref-key"


def test_builder_uses_api_key_from_provider_entry_when_present() -> None:
    service = build_service()
    base_config = {
        "api": {
            "primary_provider": "openai",
            "openai": {"api_key": "embedded-key"},
        }
    }

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    config = builder.build()

    assert config["api"]["resolved_key"] == "embedded-key"
    assert config["api"]["providers"]["openai"]["resolved_key"] == "embedded-key"


def test_builder_falls_back_to_sorted_provider_when_not_configured() -> None:
    service = build_service(UserSettings(api_keys={"claude": "c-key"}))
    base_config = {
        "api": {
            "providers": {
                "openai": {"api_key": "o-key"},
                "claude": {"api_key": "c-key"},
            }
        }
    }

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    config = builder.build()

    assert config["api"]["primary_provider"] == "claude"
    assert config["api"]["resolved_key"] == "c-key"


def test_builder_raises_when_no_providers_detected() -> None:
    service = build_service(UserSettings())
    base_config = {"api": {}}

    builder = ModuleConfigBuilder(base_config, service, lambda key: None)
    with pytest.raises(ConfigurationError):
        builder.build()
