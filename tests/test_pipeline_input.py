"""Tests for pipeline input utilities and metadata helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline_input import (
    AggregatedContentMetadata,
    EmptyPipelineInputError,
    FileSegmentMetadata,
    InvalidPipelineInputError,
    PipelineInput,
    ensure_pipeline_input,
    pipeline_input_from_aggregated_content,
)


def test_pipeline_input_instance_merges_metadata() -> None:
    """Ensure metadata is merged when the base object is supplied.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If merged metadata does not include values from both sources.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    base = PipelineInput(content="example", source="file.txt", metadata={"a": 1})
    result = ensure_pipeline_input(base, metadata={"b": 2})

    assert result.content == "example"
    assert result.source == "file.txt"
    assert result.metadata == {"a": 1, "b": 2}
    assert result is not base  # Metadata merge returns a new instance


def test_pipeline_input_requires_string_content() -> None:
    """Verify non-string content raises an ``InvalidPipelineInputError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If ``PipelineInput`` incorrectly accepts non-string content.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    with pytest.raises(InvalidPipelineInputError):
        PipelineInput(content=123)  # type: ignore[arg-type]


def test_ensure_pipeline_input_reads_file(tmp_path: Path) -> None:
    """Ensure content is read from disk when provided a file path.

    Args:
        tmp_path: Temporary directory provided by pytest for creating sample files.

    Returns:
        None.

    Raises:
        AssertionError: If the resulting pipeline input does not reflect file content.

    Side Effects:
        Creates a temporary file on disk that is cleaned up by pytest.

    Timeout:
        Not applicable.
    """

    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("hello world", encoding="utf-8")

    def reader(path: str) -> str:
        if path != str(sample_file):
            raise FileNotFoundError(path)
        return sample_file.read_text(encoding="utf-8")

    pipeline_input = ensure_pipeline_input(
        str(sample_file),
        read_file=reader,
        assume_path=True,
    )

    assert pipeline_input.content == "hello world"
    assert pipeline_input.source == str(sample_file)
    assert pipeline_input.metadata["input_type"] == "file"
    assert pipeline_input.metadata["source_path"] == str(sample_file)


def test_ensure_pipeline_input_file_read_error(tmp_path: Path) -> None:
    """Confirm file read errors propagate when fallback is disabled.

    Args:
        tmp_path: Temporary directory fixture used to construct a nonexistent path.

    Returns:
        None.

    Raises:
        AssertionError: If ``FileNotFoundError`` is not raised as expected.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    invalid_file = tmp_path / "does_not_exist.txt"

    def reader(path: str) -> str:
        raise FileNotFoundError(path)

    with pytest.raises(FileNotFoundError):
        ensure_pipeline_input(
            str(invalid_file),
            read_file=reader,
            assume_path=True,
        )


def test_ensure_pipeline_input_falls_back_to_literal(tmp_path: Path) -> None:
    """Verify literal fallback metadata is produced when enabled.

    Args:
        tmp_path: Temporary directory fixture used to provide a missing file path.

    Returns:
        None.

    Raises:
        AssertionError: If fallback metadata is not present.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    missing_path = tmp_path / "missing.txt"

    def reader(path: str) -> str:
        raise FileNotFoundError(path)

    pipeline_input = ensure_pipeline_input(
        str(missing_path),
        read_file=reader,
        assume_path=True,
        fallback_to_content=True,
        metadata={"extra": "meta"},
    )

    assert pipeline_input.content == str(missing_path)
    assert pipeline_input.metadata["fallback_reason"] == "file_not_found"
    assert pipeline_input.metadata["extra"] == "meta"


def test_ensure_pipeline_input_allows_empty_when_requested() -> None:
    """Ensure empty content is permitted when explicitly requested.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If whitespace-only content is rejected despite ``allow_empty``.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    pipeline_input = ensure_pipeline_input("   ", allow_empty=True)
    assert pipeline_input.content.strip() == ""


def test_ensure_pipeline_input_from_mapping() -> None:
    """Validate mapping inputs are normalised correctly.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If metadata or content is not transferred from the mapping.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    pipeline_input = ensure_pipeline_input({"content": "body", "source": "api", "priority": "high"})

    assert pipeline_input.content == "body"
    assert pipeline_input.source == "api"
    assert pipeline_input.metadata["priority"] == "high"


def test_ensure_pipeline_input_empty_text_raises() -> None:
    """Ensure empty text inputs raise an ``EmptyPipelineInputError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If empty content does not trigger ``EmptyPipelineInputError``.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    with pytest.raises(EmptyPipelineInputError):
        ensure_pipeline_input("", allow_empty=False)


def test_ensure_pipeline_input_invalid_mapping() -> None:
    """Confirm missing content keys in mappings raise ``InvalidPipelineInputError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If invalid mappings are accepted.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    with pytest.raises(InvalidPipelineInputError):
        ensure_pipeline_input({"source": "missing-content"})


def test_ensure_pipeline_input_uses_text_fallback_key() -> None:
    """Ensure ``text`` key is treated as content when present.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If metadata is not carried into the resulting instance.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    pipeline_input = ensure_pipeline_input({"text": 42, "meta": "value"})

    assert pipeline_input.content == "42"
    assert pipeline_input.metadata["meta"] == "value"


def test_ensure_pipeline_input_rejects_unknown_type() -> None:
    """Verify unsupported types raise ``InvalidPipelineInputError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If unsupported types do not trigger ``InvalidPipelineInputError``.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    with pytest.raises(InvalidPipelineInputError):
        ensure_pipeline_input(1234)


def test_file_segment_metadata_enforces_offsets() -> None:
    """Ensure invalid offset ordering raises ``ValueError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If ``ValueError`` is not raised for inverted offsets.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    with pytest.raises(ValueError):
        FileSegmentMetadata(
            path="data.md",
            start_offset=10,
            end_offset=5,
            byte_count=20,
            sha256_digest="deadbeef",
        )


def test_aggregated_metadata_from_segments_calculates_totals() -> None:
    """Aggregated metadata should compute byte totals and truncation flag.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If totals or truncation flags are not computed correctly.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    segments = (
        FileSegmentMetadata(
            path="intro.md",
            start_offset=0,
            end_offset=10,
            byte_count=10,
            sha256_digest="1" * 64,
        ),
        FileSegmentMetadata(
            path="methods.md",
            start_offset=10,
            end_offset=25,
            byte_count=15,
            sha256_digest="2" * 64,
            truncated=True,
        ),
    )

    metadata = AggregatedContentMetadata.from_segments(input_type="directory", segments=segments)

    assert metadata.total_bytes == 25
    assert metadata.truncated is True
    assert metadata.as_dict()["files"][0]["path"] == "intro.md"


def test_pipeline_input_from_aggregated_content_merges_metadata() -> None:
    """Ensure helper composes metadata dictionaries safely.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If metadata values are not merged as expected.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    aggregated = AggregatedContentMetadata(
        input_type="directory",
        files=[
            FileSegmentMetadata(
                path="chapter1.md",
                start_offset=0,
                end_offset=12,
                byte_count=12,
                sha256_digest="3" * 64,
            )
        ],
        total_bytes=12,
    )

    pipeline_input = pipeline_input_from_aggregated_content(
        content="chapter",
        source="/tmp/docs",
        aggregated_metadata=aggregated,
        extra_metadata={"notes": "ok"},
    )

    assert pipeline_input.content == "chapter"
    assert pipeline_input.source == "/tmp/docs"
    assert pipeline_input.metadata["notes"] == "ok"
    assert pipeline_input.metadata["input_type"] == "directory"
