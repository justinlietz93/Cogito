import pytest

from src.latex.utils import latex_compiler as compiler_module
from src.latex.utils import windows_engine_finder as finder_module
from src.latex.utils.latex_compiler import LatexCompiler


@pytest.fixture
def windows_env(monkeypatch):
    """Provide Windows-specific subprocess shims for tests that rely on STARTUPINFO."""

    class DummyStartupInfo:
        def __init__(self):
            self.dwFlags = 0

    monkeypatch.setattr(compiler_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(finder_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        compiler_module.subprocess, "STARTUPINFO", DummyStartupInfo, raising=False
    )
    monkeypatch.setattr(
        compiler_module.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False
    )
    monkeypatch.setattr(
        finder_module.subprocess, "STARTUPINFO", DummyStartupInfo, raising=False
    )
    monkeypatch.setattr(
        finder_module.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False
    )
    return DummyStartupInfo


@pytest.fixture
def compiler_factory(monkeypatch):
    def factory(**config):
        monkeypatch.setattr(
            LatexCompiler,
            "_find_available_latex_engine",
            lambda self: (True, config.get("latex_engine", "pdflatex")),
        )
        defaults = {
            "latex_engine": "pdflatex",
            "bibtex_run": False,
            "latex_runs": 1,
            "keep_intermediates": False,
            "miktex": {},
        }
        defaults.update(config)
        return LatexCompiler(config=defaults)

    return factory
