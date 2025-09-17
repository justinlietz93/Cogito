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
