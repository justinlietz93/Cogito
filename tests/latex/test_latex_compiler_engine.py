import logging
from types import SimpleNamespace

import pytest

from src.latex.utils import latex_compiler as compiler_module
from src.latex.utils import windows_engine_finder as finder_module
from src.latex.utils.latex_compiler import LatexCompiler
from src.latex.utils.windows_engine_finder import find_latex_engine_in_common_locations


def test_find_available_engine_checks_alternatives(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.latex_engine = "foo"
    compiler.custom_miktex_path = ""
    compiler.additional_search_paths = []

    attempts = []

    def fake_check(self, engine):
        attempts.append(engine)
        return engine == "xelatex"

    monkeypatch.setattr(LatexCompiler, "_check_engine_available", fake_check)
    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")

    available, engine = LatexCompiler._find_available_latex_engine(compiler)

    assert available is True
    assert engine == "xelatex"
    assert "xelatex" in attempts


def test_find_available_engine_returns_primary(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.latex_engine = "pdflatex"
    compiler.custom_miktex_path = ""
    compiler.additional_search_paths = []

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(LatexCompiler, "_check_engine_available", lambda self, engine: True)

    available, engine = LatexCompiler._find_available_latex_engine(compiler)

    assert available is True
    assert engine == "pdflatex"


def test_find_available_engine_reports_missing(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.latex_engine = "ghost"
    compiler.custom_miktex_path = ""
    compiler.additional_search_paths = []

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(LatexCompiler, "_check_engine_available", lambda self, engine: False)

    available, engine = LatexCompiler._find_available_latex_engine(compiler)

    assert available is False
    assert engine == "ghost"
    assert getattr(compiler, "_engine_path") is None


def test_find_available_engine_uses_windows_paths(monkeypatch, windows_env):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.latex_engine = "pdflatex"
    compiler.custom_miktex_path = ""
    compiler.additional_search_paths = []

    monkeypatch.setattr(LatexCompiler, "_check_engine_available", lambda self, engine: False)
    monkeypatch.setattr(
        compiler_module,
        "find_latex_engine_in_common_locations",
        lambda engine, custom, additional, logger: "C:/tex/pdflatex.exe",
    )

    available, engine = LatexCompiler._find_available_latex_engine(compiler)

    assert available is True
    assert engine == "pdflatex"
    assert compiler._engine_path == "C:/tex/pdflatex.exe"


def test_find_available_engine_windows_alternative(monkeypatch, windows_env):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.latex_engine = "pdflatex"
    compiler.custom_miktex_path = ""
    compiler.additional_search_paths = []

    monkeypatch.setattr(LatexCompiler, "_check_engine_available", lambda self, engine: False)

    def fake_find(engine, custom, additional, logger):
        return "C:/tex/xelatex.exe" if engine == "xelatex" else None

    monkeypatch.setattr(compiler_module, "find_latex_engine_in_common_locations", fake_find)

    available, engine = LatexCompiler._find_available_latex_engine(compiler)

    assert available is True
    assert engine == "xelatex"
    assert compiler._engine_path == "C:/tex/xelatex.exe"


def test_check_engine_available_handles_outcomes(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")

    results = iter(
        [
            SimpleNamespace(returncode=0, stdout="pdfTeX 1.0", stderr=""),
            SimpleNamespace(returncode=1, stdout="", stderr="missing"),
        ]
    )

    def fake_run(*args, **kwargs):
        return next(results)

    monkeypatch.setattr(compiler_module.subprocess, "run", fake_run)

    assert compiler._check_engine_available("pdflatex") is True
    assert compiler._check_engine_available("pdflatex") is False

    def raising_run(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(compiler_module.subprocess, "run", raising_run)

    assert compiler._check_engine_available("pdflatex") is False


def test_check_engine_available_windows_branch(monkeypatch, windows_env):
    compiler = LatexCompiler.__new__(LatexCompiler)

    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="TeX", stderr=""),
    )

    assert compiler._check_engine_available("pdflatex") is True


def test_run_latex_success_linux(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {"latex_args": ["-synctex=1"]}
    compiler.latex_engine = "pdflatex"

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="pdfTeX", stderr="")

    monkeypatch.setattr(compiler_module.subprocess, "run", fake_run)

    assert compiler._run_latex("doc.tex") is True
    assert captured["cmd"][0] == "pdflatex"
    assert "-synctex=1" in captured["cmd"]


def test_run_latex_failure_reports_errors(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {}
    compiler.latex_engine = "pdflatex"

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="fail"),
    )

    assert compiler._run_latex("doc.tex") is False


def test_run_latex_exception_returns_false(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {}
    compiler.latex_engine = "pdflatex"

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert compiler._run_latex("doc.tex") is False


def test_run_latex_windows_branch(monkeypatch, windows_env):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {}
    compiler.latex_engine = "pdflatex"

    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="pdfTeX", stderr=""),
    )

    assert compiler._run_latex("doc.tex") is True


def test_run_bibtex_prefers_engine_directory(tmp_path, monkeypatch, windows_env):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler._engine_path = str(tmp_path / "tex" / "pdflatex.exe")
    compiler.config = {}

    tex_dir = tmp_path / "tex"
    tex_dir.mkdir()
    bibtex_path = tex_dir / "bibtex.exe"
    bibtex_path.write_text("binary")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(compiler_module.subprocess, "run", fake_run)

    assert compiler._run_bibtex("paper") is True
    assert captured["cmd"][0] == str(bibtex_path)


def test_run_bibtex_linux_branch(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {}

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    assert compiler._run_bibtex("paper") is True


def test_run_bibtex_reports_failure(monkeypatch, windows_env):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {}

    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )

    assert compiler._run_bibtex("paper") is False


def test_run_bibtex_exception(monkeypatch):
    compiler = LatexCompiler.__new__(LatexCompiler)
    compiler.config = {}

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        compiler_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert compiler._run_bibtex("paper") is False


def test_find_latex_engine_in_common_locations_prefers_custom_path(
    tmp_path, monkeypatch, windows_env
):
    engine_dir = tmp_path / "miktex"
    engine_dir.mkdir()
    engine_path = engine_dir / "pdflatex.exe"
    engine_path.write_text("binary")

    monkeypatch.setattr(
        finder_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="MiKTeX", stderr=""),
    )

    result = find_latex_engine_in_common_locations(
        "pdflatex", str(engine_dir), [], logging.getLogger("test")
    )

    assert result == str(engine_path)


def test_find_latex_engine_in_common_locations_returns_none_for_non_windows(monkeypatch):
    monkeypatch.setattr(finder_module.platform, "system", lambda: "Linux")

    assert (
        find_latex_engine_in_common_locations(
            "pdflatex", "", [], logging.getLogger("test")
        )
        is None
    )


def test_find_latex_engine_in_common_locations_uses_additional_paths(
    tmp_path, monkeypatch, windows_env, caplog
):
    caplog.set_level(logging.INFO)

    additional_dir = tmp_path / "texlive"
    additional_dir.mkdir()
    engine_path = additional_dir / "pdflatex.exe"
    engine_path.write_text("binary")

    monkeypatch.setattr(
        finder_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="TeX", stderr=""),
    )

    result = find_latex_engine_in_common_locations(
        "pdflatex", str(tmp_path / "missing"), [str(additional_dir)], logging.getLogger("test")
    )

    assert result == str(engine_path)
    assert any("Custom MiKTeX path" in record.message for record in caplog.records)
    assert any("additional search paths" in record.message for record in caplog.records)


def test_find_latex_engine_in_common_locations_returns_none_when_not_found(
    monkeypatch, windows_env
):
    monkeypatch.setattr(finder_module.os.path, "exists", lambda path: False)
    monkeypatch.setattr(finder_module.os.path, "isfile", lambda path: False)

    result = find_latex_engine_in_common_locations(
        "pdflatex", "", [], logging.getLogger("test")
    )

    assert result is None


def test_engine_path_returns_none_on_version_failure(tmp_path, monkeypatch):
    engine_dir = tmp_path / "tex"
    engine_dir.mkdir()
    engine_file = engine_dir / "pdflatex.exe"
    engine_file.write_text("binary")

    monkeypatch.setattr(
        finder_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    assert finder_module._engine_path(str(engine_dir), "pdflatex") is None


def test_windows_startupinfo_returns_none():
    assert finder_module._windows_startupinfo() is None
