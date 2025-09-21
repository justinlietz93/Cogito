"""Directory-backed content repository implementations.

Purpose:
    Provide infrastructure implementations that aggregate directory trees into
    :class:`~src.pipeline_input.PipelineInput` instances for critique pipelines
    while enforcing filtering, ordering, and truncation semantics defined by the
    application layer.
External Dependencies:
    Python standard library modules ``fnmatch``, ``hashlib``, ``json``, and
    ``pathlib``.
Fallback Semantics:
    Unreadable or non-text files are skipped with logged warnings. No implicit
    retries are attempted beyond the configured aggregation options.
Timeout Strategy:
    Not defined at this layer. Callers should provide their own timeout handling
    when invoking long-running operations.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

from ...application.critique.ports import ContentRepository
from ...application.critique.requests import DirectoryInputRequest
from ...pipeline_input import (
    AggregatedContentMetadata,
    EmptyPipelineInputError,
    FileSegmentMetadata,
    PipelineInput,
    UnreadableFileError,
    pipeline_input_from_aggregated_content,
)

__all__ = ["DirectoryContentRepository"]


_LOGGER = logging.getLogger(__name__)


@dataclass
class DirectoryContentRepository(ContentRepository):
    """Aggregate multiple files from a directory into a single pipeline input."""

    request: DirectoryInputRequest
    encoding: str = "utf-8"

    def load_input(self) -> PipelineInput:
        """Aggregate directory contents into a pipeline input.

        Returns:
            Pipeline input containing concatenated file contents with detailed
            metadata describing the aggregation process.

        Raises:
            FileNotFoundError: When the configured root does not exist.
            NotADirectoryError: If the configured root is not a directory.
            EmptyPipelineInputError: When no files match the filters or the
                resulting content is empty.
            ValueError: If the order file cannot be parsed as JSON when a JSON
                extension is provided.

        Side Effects:
            Reads files from disk and logs skipped files for observability.

        Timeout:
            Not enforced at this layer.
        """

        root = self.request.root.expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Input directory not found: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {root}")

        files = self._discover_files(root)
        if not files:
            raise EmptyPipelineInputError("No files matched the provided filters.")

        explicit_order = self._resolve_explicit_order(root)
        ordered = self._apply_ordering(files, explicit_order, root)

        aggregator = _DirectoryAggregator(
            root=root,
            files=ordered,
            request=self.request,
            encoding=self.encoding,
        )
        result = aggregator.aggregate()
        metadata = AggregatedContentMetadata.from_segments(
            input_type="directory",
            segments=result.segments,
            truncation_reason=result.truncation_reason,
            additional_info={
                "root": str(root),
                "file_count": len(result.segments),
                "processed_files": result.processed_files,
                "skipped_files": result.skipped_files,
                "skipped_file_count": len(result.skipped_files),
                "total_characters": result.total_chars,
                "max_files": self.request.max_files,
                "max_chars": self.request.max_chars,
                "truncation_events": result.truncation_events,
            },
        )

        extra_metadata = {
            "source_path": str(root),
            "label_sections": self.request.label_sections,
            "section_separator": self.request.section_separator,
        }

        _LOGGER.info(
            "Directory aggregation summary: %s",
            json.dumps(
                {
                    "operation": "aggregate_directory",
                    "root": str(root),
                    "processed_files": result.processed_files,
                    "skipped_file_count": len(result.skipped_files),
                    "skipped_files": list(result.skipped_files),
                    "total_characters": result.total_chars,
                    "total_bytes": metadata.total_bytes,
                    "truncated": metadata.truncated,
                    "truncation_reason": metadata.truncation_reason,
                    "truncation_events": list(result.truncation_events),
                    "max_files": self.request.max_files,
                    "max_chars": self.request.max_chars,
                },
                sort_keys=True,
            ),
        )

        return pipeline_input_from_aggregated_content(
            content=result.content,
            source=str(root),
            aggregated_metadata=metadata,
            extra_metadata=extra_metadata,
        )

    def _discover_files(self, root: Path) -> List[Path]:
        """Return candidate files honouring include/exclude filters."""

        iterator: Iterator[Path]
        if self.request.recursive:
            iterator = root.rglob("*")
        else:
            iterator = root.glob("*")

        candidates: List[Path] = []
        for path in iterator:
            if not path.is_file():
                continue
            if path.is_symlink():
                _LOGGER.debug("Ignoring symlinked file: %s", path)
                continue
            try:
                path.relative_to(root)
            except ValueError:
                _LOGGER.debug("Skipping path outside root: %s", path)
                continue
            if self._is_hidden(path, root) and not self.request.include:
                _LOGGER.debug("Skipping hidden file: %s", path)
                continue
            if not self._matches_include(path, root):
                continue
            if self._matches_exclude(path, root):
                continue
            candidates.append(path)
        return candidates

    def _resolve_explicit_order(self, root: Path) -> Tuple[str, ...]:
        """Determine explicit ordering values from request parameters."""

        if self.request.explicit_order:
            return self.request.explicit_order
        if self.request.order_file is None:
            return ()
        order_path = self.request.order_file.expanduser().resolve()
        if not order_path.exists():
            raise FileNotFoundError(f"Order file not found: {order_path}")
        if not order_path.is_file():
            raise FileNotFoundError(f"Order path is not a file: {order_path}")
        raw = order_path.read_text(encoding=self.encoding)
        try:
            if order_path.suffix.lower() == ".json":
                payload = json.loads(raw)
                if not isinstance(payload, Sequence):
                    raise ValueError("JSON order file must contain an array of strings.")
                return tuple(str(item) for item in payload)
            return tuple(line.strip() for line in raw.splitlines() if line.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON order file '{order_path}': {exc}") from exc

    def _apply_ordering(
        self,
        files: List[Path],
        explicit_order: Tuple[str, ...],
        root: Path,
    ) -> List[Path]:
        """Return files ordered according to explicit preferences."""

        if not explicit_order:
            return sorted(files, key=lambda item: item.relative_to(root).as_posix())

        mapping = {file.relative_to(root).as_posix(): file for file in files}
        ordered: List[Path] = []
        for entry in explicit_order:
            candidate = mapping.pop(entry, None)
            if candidate is None:
                _LOGGER.warning("Ordered file '%s' not found under %s", entry, root)
                continue
            ordered.append(candidate)
        remaining = sorted(mapping.values(), key=lambda item: item.relative_to(root).as_posix())
        return ordered + remaining

    def _matches_include(self, path: Path, root: Path) -> bool:
        """Return ``True`` when the path matches configured include patterns."""

        if not self.request.include:
            return True
        relative_path = path.relative_to(root)
        return any(
            self._pattern_matches(relative_path, pattern) for pattern in self.request.include
        )

    def _matches_exclude(self, path: Path, root: Path) -> bool:
        """Return ``True`` when the path matches configured exclude patterns."""

        relative_path = path.relative_to(root)
        return any(
            self._pattern_matches(relative_path, pattern) for pattern in self.request.exclude
        )

    @staticmethod
    def _is_hidden(path: Path, root: Path) -> bool:
        """Determine whether the relative path is considered hidden."""

        relative = path.relative_to(root)
        return any(part.startswith(".") for part in relative.parts)

    @staticmethod
    def _pattern_matches(relative_path: Path, pattern: str) -> bool:
        """Return whether the path matches the provided glob pattern."""

        relative = relative_path.as_posix()
        if fnmatch.fnmatch(relative, pattern) or relative_path.match(pattern):
            return True
        if pattern.startswith("**/"):
            simplified = pattern[3:]
            if simplified:
                return fnmatch.fnmatch(relative, simplified) or relative_path.match(simplified)
        return False


@dataclass
class AggregationResult:
    """Container describing the result of directory aggregation.

    Attributes:
        content: Concatenated text payload ready for pipeline consumption.
        segments: Tuple of metadata entries describing each included file.
        skipped_files: Relative paths skipped due to errors or decoding issues.
        truncation_reason: Primary truncation trigger when safety caps apply.
        truncation_events: Ordered tuple of all truncation triggers encountered.
        total_chars: Total number of characters emitted after aggregation.
        processed_files: Count of files whose content contributed to the result.
    """

    content: str
    segments: Tuple[FileSegmentMetadata, ...]
    skipped_files: Tuple[str, ...]
    truncation_reason: Optional[str]
    truncation_events: Tuple[str, ...]
    total_chars: int
    processed_files: int


@dataclass
class _DirectoryAggregator:
    """Helper responsible for reading files and building metadata."""

    root: Path
    files: Sequence[Path]
    request: DirectoryInputRequest
    encoding: str
    _READ_CHUNK_SIZE: int = 8192

    def aggregate(self) -> AggregationResult:
        """Aggregate configured files into a combined content payload."""

        parts: List[str] = []
        segments: List[FileSegmentMetadata] = []
        skipped: List[str] = []
        total_chars = 0
        truncation_reasons: set[str] = set()
        files_processed = 0

        for file_path in self.files:
            if self.request.max_files is not None and files_processed >= self.request.max_files:
                truncation_reasons.add("max_files")
                break

            relative = file_path.relative_to(self.root).as_posix()
            try:
                segment_result = self._append_file(
                    parts=parts,
                    current_chars=total_chars,
                    file_path=file_path,
                    relative_path=relative,
                    is_first=files_processed == 0,
                )
            except UnicodeDecodeError:
                _LOGGER.warning("Skipping non-text file: %s", file_path)
                skipped.append(relative)
                continue
            except OSError as exc:
                _LOGGER.error("Failed to read file %s: %s", file_path, exc)
                raise UnreadableFileError(f"Failed to read {relative}") from exc

            if segment_result is None:
                truncation_reasons.add("max_chars")
                break

            total_chars = segment_result.new_total_chars
            segments.append(segment_result.metadata)
            files_processed += 1
            if segment_result.truncated:
                truncation_reasons.add("max_chars")

        combined = "".join(parts)
        if not combined.strip():
            raise EmptyPipelineInputError("Aggregated directory content is empty.")

        ordered_reasons = tuple(sorted(truncation_reasons))
        primary_reason = ordered_reasons[0] if ordered_reasons else None

        return AggregationResult(
            content=combined,
            segments=tuple(segments),
            skipped_files=tuple(skipped),
            truncation_reason=primary_reason,
            truncation_events=ordered_reasons,
            total_chars=len(combined),
            processed_files=len(segments),
        )

    @dataclass
    class _SegmentResult:
        new_total_chars: int
        metadata: FileSegmentMetadata
        truncated: bool

    def _append_file(
        self,
        *,
        parts: List[str],
        current_chars: int,
        file_path: Path,
        relative_path: str,
        is_first: bool,
    ) -> Optional["_DirectoryAggregator._SegmentResult"]:
        """Append a single file to the aggregation buffer."""

        truncated = False

        if not is_first:
            appended, current_chars, truncated_sep = self._append_part(
                parts,
                current_chars,
                self.request.section_separator,
            )
            if appended == "":
                return None
            truncated = truncated or truncated_sep

        start_offset = current_chars

        if self.request.label_sections:
            label_text = f"## {relative_path}\n\n"
            appended, current_chars, truncated_label = self._append_part(parts, current_chars, label_text)
            if appended == "":
                return None
            truncated = truncated or truncated_label

        digest = hashlib.sha256()
        new_total = current_chars
        consumed_bytes = 0

        with file_path.open("r", encoding=self.encoding) as handle:
            while True:
                chunk = handle.read(self._READ_CHUNK_SIZE)
                if chunk == "":
                    break
                appended_content, new_total, truncated_content = self._append_part(
                    parts,
                    new_total,
                    chunk,
                )
                if appended_content == "":
                    truncated = True
                    break
                encoded = appended_content.encode(self.encoding)
                consumed_bytes += len(encoded)
                digest.update(encoded)
                truncated = truncated or truncated_content
                if truncated_content:
                    break

        if consumed_bytes == 0:
            return None

        end_offset = new_total

        metadata = FileSegmentMetadata(
            path=relative_path,
            start_offset=start_offset,
            end_offset=end_offset,
            byte_count=consumed_bytes,
            sha256_digest=digest.hexdigest(),
            truncated=truncated,
        )
        return self._SegmentResult(new_total_chars=new_total, metadata=metadata, truncated=truncated)

    def _append_part(
        self,
        parts: List[str],
        current_chars: int,
        value: str,
    ) -> Tuple[str, int, bool]:
        """Append a text fragment respecting the ``max_chars`` constraint."""

        if not value:
            return "", current_chars, False

        limit = self.request.max_chars
        if limit is None:
            parts.append(value)
            return value, current_chars + len(value), False

        remaining = limit - current_chars
        if remaining <= 0:
            return "", current_chars, True

        if len(value) <= remaining:
            parts.append(value)
            return value, current_chars + len(value), False

        truncated_value = value[:remaining]
        parts.append(truncated_value)
        return truncated_value, limit, True
