"""Input gating utilities for critique execution.

Purpose:
    Prevent provider calls from exceeding model context limits by proactively
    truncating oversized pipeline content with reproducible metadata.

External Dependencies:
    Python standard library only.

Fallback Semantics:
    When the input exceeds the computed context window threshold, the content is
    truncated with a clear metadata record:
      - truncated: True
      - truncation_reason: "context_limit"
      - context_limit_tokens, approx_input_tokens, reserved_tokens,
        original_characters, gated_characters

Timeout Strategy:
    Not applicable. This module performs pure CPU-side calculations.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from ...pipeline_input import PipelineInput

_LOGGER = logging.getLogger(__name__)


def _approximate_token_count(text: str) -> int:
    """Return a rough token estimate for UTF-8 English-like text.

    Heuristic:
        1 token ~ 4 characters (conservative).
    """
    if not text:
        return 0
    # Use integer arithmetic for determinism
    return max(1, len(text) // 4)


def _pluck(mapping: Mapping[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested mapping keys and return a value or default."""
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _default_window_for_model(model: str) -> int:
    """Return a conservative default context window for known models.

    Notes:
        - o-series (o1, o3, etc.): use 240k as a conservative cap below observed ~272k.
        - 4o family: assume 128k.
        - Fallback: 128k.
    """
    m = (model or "").lower()
    if m.startswith("o") or m.startswith("o1") or m.startswith("o3") or "o3" in m or "o1" in m:
        return 240_000
    if "gpt-4o" in m or "gpt-4.1" in m or "gpt-4" in m:
        return 128_000
    return 128_000


def _resolve_context_window(config: Mapping[str, Any]) -> tuple[int, str]:
    """Resolve an approximate context window (tokens) and the model name from config.

    Resolution order:
        1) config['api']['openai']['context_window'] or ['max_context_tokens']
        2) config['api']['providers']['openai']['context_window'] or ['max_context_tokens']
        3) default based on model name
    """
    api = _pluck(config, "api", default={}) or {}
    openai_cfg = _pluck(api, "openai", default={}) or {}
    providers = _pluck(api, "providers", default={}) or {}
    provider_openai = _pluck(providers, "openai", default={}) or {}

    model = (
        _pluck(openai_cfg, "model")
        or _pluck(provider_openai, "model")
        or "gpt-4o-mini"
    )

    explicit = (
        _pluck(openai_cfg, "context_window")
        or _pluck(openai_cfg, "max_context_tokens")
        or _pluck(provider_openai, "context_window")
        or _pluck(provider_openai, "max_context_tokens")
    )
    if isinstance(explicit, int) and explicit > 0:
        return explicit, str(model)

    return _default_window_for_model(str(model)), str(model)


def gate_pipeline_input_for_model(
    pipeline_input: PipelineInput,
    config: Mapping[str, Any],
    *,
    reserved_tokens: int = 20_000,
) -> PipelineInput:
    """Return a PipelineInput respecting the model's context window with headroom.

    Parameters:
        pipeline_input: The aggregated input to gate.
        config: The resolved module configuration (ModuleConfigBuilder.build()).
        reserved_tokens: Safety headroom for prompts/system/response budget.

    Returns:
        The original PipelineInput when safe; otherwise a new PipelineInput with
        truncated content and augmented metadata.

    Side Effects:
        Logs a single info message when truncation occurs.

    Failure Modes:
        None. This function cannot raise provider-related errors and performs only
        deterministic CPU-bound operations.
    """
    content = pipeline_input.content or ""
    approx_tokens = _approximate_token_count(content)
    context_window, model_name = _resolve_context_window(config)
    threshold = max(1, context_window - max(1, reserved_tokens))

    if approx_tokens <= threshold:
        return pipeline_input

    # Compute a conservative character limit based on the threshold
    char_limit = threshold * 4  # inverse of the approximation
    if len(content) <= char_limit:
        # Edge case: char length fits but token heuristic exceeded. Keep as-is.
        return pipeline_input

    truncated_text = content[:char_limit]
    new_metadata = dict(pipeline_input.metadata or {})
    new_metadata["truncated"] = True
    # Preserve the original truncation_reason when already present; append context info.
    if "truncation_reason" in new_metadata and new_metadata["truncation_reason"]:
        reason = str(new_metadata["truncation_reason"])
        new_metadata["truncation_reason"] = f"{reason};context_limit"
    else:
        new_metadata["truncation_reason"] = "context_limit"

    # Provide reproducible gating stats
    new_metadata["context_limit_tokens"] = context_window
    new_metadata["reserved_tokens"] = reserved_tokens
    new_metadata["approx_input_tokens"] = approx_tokens
    new_metadata["gated_characters"] = char_limit
    new_metadata["original_characters"] = len(content)
    new_metadata["model_name_for_window"] = model_name

    _LOGGER.info(
        "event=context_gate status=truncated model=%s approx_tokens=%d window=%d reserved=%d "
        "orig_chars=%d gated_chars=%d",
        model_name,
        approx_tokens,
        context_window,
        reserved_tokens,
        len(content),
        char_limit,
    )

    return PipelineInput(
        content=truncated_text,
        source=pipeline_input.source,
        metadata=new_metadata,
    )