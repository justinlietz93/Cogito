"""Unit tests for CLI utility helpers."""

from __future__ import annotations

from types import SimpleNamespace

from src.pipeline_input import PipelineInput
from src.presentation.cli import utils


def test_extract_latex_args_returns_none_when_disabled() -> None:
    args = SimpleNamespace(latex=False)

    assert utils.extract_latex_args(args) is None


def test_extract_latex_args_collects_flags() -> None:
    args = SimpleNamespace(
        latex=True,
        latex_compile=True,
        latex_output_dir="out",
        latex_scientific_level="low",
        direct_latex=True,
    )

    result = utils.extract_latex_args(args)

    assert result.latex_compile is True
    assert result.latex_output_dir == "out"
    assert result.latex_scientific_level == "low"
    assert result.direct_latex is True


def test_derive_base_name_prefers_source_path() -> None:
    pipeline_input = PipelineInput(content="body", source="~/notes/report.md")

    assert utils.derive_base_name(pipeline_input) == "report"


def test_derive_base_name_falls_back_to_label() -> None:
    pipeline_input = PipelineInput(content="body", metadata={"input_label": "  Example Title  "})

    assert utils.derive_base_name(pipeline_input) == "Example_Title"


def test_derive_base_name_handles_directory_source() -> None:
    pipeline_input = PipelineInput(content="body", source="/tmp/my_project")

    assert utils.derive_base_name(pipeline_input) == "my_project"


def test_derive_base_name_strips_critique_suffix() -> None:
    pipeline_input = PipelineInput(content="body", source="./analysis_critique.md")

    assert utils.derive_base_name(pipeline_input) == "analysis"


def test_mask_key_handles_short_and_long_values() -> None:
    assert utils.mask_key("abc") == "***"
    assert utils.mask_key("abcdefghi") == "abc***hi"
