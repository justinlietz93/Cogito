"""Utility models and helpers for normalising pipeline inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Union

ReadCallback = Callable[[str], str]


class PipelineInputError(Exception):
    """Base exception for pipeline input errors."""


class InvalidPipelineInputError(PipelineInputError):
    """Raised when the supplied input cannot be converted into pipeline content."""


class EmptyPipelineInputError(PipelineInputError):
    """Raised when the resolved pipeline content is empty."""


@dataclass
class PipelineInput:
    """Canonical representation of input provided to processing pipelines."""

    content: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise InvalidPipelineInputError("Pipeline input content must be a string.")
        # Ensure metadata is always a plain dictionary to avoid accidental sharing of state.
        self.metadata = dict(self.metadata or {})


def ensure_pipeline_input(
    input_data: Union[PipelineInput, str, Mapping[str, Any]],
    *,
    read_file: Optional[ReadCallback] = None,
    assume_path: bool = False,
    fallback_to_content: bool = False,
    allow_empty: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> PipelineInput:
    """Normalise supported input types into a :class:`PipelineInput` instance.

    Args:
        input_data: Raw input that should be interpreted as pipeline content.
        read_file: Optional callable used to load content when ``input_data`` is a
            file path.
        assume_path: When ``True`` and ``input_data`` is a string, attempt to read it
            as a file path using ``read_file``.
        fallback_to_content: When ``True`` and ``assume_path`` is enabled, missing
            files are treated as literal content instead of raising an error.
        allow_empty: When ``True`` empty content is allowed. Otherwise an
            :class:`EmptyPipelineInputError` is raised.
        metadata: Optional metadata to merge into the resulting instance.

    Returns:
        A :class:`PipelineInput` instance wrapping the resolved content.

    Raises:
        FileNotFoundError: If a file path is expected but not found and fallback is
            disabled.
        InvalidPipelineInputError: If ``input_data`` cannot be interpreted.
        EmptyPipelineInputError: If the resolved content is empty and ``allow_empty``
            is ``False``.
    """

    merged_metadata: Dict[str, Any] = dict(metadata or {})

    if isinstance(input_data, PipelineInput):
        if merged_metadata:
            combined_metadata = {**input_data.metadata, **merged_metadata}
            result = PipelineInput(
                content=input_data.content,
                source=input_data.source,
                metadata=combined_metadata,
            )
        else:
            result = input_data
    elif isinstance(input_data, str):
        if assume_path and read_file is not None:
            try:
                file_content = read_file(input_data)
            except FileNotFoundError:
                if not fallback_to_content:
                    raise
                file_content = input_data
                merged_metadata.setdefault("input_type", "text")
                merged_metadata.setdefault("fallback_reason", "file_not_found")
                result = PipelineInput(content=file_content, metadata=merged_metadata)
            else:
                merged_metadata.setdefault("input_type", "file")
                merged_metadata.setdefault("source_path", input_data)
                result = PipelineInput(content=file_content, source=input_data, metadata=merged_metadata)
        else:
            merged_metadata.setdefault("input_type", "text")
            result = PipelineInput(content=input_data, metadata=merged_metadata)
    elif isinstance(input_data, Mapping):
        raw_data = dict(input_data)
        if "content" in raw_data:
            content_value = raw_data.pop("content")
        elif "text" in raw_data:
            content_value = raw_data.pop("text")
        else:
            raise InvalidPipelineInputError("Mapping input must contain a 'content' or 'text' field.")

        source_value = raw_data.pop("source", None) or raw_data.pop("source_path", None)
        combined_metadata = {**raw_data, **merged_metadata}
        result = PipelineInput(content=str(content_value), source=source_value, metadata=combined_metadata)
    else:
        raise InvalidPipelineInputError(f"Unsupported pipeline input type: {type(input_data)!r}")

    if not allow_empty and not result.content.strip():
        raise EmptyPipelineInputError("Pipeline input content is empty.")

    return result


__all__ = [
    "PipelineInput",
    "PipelineInputError",
    "InvalidPipelineInputError",
    "EmptyPipelineInputError",
    "ensure_pipeline_input",
]
