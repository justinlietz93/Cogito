"""Provider facades and dispatch helpers for the critique council."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Tuple, Union

# Import the main client modules to make them available through the package
from . import anthropic_client
from . import deepseek_client
from . import openai_client
from . import gemini_client
from . import model_config
from . import decorators

# Import all the exception classes from our exceptions module for backwards compatibility
from .exceptions import (
    ProviderError,
    ApiCallError,
    ApiResponseError,
    ApiBlockedError,
    ApiKeyError,
    MaxRetriesExceededError,
    JsonParsingError,
    JsonProcessingError
)

# Import decorator functions to make them easily available
from .decorators import (
    with_retry,
    with_error_handling,
    with_fallback,
    cache_result
)

DEFAULT_SYSTEM_MESSAGE = (
    "You are a highly knowledgeable assistant specialized in scientific and "
    "philosophical critique."
)

JsonLike = Union[str, Dict[str, Any]]


def _render_prompt(template: str, context: Mapping[str, Any] | None) -> str:
    """Substitute any ``{name}`` placeholders in ``template`` using ``context``."""

    prompt = template
    for key, value in dict(context or {}).items():
        prompt = prompt.replace(f"{{{key}}}", str(value))
    return prompt


def _normalise_provider(value: Any) -> str:
    """Normalise provider identifiers to the canonical key names."""

    if not value:
        return "openai"

    name = str(value).strip().lower()
    if name in {"claude", "claude-3", "claude-3-7-sonnet"}:
        return "anthropic"
    if name in {"google", "google-ai"}:
        return "gemini"
    return name


def _get_api_section(config: Mapping[str, Any]) -> Mapping[str, Any]:
    """Safely fetch the ``api`` section from a configuration mapping."""

    if isinstance(config, Mapping):
        api_section = config.get("api", {})
        if isinstance(api_section, Mapping):
            return api_section
    return {}


def _get_provider_config(api_section: Mapping[str, Any], provider: str) -> Dict[str, Any]:
    """Return provider-specific settings from the configuration if present."""

    providers_section = api_section.get("providers", {})
    if isinstance(providers_section, Mapping) and provider in providers_section:
        provider_cfg = providers_section.get(provider, {})
        if isinstance(provider_cfg, Mapping):
            return dict(provider_cfg)

    direct_cfg = api_section.get(provider, {})
    if isinstance(direct_cfg, Mapping):
        return dict(direct_cfg)

    return {}


def _extract_api_key(provider: str, api_section: Mapping[str, Any], provider_cfg: Mapping[str, Any]) -> str | None:
    """Resolve the API key for ``provider`` from configuration fallbacks."""

    for key_name in ("resolved_key", "api_key"):
        candidate = provider_cfg.get(key_name)
        if candidate:
            return str(candidate)

    primary = _normalise_provider(api_section.get("primary_provider"))
    if primary == provider and api_section.get("resolved_key"):
        return str(api_section["resolved_key"])

    return None


def _call_openai_with_retry(
    prompt_template: str,
    context: Mapping[str, Any] | None,
    config: Mapping[str, Any] | None,
    *,
    is_structured: bool,
) -> Tuple[JsonLike, str]:
    """Delegate to the OpenAI client while preserving the public signature."""

    return openai_client.call_openai_with_retry(
        prompt_template=prompt_template,
        context=dict(context or {}),
        config=dict(config or {}),
        is_structured=is_structured,
    )


def _call_gemini_with_retry(
    prompt_template: str,
    context: Mapping[str, Any] | None,
    config: Mapping[str, Any] | None,
    *,
    is_structured: bool,
) -> Tuple[JsonLike, str]:
    """Delegate to the Gemini client while preserving the public signature."""

    return gemini_client.call_gemini_with_retry(
        prompt_template=prompt_template,
        context=dict(context or {}),
        config=dict(config or {}),
        is_structured=is_structured,
    )


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if value is not None:
        return str(value)
    return default


def _call_anthropic_with_retry(
    prompt_template: str,
    context: Mapping[str, Any] | None,
    config: Mapping[str, Any] | None,
    *,
    is_structured: bool,
) -> Tuple[JsonLike, str]:
    """Execute the Anthropic client with prompt formatting and JSON parsing."""

    api_section = _get_api_section(config or {})
    provider_cfg = _get_provider_config(api_section, "anthropic")

    formatted_prompt = _render_prompt(prompt_template, context)
    system_message = _coerce_str(provider_cfg.get("system_message"), DEFAULT_SYSTEM_MESSAGE)
    if is_structured:
        system_message = f"{system_message} Respond strictly in valid JSON format."

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": formatted_prompt},
    ]

    model_name = _coerce_str(
        provider_cfg.get("model") or provider_cfg.get("model_name"),
        "claude-3-7-sonnet-20250219",
    )
    max_tokens = _coerce_int(provider_cfg.get("max_tokens"), 20000)
    temperature = _coerce_float(provider_cfg.get("temperature"), 0.2)
    enable_thinking = bool(provider_cfg.get("enable_thinking", False))
    api_key = _extract_api_key("anthropic", api_section, provider_cfg)

    response_text = anthropic_client.generate_content(
        messages=messages,
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        enable_thinking=enable_thinking,
        api_key=api_key,
    )

    if not is_structured:
        return response_text, f"Anthropic: {model_name}"

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise JsonParsingError(f"Anthropic response was not valid JSON: {exc}") from exc

    return parsed, f"Anthropic: {model_name}"


_PROVIDER_HANDLERS = {
    "openai": _call_openai_with_retry,
    "anthropic": _call_anthropic_with_retry,
    "gemini": _call_gemini_with_retry,
}


def call_with_retry(
    prompt_template: str,
    context: Mapping[str, Any] | None,
    config: Mapping[str, Any] | None,
    is_structured: bool = False,
) -> Tuple[JsonLike, str]:
    """Dispatch prompt execution to the configured primary provider."""

    api_section = _get_api_section(config or {})
    provider = _normalise_provider(api_section.get("primary_provider"))
    handler = _PROVIDER_HANDLERS.get(provider)

    if handler is None:
        raise ProviderError(f"Unsupported primary provider '{provider}' configured for call_with_retry.")

    return handler(
        prompt_template=prompt_template,
        context=context,
        config=config,
        is_structured=is_structured,
    )
