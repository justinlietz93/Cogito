#!/usr/bin/env python3
"""
Tests for the DirectLatexGenerator class and its integration.
"""

import unittest
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing src modules
project_root = Path(__file__).resolve().parents[2]
import shutil # For cleaning up test output

sys.path.insert(0, str(project_root))

from src.latex.converters.direct_latex_generator import DirectLatexGenerator
from src.latex.formatter import LatexFormatter
from src.latex.config import LatexConfig

# Sample Markdown Content for testing
SAMPLE_MD_BASIC = """
# Title Test
Some *italic* and **bold** text.

## Section 1
Content here.

### Subsection 1.1
More content.

---

* List item 1
* List item 2

Special chars: % & $ _ # { } ~ ^ \\
Replacements: — – … ≈ ≠ °
"""

SAMPLE_MD_PEER_REVIEW = """
# Peer Review: Analysis of X

This is the summary.

## Major Points
1. Point one is **critical**.
2. Point two needs *revision*.

Special chars: % & $ _ # { } ~ ^ \\

> Blockquote text.

## Minor Points
* Suggestion A.
* Suggestion B with ≈ symbol.

---

Final thoughts.
"""

class TestDirectLatexGeneratorUnit(unittest.TestCase):
    """Unit tests specifically for the DirectLatexGenerator class."""

    def test_title_extraction(self):
        """Test title extraction from H1."""
        gen = DirectLatexGenerator("# My Title\nContent")
        self.assertEqual(gen.title, "My Title")

    def test_default_title(self):
        """Test default title when no H1 is present."""
        gen = DirectLatexGenerator("Just content, no title.")
        self.assertEqual(gen.title, "Scientific Peer Review")

    def test_heading_conversion(self):
        """Test conversion of markdown headings."""
        md = "# H1\n## H2\n### H3"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn(r"\section*{H1}", latex)
        self.assertIn(r"\subsection*{H2}", latex)
        self.assertIn(r"\subsubsection*{H3}", latex)

    def test_numbered_section_conversion(self):
        """Test conversion of numbered sections like '1. Section'."""
        md = "1. First Section\n2. Second Section"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        # Expecting these to become unnumbered subsections for simplicity
        self.assertIn(r"\subsection*{First Section}", latex)
        self.assertIn(r"\subsection*{Second Section}", latex)

    def test_emphasis_conversion(self):
        """Test conversion of *italic* and **bold**."""
        md = "Some *italic* and **bold** text."
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        # Note: Escaped asterisks become part of the regex
        self.assertIn(r"\textit{italic}", latex)
        self.assertIn(r"\textbf{bold}", latex)

    def test_list_conversion(self):
        """Test conversion of bullet lists."""
        md = "* Item 1\n* Item 2"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn(r"\begin{itemize}", latex)
        self.assertIn(r"  \item Item 1", latex)
        self.assertIn(r"  \item Item 2", latex)
        self.assertIn(r"\end{itemize}", latex)

    def test_horizontal_rule(self):
        """Test conversion of horizontal rules."""
        md = "Text\n---\nMore text"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn(r"\par\noindent\hrulefill\par", latex)

    def test_special_char_escaping(self):
        """Test escaping of special LaTeX characters."""
        md = "Chars: % & $ _ # { } ~ ^ \\"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn(r"Chars: \% \& \$ \_ \# \{ \} \textasciitilde{} \textasciicircum{} \textbackslash{}", latex)

    def test_character_replacements(self):
        """Test specific character replacements."""
        md = "Replacements: — – … ≈ ≠ °"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn("Replacements: -- - ... $\\approx$ $\\neq$ $^{\\circ}$", latex)
        self.assertNotIn("\\textbackslash{}$\\approx", latex)

    def test_blockquote_removal(self):
        """Test that blockquotes are converted to normal text."""
        md = "> This was a quote."
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn("This was a quote.", latex)
        self.assertNotIn("> This was a quote.", latex) # Ensure '>' is removed

    def test_code_block_handling(self):
        """Code blocks should be wrapped in verbatim environment."""
        md = """```
print('hi')
```
After block
"""
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn(r"\begin{verbatim}", latex)
        self.assertIn("print('hi')", latex)
        self.assertIn(r"\end{verbatim}", latex)
        self.assertIn("After block", latex)

    def test_consecutive_blank_lines_emit_single_paragraph(self):
        """Multiple blank lines should collapse into a single paragraph break."""
        md = "First paragraph.\n\n\nSecond paragraph."
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn("First paragraph.\n\\par\nSecond paragraph.", latex)

    def test_process_content_body_deduplicates_paragraph_markers(self):
        """Safety pass removes consecutive ``\\par`` entries from output."""
        gen = DirectLatexGenerator("Line one\nLine two")
        gen._process_line = lambda line: "\\par"  # type: ignore[assignment]

        body = gen._process_content_body()

        self.assertEqual(body, "\\par")

    def test_process_line_ignores_whitespace_only(self):
        """Whitespace-only lines return empty output during processing."""
        gen = DirectLatexGenerator("Content")
        self.assertEqual(gen._process_line("   "), "")

    def test_skips_raw_markdown_header_residue(self):
        """Lines that resemble escaped headers are dropped during processing."""
        md = "\\# Residual header"
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertNotIn("\\# Residual header", latex)

    def test_paragraph_breaks(self):
        """Test handling of blank lines for paragraph breaks."""
        md = "Paragraph 1.\n\nParagraph 2."
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        self.assertIn("Paragraph 1.\n\\par\nParagraph 2.", latex)

    def test_no_double_escaping(self):
        """Test that already escaped characters or commands aren't double-escaped."""
        md = r"Keep \textbf{bold} and \% percent."
        gen = DirectLatexGenerator(md)
        latex = gen.generate_latex_document()
        # Check that \textbf is not escaped further and \% remains \%
        self.assertIn(r"Keep \textbf{bold} and \% percent.", latex)
        self.assertNotIn(r"Keep \textbackslash{}textbf{bold}", latex)
        self.assertNotIn(r"and \\% percent", latex)


class TestDirectLatexIntegration(unittest.TestCase):
    """Integration tests for DirectLatexGenerator via LatexFormatter."""

    # ... (existing methods)

    def test_custom_preamble(self):
        """Test custom preamble functionality."""
        config = self.base_config.copy()
        config["direct_conversion"] = True
        config["custom_preamble"] = r"\newcommand{\customcommand}{\textbf{\1}}"

        formatter = LatexFormatter(config)
        tex_path, _ = formatter.format_document(
            original_content="Original",
            critique_report="Critique",
            peer_review=SAMPLE_MD_PEER_REVIEW
        )

        self.assertIsNotNone(tex_path)
        with open(tex_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn(r"\newcommand{\customcommand}{\textbf{\1}}", content)

    def setUp(self):
        """Set up a temporary output directory."""
        self.test_output_dir = Path("temp_latex_test_output")
        self.test_output_dir.mkdir(exist_ok=True)
        # Minimal config for testing
        self.base_config = {
            "output_dir": str(self.test_output_dir),
            "compile_pdf": False, # Don't attempt compilation in unit tests
            "keep_tex": True,
            "template_dir": "src/latex/templates", # Needed for standard path
            "main_template": "academic_paper.tex", # Needed for standard path
        }

    def tearDown(self):
        """Clean up the temporary output directory."""
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)

    def test_formatter_direct_conversion_enabled(self):
        """Test LatexFormatter uses DirectLatexGenerator when configured."""
        config = self.base_config.copy()
        config["direct_conversion"] = True

        formatter = LatexFormatter(config)
        tex_path, _ = formatter.format_document(
            original_content="Original",
            critique_report="Critique",
            peer_review=SAMPLE_MD_PEER_REVIEW
        )

        self.assertIsNotNone(tex_path)
        self.assertTrue(Path(tex_path).exists())
        self.assertTrue(Path(tex_path).name.startswith("critique_report_direct_"))

        with open(tex_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for markers of direct generation
        self.assertIn(r"\documentclass{article}", content) # Direct generator uses basic article
        self.assertIn(r"\section*{Peer Review: Analysis of X}", content)
        self.assertIn(r"\subsection*{Major Points}", content)
        self.assertIn(r"Point one is \textbf{critical}", content)
        self.assertIn(r"Point two needs \textit{revision}", content)
        self.assertIn(r"Special chars: \% \& \$ \_ \# \{ \} \textasciitilde{} \textasciicircum{} \textbackslash{}", content)
        self.assertIn("Blockquote text.", content) # Blockquote '>' removed
        self.assertIn(r"Suggestion B with $\approx$ symbol.", content)
        self.assertNotIn(r"\input{preamble.tex}", content) # Legacy include should not exist
        self.assertNotIn(r"\input{preamble}", content) # Direct generator includes preamble inline

    def test_formatter_direct_conversion_disabled(self):
        """Test LatexFormatter uses standard path when direct conversion is False."""
        config = self.base_config.copy()
        config["direct_conversion"] = False

        formatter = LatexFormatter(config)
        # Use peer review content, but direct conversion is off
        tex_path, _ = formatter.format_document(
            original_content="Original",
            critique_report="Critique",
            peer_review=SAMPLE_MD_PEER_REVIEW
        )

        self.assertIsNotNone(tex_path)
        self.assertTrue(Path(tex_path).exists())
        # Standard path doesn't add "_direct_"
        self.assertFalse(Path(tex_path).name.startswith("critique_report_direct_"))

        with open(tex_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for markers of standard template-based generation
        self.assertIn(r"\input{preamble}", content) # Standard templates use includes
        # Standard converter might handle headings differently (e.g., numbered)
        # or might use different commands depending on the template.
        # Just check that it doesn't look exactly like the direct output.
        self.assertNotIn(r"\section*{Peer Review: Analysis of X}", content)


    def test_formatter_direct_conversion_no_peer_review(self):
        """Test fallback to standard path if direct enabled but no peer review."""
        config = self.base_config.copy()
        config["direct_conversion"] = True # Enabled

        formatter = LatexFormatter(config)
        # NO peer_review provided
        tex_path, _ = formatter.format_document(
            original_content="Original",
            critique_report="Critique Report Content",
            peer_review=None
        )

        self.assertIsNotNone(tex_path)
        self.assertTrue(Path(tex_path).exists())
        # Should use standard path, no "_direct_"
        self.assertFalse(Path(tex_path).name.startswith("critique_report_direct_"))

        with open(tex_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for markers of standard template-based generation
        self.assertIn(r"\input{preamble}", content)


if __name__ == '__main__':
    unittest.main()
