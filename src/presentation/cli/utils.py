"""Utility helpers for the CLI presentation layer.

Purpose:
    Provide presentation-layer helpers for manipulating CLI arguments,
    formatting pipeline metadata, and masking sensitive values.
External Dependencies:
    Python standard library only.
Fallback Semantics:
    No automatic fallbacks; callers decide how to handle missing values.
Timeout Strategy:
    Not applicable for these synchronous helpers.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from ...pipeline_input import PipelineInput


def extract_latex_args(args: argparse.Namespace) -> Optional[argparse.Namespace]:
    """Extract LaTeX-related CLI arguments into a lightweight namespace.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Namespace containing LaTeX parameters or ``None`` when LaTeX output is
        not requested.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    if not getattr(args, "latex", False):
        return None
    return SimpleNamespace(
        latex=True,
        latex_compile=getattr(args, "latex_compile", False),
        latex_output_dir=getattr(args, "latex_output_dir", "latex_output"),
        latex_scientific_level=getattr(args, "latex_scientific_level", "high"),
        direct_latex=getattr(args, "direct_latex", False),
    )


def derive_base_name(pipeline_input: PipelineInput) -> str:
    """Derive a normalised file-system friendly base name for outputs.

    Args:
        pipeline_input: Resolved pipeline input containing source metadata.

    Returns:
        Sanitised base name without redundant ``_critique`` suffixes.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    source_hint = pipeline_input.source or pipeline_input.metadata.get("source_path")
    candidate: str
    if isinstance(source_hint, str) and source_hint.strip():
        source_path = Path(source_hint)
        candidate = source_path.stem if source_path.suffix else source_path.name
    else:
        candidate = str(pipeline_input.metadata.get("input_label", "cli_input"))

    normalised = candidate.strip().replace(" ", "_") or "cli_input"
    lowered = normalised.lower()
    if lowered.endswith("_critique"):
        normalised = normalised[: -len("_critique")]
    elif lowered.endswith("critique"):
        normalised = normalised[: -len("critique")]
    normalised = normalised.strip("_") or "cli_input"
    return normalised


def mask_key(key: str) -> str:
    """Mask an API key while preserving useful context.

    Args:
        key: Original secret value.

    Returns:
        Masked representation retaining the first three and last two characters
        for debugging convenience.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    if len(key) <= 6:
        return "*" * len(key)
    return f"{key[:3]}***{key[-2:]}"


__all__ = ["derive_base_name", "extract_latex_args", "mask_key"]
