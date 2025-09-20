import logging
import os
import sys
from types import SimpleNamespace

import pytest

from src.latex import formatter as latex_formatter


@pytest.fixture
def formatter_stubs(monkeypatch):
    data = {
        "file_manager": None,
        "direct_generators": [],
        "compiler": None,
    }

    module = latex_formatter

    class DummyFileManager:
        def __init__(self, config):
            data["file_manager"] = self
            self.config = config
            self.write_calls = []
            self.read_calls = []
            self.render_calls = []
            self.copy_calls = []

        def write_output_file(self, filename, content):
            self.write_calls.append((filename, content))
            return os.path.join(self.config["output_dir"], filename)

        def read_template(self, name):
            self.read_calls.append(name)
            return f"TEMPLATE:{name}"

        def render_template(self, template, context):
            snapshot = {"template": template, "context": context.copy()}
            self.render_calls.append(snapshot)
            return "RENDERED_CONTENT"

        def copy_templates_to_output(self, templates):
            self.copy_calls.append(tuple(templates))

    class DummyDirectLatexGenerator:
        def __init__(self, content, title, custom_preamble):
            self.content = content
            self.title = title
            self.custom_preamble = custom_preamble
            data["direct_generators"].append(self)

        def generate_latex_document(self):
            return "DIRECT_LATEX"

    class DummyLatexCompiler:
        def __init__(self, config):
            self.config = config
            self.compile_calls = []
            self.forced_result = None
            data["compiler"] = self

        def compile_document(self, tex_path):
            self.compile_calls.append(tex_path)
            if self.forced_result is not None:
                return self.forced_result
            return True, f"{tex_path}.pdf"

    class DummyJargonProcessor:
        def __init__(self, *args, **kwargs):
            self.calls = []
            data["jargon_processor"] = self

        def process(self, content):
            self.calls.append(content)
            return f"J({content})"

    class DummyCitationProcessor:
        def __init__(self, *args, **kwargs):
            self.calls = []
            data["citation_processor"] = self

        def process(self, content):
            self.calls.append(content)
            return f"C({content})"

    class DummyMathFormatter:
        def __init__(self, *args, **kwargs):
            self.calls = []
            data["math_formatter"] = self

        def format(self, content):
            self.calls.append(content)
            return f"M({content})"

    class DummyMarkdownConverter:
        def __init__(self, *args, **kwargs):
            self.calls = []
            data["markdown_converter"] = self

        def convert(self, content):
            self.calls.append(content)
            return f"L({content})"

    monkeypatch.setattr(module, "FileManager", DummyFileManager)
    monkeypatch.setattr(module, "DirectLatexGenerator", DummyDirectLatexGenerator)
    monkeypatch.setattr(module, "LatexCompiler", DummyLatexCompiler)
    monkeypatch.setattr(module, "JargonProcessor", DummyJargonProcessor)
    monkeypatch.setattr(module, "CitationProcessor", DummyCitationProcessor)
    monkeypatch.setattr(module, "MathFormatter", DummyMathFormatter)
    monkeypatch.setattr(module, "MarkdownToLatexConverter", DummyMarkdownConverter)

    return data


def test_formatter_direct_conversion_generates_pdf(tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": True,
        "direct_conversion": True,
        "custom_preamble": "CUSTOM",
        "scientific_mode": True,
        "output_filename": "report",
    }

    formatter = latex_formatter.LatexFormatter(config)
    assert formatter.config.get("main_template") == "scientific_paper.tex"

    peer_review = "# Peer Review Title\n## Author: Example\nBody"

    tex_path, pdf_path = formatter.format_document(
        original_content="Original text",
        critique_report="Critique text",
        peer_review=peer_review,
    )

    assert os.path.basename(tex_path).startswith("report_direct_")
    assert pdf_path == f"{tex_path}.pdf"

    generators = formatter_stubs["direct_generators"]
    assert len(generators) == 1
    generator = generators[0]
    assert generator.content == peer_review
    assert generator.title == "Peer Review Title"
    assert generator.custom_preamble == "CUSTOM"

    compiler = formatter_stubs["compiler"]
    assert compiler.compile_calls == [tex_path]

    file_manager = formatter_stubs["file_manager"]
    assert file_manager.copy_calls == []
    assert file_manager.write_calls[0][0] == os.path.basename(tex_path)
    assert file_manager.write_calls[0][1] == "DIRECT_LATEX"


def test_formatter_falls_back_to_template_when_peer_review_missing(tmp_path, caplog, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": True,
        "include_bibliography": True,
        "output_filename": "report",
        "scientific_mode": False,
    }

    formatter = latex_formatter.LatexFormatter(config)
    assert formatter.config.get("main_template") == "philosophical_paper.tex"

    critique_report = "## Findings\nDetails."

    with caplog.at_level(logging.WARNING):
        tex_path, pdf_path = formatter.format_document(
            original_content="Original $content$",
            critique_report=critique_report,
            peer_review=None,
        )

    assert pdf_path is None
    assert "Falling back to standard method" in caplog.text

    file_manager = formatter_stubs["file_manager"]
    assert formatter_stubs["direct_generators"] == []
    assert file_manager.read_calls == ["philosophical_paper.tex"]
    assert file_manager.copy_calls == [("preamble.tex", "bibliography.bib")]

    render_context = file_manager.render_calls[0]["context"]
    expected_analysis = "L(M(C(J(## Findings\nDetails.))))"
    expected_review = "L(M(C(J(No peer review available for this analysis.))))"
    assert render_context["analysis_content"] == expected_analysis
    assert render_context["review_content"] == expected_review
    assert render_context["using_peer_review"] is False

    assert os.path.basename(tex_path).startswith("report_")
    assert "direct" not in os.path.basename(tex_path)

    markdown_calls = formatter_stubs["markdown_converter"].calls
    assert markdown_calls[0] == "M(C(J(## Findings\nDetails.)))"
    assert markdown_calls[1].startswith("M(C(J(No peer review available")



def test_prepare_context_prefers_peer_review_metadata(tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": False,
        "scientific_mode": True,
    }

    formatter = latex_formatter.LatexFormatter(config)
    peer_review = (
        "# Custom Title\n"
        "## Author: Jane Doe\n"
        "## Abstract\n"
        "This abstract.\n\n"
        "Body paragraph."
    )

    context = formatter._prepare_context(
        original_content="Original content",
        critique_report="Critique summary",
        peer_review=peer_review,
    )

    assert context["using_peer_review"] is True
    assert context["analysis_content"] == peer_review
    assert context["review_content"] == "Critique summary"
    assert context["author"] == "Jane Doe"
    assert context["title"] == "Custom Title"
    assert context["abstract"].startswith("This abstract.")
    assert "scientific methodology" in context["keywords"]


def test_formatter_reports_compile_failures(caplog, tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": True,
        "direct_conversion": True,
        "scientific_mode": True,
    }

    formatter = latex_formatter.LatexFormatter(config)
    formatter_stubs["compiler"].forced_result = (False, SimpleNamespace(stderr="missing engine"))

    with caplog.at_level(logging.ERROR):
        tex_path, pdf_path = formatter.format_document("content", "critique", peer_review="# Title\nBody")

    assert pdf_path is None
    assert "missing engine" in caplog.text


def test_standard_compilation_failure_logs_error(caplog, tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": True,
        "direct_conversion": False,
        "scientific_mode": False,
    }

    formatter = latex_formatter.LatexFormatter(config)
    formatter_stubs["compiler"].forced_result = (False, "compilation failed")

    with caplog.at_level(logging.ERROR):
        tex_path, pdf_path = formatter.format_document("content", "critique", peer_review=None)

    assert pdf_path is None
    assert "compilation failed" in caplog.text
    assert tex_path is not None


def test_formatter_uses_global_config_when_none(monkeypatch, tmp_path, formatter_stubs):
    latex_config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "scientific_mode": False,
    }

    monkeypatch.setattr(latex_formatter.config_loader, "get_latex_config", lambda: latex_config)

    formatter = latex_formatter.LatexFormatter()
    assert formatter.config.get("output_dir") == str(tmp_path)
    assert formatter.latex_compiler is None


def test_prepare_context_truncates_original_and_sets_flags(tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": False,
        "scientific_mode": False,
    }

    formatter = latex_formatter.LatexFormatter(config)
    long_content = "A" * 1200
    context = formatter._prepare_context(long_content, "critique")

    assert context["using_peer_review"] is False
    assert context["original_content"].endswith("...")
    assert len(context["original_content"]) <= 1000


def test_extract_abstract_handles_long_paragraph(tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": False,
    }

    formatter = latex_formatter.LatexFormatter(config)
    content = "Paragraph " + ("text " * 200)

    abstract = formatter._extract_abstract(content)
    assert abstract.endswith("...")

    default_abstract = formatter._extract_abstract("")
    assert "scientific critique" in default_abstract


def test_prepare_original_content_summary_truncates_and_formats(tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": False,
    }

    formatter = latex_formatter.LatexFormatter(config)
    summary = formatter._prepare_original_content_summary("B" * 1200)

    assert summary.lstrip().startswith("The analysis")
    assert "\\begin{quote}" in summary

    short_summary = formatter._prepare_original_content_summary("Short body")
    assert "Short body" in short_summary


def test_standard_compilation_success_logs_info(caplog, tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": True,
        "direct_conversion": False,
        "scientific_mode": False,
    }

    formatter = latex_formatter.LatexFormatter(config)

    with caplog.at_level(logging.INFO):
        tex_path, pdf_path = formatter.format_document("content", "critique")

    assert pdf_path == f"{tex_path}.pdf"
    assert "Standard PDF compilation successful" in caplog.text


def test_formatter_logs_completion_on_success(caplog, tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": False,
        "scientific_mode": False,
    }

    formatter = latex_formatter.LatexFormatter(config)

    with caplog.at_level(logging.INFO):
        tex_path, pdf_path = formatter.format_document("content", "critique")

    assert pdf_path is None
    assert f"LaTeX generation complete. Output TEX: {tex_path}" in caplog.text


def test_formatter_logs_when_no_tex_generated(caplog, tmp_path, formatter_stubs):
    config = {
        "output_dir": str(tmp_path),
        "template_dir": str(tmp_path / "templates"),
        "compile_pdf": False,
        "direct_conversion": False,
        "scientific_mode": False,
    }

    formatter = latex_formatter.LatexFormatter(config)
    file_manager = formatter_stubs["file_manager"]

    def _return_none(filename, content):
        file_manager.write_calls.append((filename, content))
        return None

    file_manager.write_output_file = _return_none  # type: ignore[assignment]

    with caplog.at_level(logging.ERROR):
        tex_path, pdf_path = formatter.format_document("content", "critique")

    assert tex_path is None
    assert pdf_path is None
    assert "No TEX file path generated" in caplog.text


def test_formatter_module_import_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import builtins

    original_import = builtins.__import__
    attempts = {"count": 0}

    def flaky_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[override]
        if name == "src.config_loader" and attempts["count"] == 0:
            attempts["count"] += 1
            raise ImportError("simulated import failure")
        return original_import(name, globals, locals, fromlist, level)

    expected_prefix = os.path.abspath(os.path.join(os.path.dirname(latex_formatter.__file__), "../../"))

    monkeypatch.setattr(builtins, "__import__", flaky_import)

    try:
        importlib.reload(latex_formatter)
        assert attempts["count"] == 1
    finally:
        monkeypatch.setattr(builtins, "__import__", original_import)
        importlib.reload(latex_formatter)

    assert expected_prefix in sys.path
    if sys.path and sys.path[0] == expected_prefix:
        sys.path.pop(0)
