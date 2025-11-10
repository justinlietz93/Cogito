"""Tests for directory ingestion hardening in FileSystemContentRepositoryFactory.

Purpose:
- Prove that passing a directory path via FileInputRequest no longer triggers the
  "Input path is not a file" failure and instead coerces to directory aggregation.
- Validate the explicit DirectoryInputRequest path still aggregates multiple files.

External Dependencies:
- pytest (test runner)
- Python standard library: pathlib

Fallback Semantics:
- None in tests; failures raise assertions.

Timeout Strategy:
- Not applicable. Tests are local and file-system bound.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.application.critique.requests import DirectoryInputRequest, FileInputRequest
from src.infrastructure.io.file_repository import FileSystemContentRepositoryFactory


def _make_files(root: Path) -> list[Path]:
    """Create a small corpus of UTF-8 text files under the provided root directory."""
    files = []
    files.append((root / "a.txt").write_text("Alpha", encoding="utf-8") or root / "a.txt")
    files.append((root / "b.md").write_text("# Bravo", encoding="utf-8") or root / "b.md")
    return [root / "a.txt", root / "b.md"]


def test_create_for_file_coerces_directory(tmp_path: Path) -> None:
    """FileInputRequest(path=dir) should be coerced to directory aggregation.

    Validates hardening added in
    - [FileSystemContentRepositoryFactory.create_for_file()](src/infrastructure/io/file_repository.py:42)
    so that a directory path wrapped in FileInputRequest results in aggregated content
    rather than a FileNotFoundError ("Input path is not a file").
    """
    # Arrange: build a small INPUT-like tree with two readable files
    _make_files(tmp_path)

    factory = FileSystemContentRepositoryFactory()

    # Act: call create_for_file with a directory path; this should coerce to DirectoryContentRepository
    repo = factory.create_for_file(FileInputRequest(path=tmp_path))
    pipeline_input = repo.load_input()
    md = dict(pipeline_input.metadata or {})

    # Assert: aggregated directory semantics surfaced in metadata
    assert md.get("input_type") == "directory", "Expected directory aggregation after coercion"
    assert isinstance(md.get("files"), list) and len(md["files"]) == 2, "Expected two file segments in metadata"

    # The source_path should be the directory root for aggregated input
    additional = md.get("additional_info") or {}
    source_hint = additional.get("root") or md.get("source_path") or pipeline_input.source
    assert source_hint is not None and str(tmp_path) in str(source_hint)


def test_create_for_directory_aggregates(tmp_path: Path) -> None:
    """DirectoryInputRequest(root=dir) should aggregate multiple files into a PipelineInput."""
    # Arrange
    _make_files(tmp_path)

    factory = FileSystemContentRepositoryFactory()

    # Act
    repo = factory.create_for_directory(DirectoryInputRequest(root=tmp_path))
    pipeline_input = repo.load_input()
    md = dict(pipeline_input.metadata or {})

    # Assert
    assert md.get("input_type") == "directory"
    assert isinstance(md.get("files"), list) and len(md["files"]) == 2
    assert pipeline_input.content.strip() != "", "Aggregated content should not be empty"