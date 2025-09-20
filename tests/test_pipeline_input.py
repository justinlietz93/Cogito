import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pipeline_input import (
    EmptyPipelineInputError,
    InvalidPipelineInputError,
    PipelineInput,
    ensure_pipeline_input,
)


def test_pipeline_input_instance_merges_metadata():
    base = PipelineInput(content="example", source="file.txt", metadata={"a": 1})
    result = ensure_pipeline_input(base, metadata={"b": 2})

    assert result.content == "example"
    assert result.source == "file.txt"
    assert result.metadata == {"a": 1, "b": 2}
    assert result is not base  # Metadata merge returns a new instance


def test_pipeline_input_requires_string_content():
    with pytest.raises(InvalidPipelineInputError):
        PipelineInput(content=123)  # type: ignore[arg-type]


def test_ensure_pipeline_input_reads_file(tmp_path):
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


def test_ensure_pipeline_input_file_read_error(tmp_path):
    invalid_file = tmp_path / "does_not_exist.txt"

    def reader(path: str) -> str:
        raise FileNotFoundError(path)

    with pytest.raises(FileNotFoundError):
        ensure_pipeline_input(
            str(invalid_file),
            read_file=reader,
            assume_path=True,
        )


def test_ensure_pipeline_input_falls_back_to_literal(tmp_path):
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


def test_ensure_pipeline_input_allows_empty_when_requested():
    pipeline_input = ensure_pipeline_input("   ", allow_empty=True)
    assert pipeline_input.content.strip() == ""


def test_ensure_pipeline_input_from_mapping():
    pipeline_input = ensure_pipeline_input({"content": "body", "source": "api", "priority": "high"})

    assert pipeline_input.content == "body"
    assert pipeline_input.source == "api"
    assert pipeline_input.metadata["priority"] == "high"


def test_ensure_pipeline_input_empty_text_raises():
    with pytest.raises(EmptyPipelineInputError):
        ensure_pipeline_input("", allow_empty=False)


def test_ensure_pipeline_input_invalid_mapping():
    with pytest.raises(InvalidPipelineInputError):
        ensure_pipeline_input({"source": "missing-content"})


def test_ensure_pipeline_input_uses_text_fallback_key():
    pipeline_input = ensure_pipeline_input({"text": 42, "meta": "value"})

    assert pipeline_input.content == "42"
    assert pipeline_input.metadata["meta"] == "value"


def test_ensure_pipeline_input_rejects_unknown_type():
    with pytest.raises(InvalidPipelineInputError):
        ensure_pipeline_input(1234)
