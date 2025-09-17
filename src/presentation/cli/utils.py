"""Utility helpers for the CLI presentation layer."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from ...pipeline_input import PipelineInput


def extract_latex_args(args: argparse.Namespace) -> Optional[argparse.Namespace]:
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
    source_hint = pipeline_input.source or pipeline_input.metadata.get("source_path")
    candidate = Path(str(source_hint)).stem if source_hint else pipeline_input.metadata.get("input_label", "cli_input")
    normalised = str(candidate).strip() or "cli_input"
    return normalised.replace(" ", "_")


def mask_key(key: str) -> str:
    if len(key) <= 6:
        return "*" * len(key)
    return f"{key[:3]}***{key[-2:]}"


__all__ = ["derive_base_name", "extract_latex_args", "mask_key"]
