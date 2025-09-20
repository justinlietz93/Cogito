import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.latex.utils import latex_compiler as compiler_module
from src.latex.utils.latex_compiler import LatexCompiler


def test_compile_document_success_removes_intermediates(tmp_path, compiler_factory, monkeypatch):
    compiler = compiler_factory()

    calls = []

    def fake_run_latex(self, tex_file):
        calls.append(tex_file)
        Path(tex_file).with_suffix(".pdf").write_text("pdf")
        Path(tex_file).with_suffix(".aux").write_text("aux")
        Path(tex_file).with_suffix(".log").write_text("log")
        return True

    monkeypatch.setattr(LatexCompiler, "_run_latex", fake_run_latex)

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}")

    success, output = compiler.compile_document(str(tex_path))

    assert success is True
    assert Path(output).is_file()
    assert calls == ["paper.tex"]
    assert not (tmp_path / "paper.aux").exists()
    assert not (tmp_path / "paper.log").exists()


def test_compile_document_reports_missing_pdf(tmp_path, compiler_factory, monkeypatch):
    compiler = compiler_factory(keep_intermediates=True)

    monkeypatch.setattr(LatexCompiler, "_run_latex", lambda self, tex_file: True)

    observed = []

    def fake_check(self, tex_dir, tex_name):
        observed.append((tex_dir, tex_name))

    monkeypatch.setattr(LatexCompiler, "_check_error_logs", fake_check)

    tex_path = tmp_path / "missing.tex"
    tex_path.write_text("content")

    success, message = compiler.compile_document(str(tex_path))

    assert success is False
    assert "PDF file not generated" in message
    assert observed == [(str(tmp_path), "missing")]


def test_compile_document_requires_available_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(
        LatexCompiler, "_find_available_latex_engine", lambda self: (False, "pdflatex")
    )
    compiler = LatexCompiler(config={"latex_engine": "pdflatex", "miktex": {}})

    success, message = compiler.compile_document(str(tmp_path / "file.tex"))

    assert success is False
    assert "not available" in message


def test_compile_document_missing_source_file(tmp_path, compiler_factory):
    compiler = compiler_factory()

    success, message = compiler.compile_document(str(tmp_path / "ghost.tex"))

    assert success is False
    assert "source file not found" in message


def test_compile_document_latex_failure(tmp_path, compiler_factory, monkeypatch):
    compiler = compiler_factory()

    monkeypatch.setattr(LatexCompiler, "_run_latex", lambda self, tex_file: False)

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("content")

    success, message = compiler.compile_document(str(tex_path))

    assert success is False
    assert "compilation failed" in message


def test_compile_document_bibtex_failure(tmp_path, compiler_factory, monkeypatch):
    compiler = compiler_factory(bibtex_run=True, latex_runs=1)

    def fake_run_latex(self, tex_file):
        Path(tex_file).with_suffix(".aux").write_text("aux")
        Path(tex_file).with_suffix(".pdf").write_text("pdf")
        return True

    monkeypatch.setattr(LatexCompiler, "_run_latex", fake_run_latex)
    monkeypatch.setattr(LatexCompiler, "_run_bibtex", lambda self, name: False)

    tex_path = tmp_path / "bib.tex"
    tex_path.write_text("content")

    success, message = compiler.compile_document(str(tex_path))

    assert success is False
    assert "BibTeX" in message


def test_compile_document_additional_run_failure(tmp_path, compiler_factory, monkeypatch):
    compiler = compiler_factory(latex_runs=2)

    call_state = {"first": True}

    def fake_run_latex(self, tex_file):
        if call_state["first"]:
            call_state["first"] = False
            return True
        return False

    monkeypatch.setattr(LatexCompiler, "_run_latex", fake_run_latex)

    tex_path = tmp_path / "extra.tex"
    tex_path.write_text("content")

    success, message = compiler.compile_document(str(tex_path))

    assert success is False
    assert "pass 2" in message


def test_compile_document_handles_exception(tmp_path, compiler_factory, monkeypatch):
    compiler = compiler_factory()

    def raising_run(self, tex_file):
        raise RuntimeError("boom")

    monkeypatch.setattr(LatexCompiler, "_run_latex", raising_run)

    tex_path = tmp_path / "raise.tex"
    tex_path.write_text("content")

    success, message = compiler.compile_document(str(tex_path))

    assert success is False
    assert "Exception during LaTeX compilation" in message


def test_clean_intermediates_removes_files(tmp_path):
    compiler = LatexCompiler.__new__(LatexCompiler)

    for extension in [".aux", ".log", ".out"]:
        target = tmp_path / f"doc{extension}"
        target.write_text("data")
        assert target.exists()

    compiler._clean_intermediates(str(tmp_path), "doc")

    for extension in [".aux", ".log", ".out"]:
        assert not (tmp_path / f"doc{extension}").exists()


def test_clean_intermediates_warns_on_error(tmp_path, monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)

    target = tmp_path / "doc.aux"
    target.write_text("data")

    def fake_remove(path):
        raise OSError("denied")

    monkeypatch.setattr(os, "remove", fake_remove)

    compiler._clean_intermediates(str(tmp_path), "doc")


def test_check_error_logs_reports_entries(tmp_path, capsys):
    compiler = LatexCompiler.__new__(LatexCompiler)
    log_path = tmp_path / "doc.log"
    log_path.write_text("! Emergency stop\nerror: missing file\n")

    compiler._check_error_logs(str(tmp_path), "doc")

    captured = capsys.readouterr()
    assert "Emergency stop" in captured.out
    assert "missing file" in captured.out


def test_check_error_logs_handles_read_error(tmp_path, monkeypatch, capsys):
    compiler = LatexCompiler.__new__(LatexCompiler)
    log_path = tmp_path / "doc.log"
    log_path.write_text("content")

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("denied")))

    compiler._check_error_logs(str(tmp_path), "doc")

    captured = capsys.readouterr()
    assert "Error reading log file" in captured.out


def test_check_error_logs_reports_no_specific_errors(tmp_path, capsys):
    compiler = LatexCompiler.__new__(LatexCompiler)
    log_path = tmp_path / "doc.log"
    log_path.write_text("This is only informational.\n")

    compiler._check_error_logs(str(tmp_path), "doc")

    captured = capsys.readouterr()
    assert "No specific errors" in captured.out


def test_check_error_logs_handles_missing_file(tmp_path, capsys):
    compiler = LatexCompiler.__new__(LatexCompiler)

    compiler._check_error_logs(str(tmp_path), "missing")

    captured = capsys.readouterr()
    assert "No log file" in captured.out


def test_latex_compiler_uses_default_config(monkeypatch):
    sample_config = {
        "latex_engine": "pdflatex",
        "bibtex_run": False,
        "latex_runs": 1,
        "keep_intermediates": True,
        "miktex": {},
    }

    monkeypatch.setattr(
        LatexCompiler,
        "_find_available_latex_engine",
        lambda self: (True, sample_config["latex_engine"]),
    )
    monkeypatch.setattr(
        compiler_module,
        "config_loader",
        SimpleNamespace(get_latex_config=lambda: sample_config),
    )

    compiler = LatexCompiler()

    assert compiler.config is sample_config
    assert compiler.keep_intermediates is True
