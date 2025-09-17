"""Configuration helpers for critique execution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional

from ..user_settings.services import UserSettingsService
from .exceptions import ConfigurationError, MissingApiKeyError

EnvGetter = Callable[[str], Optional[str]]


class ModuleConfigBuilder:
    """Builds the runtime configuration for the critique pipeline."""

    def __init__(
        self,
        base_config: Optional[Mapping[str, Any]],
        settings_service: UserSettingsService,
        env_getter: EnvGetter,
    ) -> None:
        self._base_config = deepcopy(dict(base_config or {}))
        self._settings_service = settings_service
        self._env_getter = env_getter

    def build(self) -> Dict[str, Any]:
        settings = self._settings_service.get_settings()
        base_api = dict(self._base_config.get("api", {}))
        raw_providers = base_api.get("providers", {})
        providers_template: Dict[str, Mapping[str, Any]] = {}
        if isinstance(raw_providers, Mapping):
            providers_template = {
                name: value
                for name, value in raw_providers.items()
                if isinstance(value, Mapping)
            }

        provider_names = {
            name
            for name, value in base_api.items()
            if isinstance(value, MutableMapping)
        }
        provider_names.discard("providers")
        provider_names.discard("resolved_key")
        provider_names.discard("primary_provider")
        provider_names.update(providers_template.keys())
        provider_names.update(settings.api_keys.keys())

        providers: Dict[str, Dict[str, Any]] = {}
        for provider in sorted(provider_names):
            providers[provider] = self._build_provider_config(
                provider,
                base_api,
                providers_template,
                settings.api_keys,
            )

        primary_provider = self._resolve_primary_provider(base_api, providers, settings.preferred_provider)

        config = {
            "api": {
                "providers": providers,
                "primary_provider": primary_provider,
            },
            "reasoning_tree": deepcopy(self._base_config.get("reasoning_tree", {})),
            "council_orchestrator": deepcopy(self._base_config.get("council_orchestrator", {})),
        }

        for provider, provider_config in providers.items():
            config["api"][provider] = provider_config

        primary_entry = providers.get(primary_provider, {})
        resolved_key = self._extract_key(primary_entry)
        if not resolved_key:
            raise MissingApiKeyError(
                f"Primary provider '{primary_provider}' is missing an API key. Configure it via the settings menu."
            )
        config["api"]["resolved_key"] = resolved_key

        return config

    def _build_provider_config(
        self,
        provider: str,
        base_api: Mapping[str, Any],
        template: Mapping[str, Mapping[str, Any]],
        stored_keys: Mapping[str, str],
    ) -> Dict[str, Any]:
        provider_config: Dict[str, Any] = {}
        template_config = template.get(provider)
        if isinstance(template_config, Mapping):
            provider_config.update(deepcopy(template_config))

        base_entry = base_api.get(provider, {})
        if isinstance(base_entry, Mapping):
            provider_config.update(deepcopy(base_entry))

        key_from_settings = stored_keys.get(provider)
        key_from_env = self._env_getter(f"{provider.upper()}_API_KEY")
        existing_key = self._extract_key(provider_config)

        resolved_key = key_from_settings or key_from_env or existing_key
        if resolved_key:
            provider_config.setdefault("resolved_key", resolved_key)
            provider_config.setdefault("api_key", resolved_key)

        return provider_config

    @staticmethod
    def _extract_key(config: Mapping[str, Any]) -> Optional[str]:
        if "resolved_key" in config and config["resolved_key"]:
            return str(config["resolved_key"])
        if "api_key" in config and config["api_key"]:
            return str(config["api_key"])
        return None

    def _resolve_primary_provider(
        self,
        base_api: Mapping[str, Any],
        providers: Mapping[str, Mapping[str, Any]],
        preferred_provider: Optional[str],
    ) -> str:
        if preferred_provider and preferred_provider in providers:
            return preferred_provider

        if isinstance(base_api.get("primary_provider"), str):
            candidate = base_api["primary_provider"]
            if candidate in providers:
                return str(candidate)

        if providers:
            return next(iter(sorted(providers.keys())))

        raise ConfigurationError("No providers configured for critique execution.")


__all__ = ["ModuleConfigBuilder"]
