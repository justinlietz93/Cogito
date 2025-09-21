"""Utility models and helpers for normalising pipeline inputs.

Purpose:
    Provide framework-agnostic abstractions for representing text content and
    associated metadata across presentation and application layers.
External Dependencies:
    Uses only the Python standard library.
Fallback Semantics:
    Delegated to caller-provided callbacks such as ``read_file`` and optional
    parameters on the normalisation helpers.
Timeout Strategy:
    No explicit timeouts are enforced in this module; callers should wrap file
    system access using higher-level ``operation_timeout`` utilities when
    required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple, Union

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


@dataclass(frozen=True)
class FileSegmentMetadata:
    """Metadata describing a single file segment contributing to pipeline input.

    Attributes:
        path: Normalised path relative to the repository root identifying the
            contributing file.
        start_offset: Starting character offset (zero-based) of the file's
            contribution within the aggregated pipeline content.
        end_offset: Exclusive ending character offset within the aggregated
            content corresponding to this file. ``end_offset`` must be greater
            than or equal to ``start_offset``.
        byte_count: Size of the UTF-8 encoded payload consumed from the file. The
            value reflects truncated reads when size caps are enforced.
        sha256_digest: Hex-encoded SHA-256 digest of the consumed bytes. When
            truncation occurs, the digest is calculated over the truncated data to
            retain reproducibility guarantees.
        truncated: Flag indicating whether the repository truncated this file's
            content due to safety caps.

    Raises:
        ValueError: If ``end_offset`` is less than ``start_offset`` when the
            instance is created.
    """

    path: str
    start_offset: int
    end_offset: int
    byte_count: int
    sha256_digest: str
    truncated: bool = False

    def __post_init__(self) -> None:
        """Validate offset ordering for the metadata instance.

        Raises:
            ValueError: If ``end_offset`` is less than ``start_offset``.
        """

        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be greater than or equal to start_offset")

    def as_dict(self) -> Dict[str, Any]:
        """Serialise the metadata to a dictionary for pipeline consumers.

        Returns:
            Dictionary containing serialisable metadata fields suitable for JSON
            output or storage within :class:`PipelineInput.metadata`.
        """

        return {
            "path": self.path,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "bytes": self.byte_count,
            "sha256": self.sha256_digest,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class AggregatedContentMetadata:
    """Container describing aggregated content returned by a repository.

    Attributes:
        input_type: Identifier describing the origin of the aggregated content.
            Typical values include ``"file"`` and ``"directory"``.
        files: Ordered sequence of :class:`FileSegmentMetadata` instances capturing
            how individual files contributed to the aggregated payload.
        total_bytes: Combined byte count across all included files.
        truncated: Indicates whether any repository-level truncation occurred (for
            example because ``max_chars`` was exceeded).
        truncation_reason: Optional human-readable reason for truncation.
        additional_info: Optional mapping with implementation-specific metadata.

    Raises:
        ValueError: If ``files`` contains duplicate paths while ``input_type`` is
            ``"directory"``.
    """

    input_type: str
    files: Sequence[FileSegmentMetadata] = field(default_factory=tuple)
    total_bytes: int = 0
    truncated: bool = False
    truncation_reason: Optional[str] = None
    additional_info: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate aggregated metadata assumptions after initialisation."""

        if self.input_type == "directory":
            seen_paths: set[str] = set()
            for segment in self.files:
                if segment.path in seen_paths:
                    raise ValueError(f"Duplicate metadata entry for path: {segment.path}")
                seen_paths.add(segment.path)

    def as_dict(self) -> Dict[str, Any]:
        """Serialise the aggregated metadata into a plain dictionary.

        Returns:
            Mapping containing the aggregated metadata suitable for embedding in a
            :class:`PipelineInput` instance.
        """

        return {
            "input_type": self.input_type,
            "files": [segment.as_dict() for segment in self.files],
            "total_bytes": self.total_bytes,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "additional_info": dict(self.additional_info),
        }

    @classmethod
    def from_segments(
        cls,
        *,
        input_type: str,
        segments: Iterable[FileSegmentMetadata],
        truncation_reason: Optional[str] = None,
        additional_info: Optional[Mapping[str, Any]] = None,
    ) -> "AggregatedContentMetadata":
        """Construct metadata from a sequence of file segments.

        Args:
            input_type: Logical identifier describing the origin of the content.
            segments: Iterable of :class:`FileSegmentMetadata` objects.
            truncation_reason: Optional reason describing why truncation occurred.
            additional_info: Optional mapping containing implementation specific
                metadata.

        Returns:
            Instance of :class:`AggregatedContentMetadata` combining supplied
            segments.
        """

        segment_list: Tuple[FileSegmentMetadata, ...] = tuple(segments)
        total_bytes = sum(item.byte_count for item in segment_list)
        truncated = any(item.truncated for item in segment_list)
        return cls(
            input_type=input_type,
            files=segment_list,
            total_bytes=total_bytes,
            truncated=truncated,
            truncation_reason=truncation_reason,
            additional_info=additional_info or {},
        )


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


def pipeline_input_from_aggregated_content(
    *,
    content: str,
    source: Optional[str],
    aggregated_metadata: AggregatedContentMetadata,
    extra_metadata: Optional[Mapping[str, Any]] = None,
) -> PipelineInput:
    """Build a :class:`PipelineInput` from aggregated repository metadata.

    Args:
        content: Concatenated string content supplied by the repository.
        source: Optional canonical source identifier (for example the root
            directory path). ``None`` should be used for literal content without a
            stable origin.
        aggregated_metadata: Metadata describing the aggregated content produced
            by the repository.
        extra_metadata: Optional additional metadata to merge into the resulting
            :class:`PipelineInput`. Keys in ``extra_metadata`` override those from
            ``aggregated_metadata`` when duplicates are present.

    Returns:
        A :class:`PipelineInput` instance containing the supplied content and a
        metadata dictionary generated from ``aggregated_metadata``.

    Raises:
        InvalidPipelineInputError: If ``content`` is not a string.

    Side Effects:
        None.

    Timeout:
        Not applicable; callers should manage timeouts during repository reads.
    """

    metadata: Dict[str, Any] = aggregated_metadata.as_dict()
    if extra_metadata:
        metadata.update(dict(extra_metadata))
    return PipelineInput(content=content, source=source, metadata=metadata)


__all__ = [
    "AggregatedContentMetadata",
    "EmptyPipelineInputError",
    "FileSegmentMetadata",
    "InvalidPipelineInputError",
    "PipelineInput",
    "PipelineInputError",
    "ensure_pipeline_input",
    "pipeline_input_from_aggregated_content",
]
