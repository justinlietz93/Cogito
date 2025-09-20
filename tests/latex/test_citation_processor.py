from __future__ import annotations

import builtins
import os
from pathlib import Path

from src.latex.processors.citation_processor import CitationProcessor


def test_citation_processor_generates_bibtex(tmp_path: Path) -> None:
    processor = CitationProcessor(output_dir=str(tmp_path))
    content = (
        "Introduction citing (Doe, 2020) and Smith (2021).\n"
        "---\n"
        "Doe, Jane. (2020). Insights into Science. Journal of Testing.\n"
        "Smith, John. (2021). Another Study."
    )

    processed = processor.process(content, context={"output_dir": str(tmp_path)})

    assert "\\cite{doe2020}" in processed
    assert "\\citeauthor{smith2021}" in processed

    bib_file = tmp_path / "bibliography.bib"
    assert bib_file.exists()
    text = bib_file.read_text(encoding="utf-8")
    assert "% Bibliography file copied from template" in text


def test_citation_processor_respects_context_flags(tmp_path: Path) -> None:
    processor = CitationProcessor(output_dir=str(tmp_path))
    content = "Findings from (Lee, 2022)."

    processed = processor.process(content, context={"generate_bibtex": False})
    assert "\\cite{lee2022}" in processed
    assert not list(tmp_path.glob("*.bib"))


def test_citation_processor_fallback_generation(tmp_path: Path, monkeypatch) -> None:
    processor = CitationProcessor(output_dir=str(tmp_path))
    processor._citations = {
        "doe2020": {
            "author": "Doe, Jane",
            "year": "2020",
            "title": "Fallback Entry",
            "type": "article",
            "publisher": "Press",
            "journal": "Journal",
            "volume": "12",
            "number": "3",
            "pages": "10-20",
            "url": "http://example.com",
        }
    }

    monkeypatch.setattr(
        "src.latex.processors.citation_processor.os.path.exists",
        lambda _path: False,
    )

    processor._generate_bibtex_file(str(tmp_path))

    generated = (tmp_path / "bibliography.bib").read_text(encoding="utf-8")
    assert "Bibliography file generated" in generated
    assert "@article{doe2020" in generated


def test_citation_processor_process_fallback_handles_template_failure(
    tmp_path: Path, monkeypatch
) -> None:
    processor = CitationProcessor(output_dir=str(tmp_path))
    content = (
        "Review referencing (Doe, 2020).\n"
        "---\n"
        "Doe, Jane. (2020). Fallback Entry. Publisher.\n"
    )

    module = __import__("src.latex.processors.citation_processor", fromlist=["os"])
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(module.__file__)),
        "templates",
        "bibliography.bib",
    )

    original_exists = module.os.path.exists
    monkeypatch.setattr(
        module.os.path,
        "exists",
        lambda path: True if path == template_path else original_exists(path),
    )

    original_open = builtins.open

    def flaky_open(path, mode="r", *args, **kwargs):  # type: ignore[override]
        if path == template_path and "r" in mode:
            raise OSError("cannot read template")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", flaky_open)

    processed = processor.process(content, context={"output_dir": str(tmp_path)})

    assert "\\cite{doe2020}" in processed

    bib_text = (tmp_path / "bibliography.bib").read_text(encoding="utf-8")
    assert "Bibliography file generated" in bib_text
    assert "@book{doe2020" in bib_text or "@misc{doe2020" in bib_text
    assert "publisher" in bib_text

    assert processor.name == "citation_processor"
    assert processor.description.startswith("Handles citations")
