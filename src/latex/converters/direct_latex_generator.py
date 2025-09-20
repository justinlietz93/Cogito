#!/usr/bin/env python3
"""
Direct LaTeX generator specifically for peer review files.

This module provides a DirectLatexGenerator class that converts peer review
content (assumed to be simple markdown) directly into a basic LaTeX document,
bypassing complex markdown parsing for robustness.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Match

logger = logging.getLogger(__name__)

class DirectLatexGenerator:
    """
    Generates LaTeX directly from simple markdown content, optimized for peer reviews.

    This class takes markdown text as input and applies minimal transformations
    to produce a compilable LaTeX document. It focuses on handling basic
    structures like headings, lists, and emphasis, while escaping special
    LaTeX characters.
    """

    # LaTeX special characters and their escaped versions
    LATEX_SPECIAL_CHARS: Dict[str, str] = {
        '%': r'\%',
        '&': r'\&',
        '$': r'\$',
        '_': r'\_',
        '#': r'\#',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}',
    }

    # Additional character replacements for common issues
    CHARACTER_REPLACEMENTS: List[Tuple[str, str]] = [
        ('─', '-'),        # Replace Unicode dash with ASCII dash
        ('…', '...'),      # Replace ellipsis with periods
        ('—', '--'),       # Replace em dash
        ('–', '-'),        # Replace en dash
        ('"', '"'),        # Replace smart quotes (left)
        ('"', '"'),        # Replace smart quotes (right)
        (''', "'"),        # Replace smart apostrophes (left)
        (''', "'"),        # Replace smart apostrophes (right)
        ('≈', '$\\approx$'),  # Replace approximate symbol
        ('≠', '$\\neq$'),   # Replace not equal symbol
        ('°', '$^{\\circ}$'),  # Replace degree symbol
        ('\t', '    '),    # Replace tabs with spaces
    ]

    def __init__(self, content: str, title: Optional[str] = None, custom_preamble: Optional[str] = None):
        """
        Initialize the generator with the markdown content.

        Args:
            content: The raw markdown content of the peer review.
            title: Optional override for the document title. If None, it will
                   attempt to extract from the first H1 heading.
        """
        self.raw_content: str = content
        self.title: str = title if title else self._extract_title(content)
        self.processed_lines: List[str] = []
        self.custom_preamble = custom_preamble or ""

    def _extract_title(self, content: str) -> str:
        """
        Extracts the title from the first H1 markdown heading.

        Args:
            content: The markdown content.

        Returns:
            The extracted title or a default title.
        """
        title_match = re.search(r'^# (.+?)$', content, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()
        logger.warning("Could not extract title from H1, using default.")
        return "Scientific Peer Review"

    def _escape_latex_chars(self, text: str) -> str:
        """Escape LaTeX reserved characters while preserving existing commands."""

        placeholders: Dict[str, str] = {}
        placeholder_prefix = "\uF000"
        placeholder_suffix = "\uF001"
        placeholder_index = 0

        def _store_placeholder(value: str) -> str:
            nonlocal placeholder_index
            placeholder = f"{placeholder_prefix}{placeholder_index}{placeholder_suffix}"
            placeholder_index += 1
            placeholders[placeholder] = value
            return placeholder

        def _protect(pattern: re.Pattern[str]) -> None:
            nonlocal text
            matches = list(pattern.finditer(text))
            for match in reversed(matches):
                start, end = match.span()
                original = match.group(0)
                placeholder = _store_placeholder(original)
                text = f"{text[:start]}{placeholder}{text[end:]}"

        # Preserve existing LaTeX commands (e.g. ``\textbf{}``) and explicit
        # escapes (e.g. ``\%``) so that we do not corrupt them during the
        # generic escaping phase below.
        command_pattern = re.compile(r'\\[a-zA-Z@]+(?:\[[^\]]*\])?(?:{[^{}]*})?')
        escaped_symbol_pattern = re.compile(r'\\[\\%&\$#{}_~^]')
        _protect(command_pattern)
        _protect(escaped_symbol_pattern)

        for old, new in self.CHARACTER_REPLACEMENTS:
            if any(marker in new for marker in ("\\", "$")):
                text = text.replace(old, _store_placeholder(new))
            else:
                text = text.replace(old, new)

        for char, escaped in self.LATEX_SPECIAL_CHARS.items():
            if char == '\\':
                continue
            if char in text:
                if any(marker in escaped for marker in ("\\", "$")):
                    text = text.replace(char, _store_placeholder(escaped))
                else:
                    text = text.replace(char, escaped)  # pragma: no cover - current mappings always use placeholders

        if '\\' in text:
            text = re.sub(
                r'(?<!\\)\\(?![a-zA-Z@])',
                lambda _: self.LATEX_SPECIAL_CHARS['\\'],
                text,
            )

        for placeholder, replacement in placeholders.items():
            text = text.replace(placeholder, replacement)
        return text

    def _apply_inline_formatting(self, text: str) -> tuple[str, Dict[str, str]]:
        """Convert basic markdown emphasis to LaTeX commands using placeholders."""

        emphasis_placeholders: Dict[str, str] = {}
        placeholder_prefix = "\uE000"
        placeholder_suffix = "\uE001"
        placeholder_index = 0

        def _store_emphasis(value: str) -> str:
            nonlocal placeholder_index
            placeholder = f"{placeholder_prefix}{placeholder_index}{placeholder_suffix}"
            placeholder_index += 1
            emphasis_placeholders[placeholder] = value
            return placeholder

        def _convert_bold(match: Match[str]) -> str:
            inner = self._escape_latex_chars(match.group(1))
            return _store_emphasis(f"\\textbf{{{inner}}}")

        def _convert_italic(match: Match[str]) -> str:
            inner = self._escape_latex_chars(match.group(1))
            return _store_emphasis(f"\\textit{{{inner}}}")

        text = re.sub(r'\*\*(.+?)\*\*', _convert_bold, text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', _convert_italic, text)

        return text, emphasis_placeholders

    def _process_line(self, line: str) -> str:
        """Process a single line of markdown content for LaTeX output."""

        stripped_line = line.strip()

        if not stripped_line:
            return ""

        def _finalise_inline(text: str, placeholders: Dict[str, str]) -> str:
            escaped = self._escape_latex_chars(text)
            for placeholder, replacement in placeholders.items():
                escaped = escaped.replace(placeholder, replacement)
            return escaped

        # Headings and numbered sections take precedence and should not include
        # additional formatting conversions.
        if stripped_line.startswith('# '):
            text, placeholders = self._apply_inline_formatting(stripped_line[2:].strip())
            return f"\\section*{{{_finalise_inline(text, placeholders)}}}"
        if stripped_line.startswith('## '):
            text, placeholders = self._apply_inline_formatting(stripped_line[3:].strip())
            return f"\\subsection*{{{_finalise_inline(text, placeholders)}}}"
        if stripped_line.startswith('### '):
            text, placeholders = self._apply_inline_formatting(stripped_line[4:].strip())
            return f"\\subsubsection*{{{_finalise_inline(text, placeholders)}}}"

        numbered_match = re.match(r'^(\d+)\.\s+(.+)$', stripped_line)
        if numbered_match:
            text, placeholders = self._apply_inline_formatting(numbered_match.group(2).strip())
            return f"\\subsection*{{{_finalise_inline(text, placeholders)}}}"

        if stripped_line in {'---', '***', '___', '───'}:
            return "\\par\\noindent\\hrulefill\\par"

        # Remove blockquote markers before further processing.
        content = re.sub(r'^>\s*', '', line)

        content, emphasis_placeholders = self._apply_inline_formatting(content)
        processed_line = _finalise_inline(content, emphasis_placeholders)

        if processed_line.strip().startswith('\\#'):
            logger.debug("Skipping potential raw markdown header remnant: %s", processed_line)
            return ""

        return processed_line

    def _process_content_body(self) -> str:
        """
        Processes the main body of the markdown content.

        Handles line-by-line processing and list environments.

        Returns:
            The processed body content as a single LaTeX string.
        """
        processed_lines: List[str] = []
        in_itemize = False
        in_code_block = False
        lines = self.raw_content.splitlines()

        for line in lines:
            stripped_line = line.strip()
            is_list_item = bool(re.match(r'^[*-]\s+', stripped_line))

            if stripped_line == '```':
                if not in_code_block:
                    processed_lines.append("\\begin{verbatim}")
                    in_code_block = True
                else:
                    processed_lines.append("\\end{verbatim}")
                    in_code_block = False
                continue

            if in_code_block:
                processed_lines.append(line)
                continue

            if not stripped_line:
                if in_itemize:
                    continue
                if processed_lines and processed_lines[-1] != "\\par":
                    processed_lines.append("\\par")
                continue

            if is_list_item:
                if not in_itemize:
                    processed_lines.append("\\begin{itemize}")
                    in_itemize = True
                item_text = stripped_line[2:].lstrip()
                processed_item = self._process_line(item_text)
                processed_lines.append(f"  \\item {processed_item}")
                continue

            if in_itemize:
                processed_lines.append("\\end{itemize}")
                in_itemize = False

            processed_line = self._process_line(line)
            if processed_line:
                processed_lines.append(processed_line)

        if in_itemize:
            processed_lines.append("\\end{itemize}")

        final_output: List[str] = []
        for entry in processed_lines:
            if entry == "\\par" and final_output and final_output[-1] == "\\par":
                continue
            final_output.append(entry)

        return '\n'.join(final_output)

    def generate_latex_document(self) -> str:
        """
        Generates the full LaTeX document string.

        Combines the preamble, title section, processed body, and closing tags.

        Returns:
            The complete LaTeX document as a string.
        """
        latex_body = self._process_content_body()
        custom_preamble = ""
        if self.custom_preamble.strip():
            custom_preamble = "\n% Custom preamble additions\n" + self.custom_preamble.strip() + "\n"

        # Basic LaTeX document structure
        document = f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath}} % For math symbols like approx, neq
\\usepackage{{geometry}} % For margins
\\geometry{{a4paper, margin=1in}}
\\usepackage{{hyperref}} % For clickable links (if any)
\\hypersetup{{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=cyan,
}}

{custom_preamble}

% Document metadata
\\title{{{self._escape_latex_chars(self.title)}}}
\\author{{Scientific Peer Review}} % Placeholder author
\\date{{\\today}}

\\begin{{document}}

\\maketitle

{latex_body}

\\end{{document}}
"""
        logger.info("Direct LaTeX document generated.")
        return document

# Example usage (for testing purposes if run directly)
if __name__ == '__main__':  # pragma: no cover - manual testing helper
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing DirectLatexGenerator...")

    # Sample markdown content
    sample_markdown = """
# Peer Review Report: Example Paper

This is a *sample* peer review report.

## Section 1: Summary

The paper presents an **interesting** approach.

Key points:
* Point 1: Strength A
* Point 2: Strength B

---

## Section 2: Major Concerns

1. Concern one about methodology.
2. Concern two regarding data interpretation.

### Subsection 2.1: Details

Further details on the methodology concern. Special chars: % & $ _ # { } ~ ^ \\

> This is a blockquote that should just become normal text.

Another paragraph with ≈ ≠ ° symbols.

## Section 3: Minor Suggestions

- Suggestion alpha.
- Suggestion beta.

Final thoughts.
"""

    generator = DirectLatexGenerator(sample_markdown)
    latex_output = generator.generate_latex_document()

    print("\n--- Generated LaTeX Output ---")
    print(latex_output)
    print("--- End Generated LaTeX Output ---\n")

    # You could add code here to write to a file and compile with pdflatex
    # import subprocess
    # output_path = "test_direct_output.tex"
    # with open(output_path, "w", encoding="utf-8") as f:
    #     f.write(latex_output)
    # print(f"LaTeX written to {output_path}")
    # try:
    #     subprocess.run(["pdflatex", "-interaction=nonstopmode", output_path], check=True)
    #     print("PDF compilation successful (test_direct_output.pdf)")
    # except Exception as e:
    #     print(f"PDF compilation failed: {e}")
