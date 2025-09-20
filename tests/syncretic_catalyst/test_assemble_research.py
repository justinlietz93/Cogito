from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from syncretic_catalyst import assemble_research


def test_extract_title_parses_markdown_heading() -> None:
    content = "# 1. Syncretic Catalyst\nBody"

    title = assemble_research.extract_title(content)

    assert title == "1. Syncretic Catalyst"


def test_extract_title_returns_default_for_missing_heading() -> None:
    assert assemble_research.extract_title("No heading present") == "Untitled Section"


def test_extract_content_strips_markers(tmp_path: Path) -> None:
    source = tmp_path / "document.md"
    source.write_text(
        "=== File: doc/SECTION.md ===\nLine 1\n<CURRENT_CURSOR_POSITION>",
        encoding="utf-8",
    )

    result = assemble_research.extract_content(source)

    assert "=== File" not in result
    assert "<CURRENT_CURSOR_POSITION>" not in result
    assert "Line 1" in result


def test_extract_content_logs_error_on_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def failing_open(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", failing_open)

    content = assemble_research.extract_content(Path("missing.md"))

    captured = capsys.readouterr()
    assert "Error reading file" in captured.out
    assert content == ""


def test_main_builds_comprehensive_manual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doc_dir = tmp_path / "some_project" / "doc"
    doc_dir.mkdir(parents=True)
    (doc_dir / "CONTEXT_CONSTRAINTS.md").write_text(
        "=== File: doc/CONTEXT_CONSTRAINTS.md ===\n# 1. Context Constraints\nContent",
        encoding="utf-8",
    )
    (doc_dir / "DIVERGENT_SOLUTIONS.md").write_text(
        "# Divergent Solutions\nApproach details",
        encoding="utf-8",
    )
    (doc_dir / "DEEP_DIVE_MECHANISMS.md").write_text(
        "# Deep Dive Mechanisms\nMechanism notes",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assemble_research.main()

    captured = capsys.readouterr()
    manual_path = doc_dir / "COMPREHENSIVE_MANUAL.md"
    assert manual_path.exists()
    manual = manual_path.read_text(encoding="utf-8")

    assert manual.startswith("# Comprehensive Implementation Manual")
    assert "- 1. [Context Constraints](#1-context-constraints)" in manual
    assert "- 2. [Divergent Solutions](#2-divergent-solutions)" in manual
    assert "###### 1. Context Constraints" in manual
    assert "Approach details" in manual
    assert "Warning: File some_project/doc/ELABORATIONS.md not found" in captured.out
    assert "<CURRENT_CURSOR_POSITION>" not in manual
    assert "=== File" not in manual


def test_main_reports_write_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doc_dir = tmp_path / "some_project" / "doc"
    doc_dir.mkdir(parents=True)
    (doc_dir / "CONTEXT_CONSTRAINTS.md").write_text("# Context\nBody", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    real_open = builtins.open

    def failing_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        mode = args[0] if args else kwargs.get("mode", "r")
        if str(path).endswith("COMPREHENSIVE_MANUAL.md") and "w" in mode:
            raise OSError("disk full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)

    assemble_research.main()

    captured = capsys.readouterr()
    assert "Error writing target file" in captured.out
    assert not (doc_dir / "COMPREHENSIVE_MANUAL.md").exists()
