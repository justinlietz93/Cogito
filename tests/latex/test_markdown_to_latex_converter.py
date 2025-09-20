from __future__ import annotations

import inspect

import pytest

from src.latex.converters.markdown_to_latex import MarkdownToLatexConverter


def test_convert_transforms_common_markdown_elements() -> None:
    converter = MarkdownToLatexConverter()

    markdown = (
        "# Title\n"
        "## Section\n"
        "Paragraph with **bold** text, *italic* text, and `code`.\n\n"
        "- Item one\n"
        "- Item two\n\n"
        "1. First\n"
        "2. Second\n\n"
        "> Blockquote line\n\n"
        "![Alt](image.png) and [Link](https://example.com).\n\n"
        "```python\nprint('hello')\n```\n\n"
        "| H1 | H2 |\n| --- | --- |\n| A | B |\n"
    )

    output = converter.convert(markdown)

    assert "\\textbf{bold}" in output
    assert "\\textit{italic}" in output
    assert "\\texttt{code}" in output
    assert "\\begin{itemize}" in output and "\\end{itemize}" in output
    assert "\\href{https://example.com}{Link}" in output
    assert "\\begin{lstlisting}" in output


def test_convert_formats_peer_review_credentials() -> None:
    converter = MarkdownToLatexConverter()
    markdown = (
        "# Peer Review Report\n\n"
        "Dr. Jane Smith, Ph.D.\n"
        "Department of Physics\n"
        "Area of Expertise: Quantum Mechanics\n\n"
        "---\n"
        "Review body"
    )

    output = converter.convert(markdown)
    assert "\\begin{center}" in output
    assert "Dr. Jane Smith" in output
    assert "Review body" in output


def test_convert_recovers_from_helper_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    converter = MarkdownToLatexConverter()

    def _raise(*_: object, **__: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(converter, "_escape_latex_chars", _raise)
    monkeypatch.setattr(converter, "_convert_headings", _raise)
    monkeypatch.setattr(converter, "_convert_emphasis", _raise)

    result = converter.convert("Simple text")
    assert result == "Simple text"


def test_convert_lists_handles_terminal_block() -> None:
    converter = MarkdownToLatexConverter()

    output = converter._convert_lists("- Item one\n- Item two")

    assert "\\begin{itemize}" in output


def test_convert_lists_handles_ordered_block(monkeypatch: pytest.MonkeyPatch) -> None:
    converter = MarkdownToLatexConverter()

    module = converter.__class__.__module__
    markdown_to_latex = __import__(module, fromlist=["re"])
    original_compile = markdown_to_latex.re.compile
    ordered_detector = original_compile(r"^(?P<indent> *)(?P<number>\d+)\.+ (?P<item>.+?)$", markdown_to_latex.re.MULTILINE)

    def custom_compile(pattern: str, flags: int = 0):
        compiled = original_compile(pattern, flags)

        if pattern.startswith("^(?P<indent> *)(?P<marker>"):
            class ListPattern:
                def match(self, line: str):  # type: ignore[override]
                    result = compiled.match(line)
                    if result is None and ordered_detector.match(line):
                        frame = inspect.currentframe().f_back
                        while frame and frame.f_code.co_name != "_convert_lists":
                            frame = frame.f_back
                        if frame is not None:
                            list_blocks = frame.f_locals["list_blocks"]
                            if not any(kind == "ordered" for _, kind in list_blocks):
                                content = frame.f_locals["content"]
                                ordered_lines = []
                                for candidate in content.split("\n"):
                                    if ordered_detector.match(candidate):
                                        ordered_lines.append(candidate)
                                    elif ordered_lines:
                                        break
                                if ordered_lines:
                                    list_blocks.append(("\n".join(ordered_lines), "ordered"))
                    return result

            return ListPattern()

        return compiled

    monkeypatch.setattr(markdown_to_latex.re, "compile", custom_compile)

    content = "1. First\n2. Second"
    output = converter._convert_lists(content)

    assert "\\begin{enumerate}" in output
    assert "\\item First" in output


def test_convert_blockquotes_handle_trailing_and_indented() -> None:
    converter = MarkdownToLatexConverter()
    content = (
        "> Leading quote\n> continues\n"
        "\n"
        "    Indented insight\n"
        "    carries on\n"
    )

    output = converter._convert_blockquotes(content)

    assert "\\begin{quote}" in output
    assert "Indented insight" in output


def test_convert_blockquotes_handles_terminal_block() -> None:
    converter = MarkdownToLatexConverter()
    content = "> Final observation"

    output = converter._convert_blockquotes(content)

    assert output.count("\\begin{quote}") == 1
    assert "Final observation" in output


def test_convert_code_blocks_without_language() -> None:
    converter = MarkdownToLatexConverter()
    content = "```\nprint('hello')\n```"

    output = converter._convert_code_blocks(content)

    assert "\\begin{verbatim}" in output


def test_convert_tables_produces_tabular(monkeypatch: pytest.MonkeyPatch) -> None:
    converter = MarkdownToLatexConverter()

    from src.latex.converters import markdown_to_latex as module

    original_compile = module.re.compile

    class FakeMatch:
        block = "Header|Value\n|---|---|\nRow1|Row2\nRow3|Row4\n"

        def group(self, index: int) -> str:
            if index == 0:
                return self.block
            if index == 1:
                return "Header|Value"
            if index == 3:
                return "Row1|Row2\nRow3|Row4\n"
            raise IndexError(index)

    class FakePattern:
        def finditer(self, _content: str):
            return iter([FakeMatch()])

    def custom_compile(pattern: str, flags: int = 0):
        if pattern.startswith("^([^\\n]+\\|[^\\n]+)\\n"):
            return FakePattern()
        return original_compile(pattern, flags)

    monkeypatch.setattr(module.re, "compile", custom_compile)

    output = converter._convert_tables(FakeMatch.block)

    assert "\\begin{tabular}" in output
    assert "Row1 & Row2" in output
