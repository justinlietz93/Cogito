"""Unit tests for input gating to prevent provider context overflows.

Validates:
- Safe inputs: no mutation, no truncation metadata.
- Oversized inputs: content truncated deterministically, metadata annotated.
- Existing truncation_reason is preserved and appended with 'context_limit'.
"""

from __future__ import annotations

from typing import Dict, Any

import pytest

from src.pipeline_input import PipelineInput
from src.application.critique.input_gating import gate_pipeline_input_for_model


def _make_config(model: str, window: int | None = None) -> Dict[str, Any]:
    """Build a minimal config structure compatible with the gating utility."""
    cfg: Dict[str, Any] = {
        "api": {
            "openai": {
                "model": model,
            }
        }
    }
    if window is not None:
        cfg["api"]["openai"]["context_window"] = int(window)
    return cfg


def test_gate_pipeline_input_no_truncation_when_below_threshold() -> None:
    # Given a small content well below threshold
    # window=1000 tokens, reserved=100 -> threshold=900 tokens -> ~3600 chars
    content = "x" * 1000  # approx 250 tokens by 4-chars-per-token heuristic
    original = PipelineInput(content=content, metadata={"input_type": "directory"})

    config = _make_config(model="gpt-4o-mini", window=1000)
    gated = gate_pipeline_input_for_model(original, config, reserved_tokens=100)

    # No mutation expected (safe path returns original object)
    assert gated is original
    assert "truncated" not in gated.metadata
    assert "truncation_reason" not in gated.metadata
    assert gated.content == content


def test_gate_pipeline_input_truncates_when_exceeding_threshold() -> None:
    # window=2000 tokens, reserved=500 -> threshold=1500 tokens -> char_limit=6000 chars
    original_chars = 20_000  # much larger than 6,000
    content = "a" * original_chars
    original = PipelineInput(content=content, metadata={"input_type": "directory"})

    config = _make_config(model="gpt-4o-mini", window=2000)
    gated = gate_pipeline_input_for_model(original, config, reserved_tokens=500)

    # Expect a new object with truncated content
    assert gated is not original
    assert len(gated.content) == 6000
    assert gated.metadata.get("truncated") is True
    assert gated.metadata.get("truncation_reason") == "context_limit"
    # Reproducibility stats present
    assert gated.metadata.get("context_limit_tokens") == 2000
    assert gated.metadata.get("reserved_tokens") == 500
    assert gated.metadata.get("gated_characters") == 6000
    assert gated.metadata.get("original_characters") == original_chars
    # sanity on approx tokens
    assert isinstance(gated.metadata.get("approx_input_tokens"), int)


def test_gate_pipeline_input_appends_existing_truncation_reason() -> None:
    # window=1200 tokens, reserved=200 -> threshold=1000 tokens -> char_limit=4000 chars
    content = "b" * 10_000
    original = PipelineInput(
        content=content,
        metadata={"input_type": "directory", "truncated": True, "truncation_reason": "max_chars"},
    )
    config = _make_config(model="gpt-4o", window=1200)
    gated = gate_pipeline_input_for_model(original, config, reserved_tokens=200)

    assert gated.metadata.get("truncated") is True
    # Should append context_limit to the existing reason
    assert gated.metadata.get("truncation_reason") == "max_chars;context_limit"
    assert len(gated.content) == 4000