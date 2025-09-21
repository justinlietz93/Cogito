"""Infrastructure-level tests for file-system content repositories."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.application.critique.requests import DirectoryInputRequest, FileInputRequest
from src.infrastructure.io.directory_repository import DirectoryContentRepository
from src.infrastructure.io.file_repository import (
    FileSystemContentRepositoryFactory,
    SingleFileContentRepository,
)
from src.pipeline_input import PipelineInput, UnreadableFileError


def test_single_file_repository_loads_text(tmp_path: Path) -> None:
    """Ensure single-file repositories read text and emit metadata.

    Args:
        tmp_path: Temporary directory supplied by pytest for file creation.

    Returns:
        None.

    Raises:
        AssertionError: If the resulting metadata omits expected entries.

    Side Effects:
        Writes a temporary file to disk for repository ingestion.

    Timeout:
        Not applicable.
    """

    file_path = tmp_path / "note.md"
    file_path.write_text("hello", encoding="utf-8")

    repository = SingleFileContentRepository(FileInputRequest(path=file_path))
    result = repository.load_input()

    assert isinstance(result, PipelineInput)
    assert result.content == "hello"
    assert result.source == str(file_path.resolve())
    assert result.metadata["input_type"] == "file"
    assert result.metadata["files"][0]["path"] == "note.md"


def test_directory_repository_aggregates_with_labels(tmp_path: Path) -> None:
    """Aggregate multiple files while injecting heading labels.

    Args:
        tmp_path: Temporary directory used to build the sample repository.

    Returns:
        None.

    Raises:
        AssertionError: If ordering or metadata differ from expectations.

    Side Effects:
        Writes sample markdown files to the temporary directory.

    Timeout:
        Not applicable.
    """

    root = tmp_path / "docs"
    root.mkdir()
    (root / "b.md").write_text("second", encoding="utf-8")
    (root / "a.md").write_text("first", encoding="utf-8")

    request = DirectoryInputRequest(root=root, section_separator="\n---\n", label_sections=True)
    repository = DirectoryContentRepository(request)

    result = repository.load_input()

    assert "## a.md" in result.content
    assert "## b.md" in result.content
    assert result.metadata["input_type"] == "directory"
    assert [segment["path"] for segment in result.metadata["files"]] == ["a.md", "b.md"]
    info = result.metadata["additional_info"]
    assert info["processed_files"] == 2
    assert info["total_characters"] == len(result.content)


def test_directory_repository_respects_include_exclude(tmp_path: Path) -> None:
    """Ensure include and exclude glob patterns filter directory content.

    Args:
        tmp_path: Pytest temporary directory hosting the repository tree.

    Returns:
        None.

    Raises:
        AssertionError: If excluded files appear in the aggregated metadata.

    Side Effects:
        Writes multiple files to the temporary directory to exercise filtering.

    Timeout:
        Not applicable.
    """

    root = tmp_path / "docs"
    root.mkdir()
    (root / "keep.md").write_text("keep", encoding="utf-8")
    (root / "skip.txt").write_text("skip", encoding="utf-8")
    hidden = root / ".hidden.md"
    hidden.write_text("hidden", encoding="utf-8")

    request = DirectoryInputRequest(
        root=root,
        include=("**/*.md",),
        exclude=("**/.hidden.md",),
    )
    repository = DirectoryContentRepository(request)

    result = repository.load_input()

    assert "keep" in result.content
    assert "skip" not in result.content
    assert hidden.name not in [segment["path"] for segment in result.metadata["files"]]
    info = result.metadata["additional_info"]
    assert info["skipped_file_count"] == 0


def test_directory_repository_enforces_limits(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Verify max file and character caps update metadata and logs.

    Args:
        tmp_path: Temporary directory for test file creation.
        caplog: Pytest fixture capturing log output for assertions.

    Returns:
        None.

    Raises:
        AssertionError: If truncation metadata is absent when caps are reached.

    Side Effects:
        Writes multiple files to disk for aggregation.

    Timeout:
        Not applicable.
    """

    root = tmp_path / "docs"
    root.mkdir()
    for index in range(3):
        (root / f"file{index}.md").write_text(f"content-{index}", encoding="utf-8")

    request = DirectoryInputRequest(root=root, max_files=2, max_chars=20)
    repository = DirectoryContentRepository(request)

    with caplog.at_level("INFO"):
        result = repository.load_input()

    assert len(result.metadata["files"]) <= 2
    assert result.metadata["truncated"] is True
    assert result.metadata["truncation_reason"] in {"max_files", "max_chars"}
    info = result.metadata["additional_info"]
    assert set(info["truncation_events"]).issubset({"max_files", "max_chars"})
    assert info["processed_files"] <= 2
    assert "Directory aggregation summary" in caplog.text


def test_directory_repository_skips_non_text(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Skip binary files and record skips in metadata and logs.

    Args:
        tmp_path: Temporary directory for file creation.
        caplog: Pytest log capture fixture.

    Returns:
        None.

    Raises:
        AssertionError: If binary files appear in metadata or warning log missing.

    Side Effects:
        Writes both text and binary files to disk.

    Timeout:
        Not applicable.
    """

    root = tmp_path / "docs"
    root.mkdir()
    (root / "good.md").write_text("text", encoding="utf-8")
    (root / "bad.bin").write_bytes(b"\xff\xfe\x00")

    request = DirectoryInputRequest(root=root)
    repository = DirectoryContentRepository(request)

    with caplog.at_level("WARNING"):
        result = repository.load_input()

    assert "Skipping non-text file" in caplog.text
    assert [segment["path"] for segment in result.metadata["files"]] == ["good.md"]
    info = result.metadata["additional_info"]
    assert info["skipped_files"] == ("bad.bin",)
    assert info["skipped_file_count"] == 1




def test_directory_repository_missing_root_raises() -> None:
    """Ensure missing directories raise a clear FileNotFoundError."""

    request = DirectoryInputRequest(root=Path('does-not-exist'))
    repository = DirectoryContentRepository(request)

    with pytest.raises(FileNotFoundError):
        repository.load_input()



def test_directory_repository_raises_on_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise an explicit error when a file cannot be read."""

    root = tmp_path / 'docs'
    root.mkdir()
    unreadable = root / 'restricted.md'
    unreadable.write_text('secret', encoding='utf-8')

    request = DirectoryInputRequest(root=root)
    repository = DirectoryContentRepository(request)

    original_open = Path.open

    def patched_open(self: Path, *args, **kwargs):  # type: ignore[override]
        if self == unreadable:
            raise PermissionError('denied')
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', patched_open)

    with pytest.raises(UnreadableFileError) as exc_info:
        repository.load_input()

    assert 'restricted.md' in str(exc_info.value)

def test_directory_repository_ignores_symlink_traversal(tmp_path: Path) -> None:
    """Ensure symlinks pointing outside the root directory are ignored.

    Args:
        tmp_path: Temporary directory to construct the test repository.

    Returns:
        None.

    Raises:
        AssertionError: If the symlink target content is aggregated.

    Side Effects:
        Creates a symlink on disk referencing an external file.

    Timeout:
        Not applicable.
    """

    root = tmp_path / "docs"
    root.mkdir()
    external = tmp_path / "outside.md"
    external.write_text("outside", encoding="utf-8")
    inside = root / "inside.md"
    inside.write_text("inside", encoding="utf-8")
    symlink = root / "link.md"
    os.symlink(external, symlink)

    repository = DirectoryContentRepository(DirectoryInputRequest(root=root))
    result = repository.load_input()

    assert "outside" not in result.content
    paths = [segment["path"] for segment in result.metadata["files"]]
    assert "link.md" not in paths
    assert "inside.md" in paths


def test_directory_repository_rejects_order_entries_outside_root(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Warn when explicit order entries reference files outside the root.

    Args:
        tmp_path: Temporary directory for repository creation.
        caplog: Log capture fixture for verifying warnings.

    Returns:
        None.

    Raises:
        AssertionError: If traversal entries are honoured or no warning is logged.

    Side Effects:
        Creates files on disk for aggregation.

    Timeout:
        Not applicable.
    """

    root = tmp_path / "docs"
    root.mkdir()
    (root / "include.md").write_text("body", encoding="utf-8")
    (tmp_path / "outside.md").write_text("outside", encoding="utf-8")

    request = DirectoryInputRequest(root=root, order=("../outside.md", "include.md"))
    repository = DirectoryContentRepository(request)

    with caplog.at_level("WARNING"):
        result = repository.load_input()

    assert "Ordered file '../outside.md' not found" in caplog.text
    paths = [segment["path"] for segment in result.metadata["files"]]
    assert paths == ["include.md"]


def test_factory_creates_expected_repository(tmp_path: Path) -> None:
    """Factory should return repository implementations for files and directories.

    Args:
        tmp_path: Temporary directory used to construct request paths.

    Returns:
        None.

    Raises:
        AssertionError: If incorrect repository types are instantiated.

    Side Effects:
        None beyond object construction.

    Timeout:
        Not applicable.
    """

    factory = FileSystemContentRepositoryFactory()
    file_repo = factory.create_for_file(FileInputRequest(path=tmp_path / "one.md"))
    dir_repo = factory.create_for_directory(DirectoryInputRequest(root=tmp_path))

    assert isinstance(file_repo, SingleFileContentRepository)
    assert isinstance(dir_repo, DirectoryContentRepository)


__all__ = []
