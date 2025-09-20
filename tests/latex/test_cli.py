import argparse
import logging
import os
import sys
from argparse import Namespace
from typing import Optional

import pytest

from src.latex.cli import add_latex_arguments, handle_latex_output


def _build_args(
    *,
    latex: bool,
    output_dir: str,
    compile_pdf: bool,
    scientific_level: str,
    direct: bool,
) -> Namespace:
    return Namespace(
        latex=latex,
        latex_output_dir=output_dir,
        latex_compile=compile_pdf,
        latex_scientific_level=scientific_level,
        direct_latex=direct,
    )


def test_add_latex_arguments_registers_expected_flags() -> None:
    parser = argparse.ArgumentParser()
    parser = add_latex_arguments(parser)

    parsed = parser.parse_args(
        [
            "--latex",
            "--latex-output-dir",
            "custom",
            "--latex-compile",
            "--latex-scientific-level",
            "medium",
            "--direct-latex",
        ]
    )

    assert parsed.latex is True
    assert parsed.latex_output_dir == "custom"
    assert parsed.latex_compile is True
    assert parsed.latex_scientific_level == "medium"
    assert parsed.direct_latex is True

    defaults = parser.parse_args([])
    assert defaults.latex is False
    assert defaults.latex_output_dir == "latex_output"
    assert defaults.latex_compile is False
    assert defaults.latex_scientific_level == "high"
    assert defaults.direct_latex is False


def test_handle_latex_output_returns_early_when_flag_disabled(tmp_path) -> None:
    args = _build_args(
        latex=False,
        output_dir=str(tmp_path / "out"),
        compile_pdf=False,
        scientific_level="high",
        direct=False,
    )

    success, tex_path, pdf_path = handle_latex_output(
        args,
        original_content="content",
        critique_report="report",
    )

    assert success is False
    assert tex_path is None
    assert pdf_path is None


def test_handle_latex_output_applies_cli_overrides(monkeypatch, tmp_path) -> None:
    from src.latex import cli as cli_module

    yaml_config = {
        "output_dir": "yaml_output",
        "compile_pdf": False,
        "scientific_objectivity_level": "medium",
        "scientific_mode": False,
        "direct_conversion": False,
    }

    monkeypatch.setattr(
        cli_module.config_loader,
        "get_latex_config",
        lambda: yaml_config,
    )

    captured_config: Optional[dict] = None

    def fake_format(
        original: str,
        critique: str,
        peer: Optional[str],
        config: dict,
    ):
        nonlocal captured_config
        captured_config = {
            "original": original,
            "critique": critique,
            "peer": peer,
            "config": config.copy(),
        }
        return str(tmp_path / "generated.tex"), str(tmp_path / "generated.pdf")

    monkeypatch.setattr(cli_module, "format_as_latex", fake_format)

    args = _build_args(
        latex=True,
        output_dir=str(tmp_path / "cli_output"),
        compile_pdf=True,
        scientific_level="low",
        direct=True,
    )

    success, tex_path, pdf_path = handle_latex_output(
        args,
        original_content="original",
        critique_report="critique",
        peer_review="peer",
        scientific_mode=True,
    )

    assert success is True
    assert tex_path.endswith("generated.tex")
    assert pdf_path.endswith("generated.pdf")

    assert captured_config is not None
    assert captured_config["original"] == "original"
    assert captured_config["critique"] == "critique"
    assert captured_config["peer"] == "peer"

    cli_config = captured_config["config"]
    assert cli_config["output_dir"] == str(tmp_path / "cli_output")
    assert cli_config["compile_pdf"] is True
    assert cli_config["scientific_objectivity_level"] == "low"
    assert cli_config["scientific_mode"] is True
    assert cli_config["direct_conversion"] is True


def test_handle_latex_output_uses_empty_loader_config(monkeypatch, tmp_path) -> None:
    from src.latex import cli as cli_module

    monkeypatch.setattr(cli_module.config_loader, "get_latex_config", lambda: {})

    captured: dict[str, object] = {}

    def fake_format(original: str, critique: str, peer: Optional[str], config: dict):
        captured.update({
            "original": original,
            "critique": critique,
            "peer": peer,
            "config": config.copy(),
        })
        return str(tmp_path / "doc.tex"), None

    monkeypatch.setattr(cli_module, "format_as_latex", fake_format)

    args = _build_args(
        latex=True,
        output_dir=str(tmp_path / "out"),
        compile_pdf=False,
        scientific_level="high",
        direct=False,
    )

    success, tex_path, pdf_path = handle_latex_output(
        args,
        original_content="body",
        critique_report="critique",
    )

    assert success is True
    assert pdf_path is None
    assert tex_path.endswith("doc.tex")

    config = captured["config"]  # type: ignore[index]
    assert config["output_dir"] == str(tmp_path / "out")
    assert config["compile_pdf"] is False
    assert config["scientific_objectivity_level"] == "high"
    assert config["direct_conversion"] is False


def test_handle_latex_output_logs_and_handles_errors(monkeypatch, tmp_path, caplog) -> None:
    from src.latex import cli as cli_module

    yaml_config = {
        "output_dir": "yaml_output",
        "compile_pdf": False,
        "scientific_objectivity_level": "high",
        "scientific_mode": False,
        "direct_conversion": False,
    }

    monkeypatch.setattr(
        cli_module.config_loader,
        "get_latex_config",
        lambda: yaml_config,
    )

    def raising_format(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "format_as_latex", raising_format)

    args = _build_args(
        latex=True,
        output_dir=str(tmp_path / "cli_output"),
        compile_pdf=False,
        scientific_level="high",
        direct=False,
    )

    with caplog.at_level(logging.ERROR):
        success, tex_path, pdf_path = handle_latex_output(
            args,
            original_content="original",
            critique_report="critique",
        )

    assert success is False
    assert tex_path is None
    assert pdf_path is None
    assert "Failed to generate LaTeX document" in caplog.text


def test_cli_module_import_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import builtins
    from src.latex import cli as cli_module

    original_import = builtins.__import__
    attempts = {"count": 0}

    def flaky_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[override]
        if name == "src.config_loader" and attempts["count"] == 0:
            attempts["count"] += 1
            raise ImportError("simulated path issue")
        return original_import(name, globals, locals, fromlist, level)

    expected_prefix = os.path.abspath(os.path.join(os.path.dirname(cli_module.__file__), "../../"))

    monkeypatch.setattr(builtins, "__import__", flaky_import)

    try:
        importlib.reload(cli_module)
        assert attempts["count"] == 1
    finally:
        monkeypatch.setattr(builtins, "__import__", original_import)
        importlib.reload(cli_module)

    assert expected_prefix in sys.path
    if sys.path and sys.path[0] == expected_prefix:
        sys.path.pop(0)
