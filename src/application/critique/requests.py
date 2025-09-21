"""Application-level DTOs describing critique input sources.

Purpose:
    Provide immutable request objects that presentation adapters use to describe
    how critique content should be resolved. The application layer consumes these
    DTOs to select appropriate content repositories without peeking into
    presentation-specific constructs.
External Dependencies:
    Uses only the Python standard library ``dataclasses`` and ``pathlib``
    modules.
Fallback Semantics:
    DTOs do not encode fallback behaviour. Repository implementations decide how
    to handle missing files or decoding issues.
Timeout Strategy:
    Not applicable. These DTOs carry configuration only and are not responsible
    for executing I/O operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class LiteralTextInputRequest:
    """Describe a literal text payload supplied directly by the user.

    Args:
        text: The textual content that should be critiqued.
        label: Optional identifier to store alongside the aggregated metadata.

    Raises:
        ValueError: If ``text`` is empty or whitespace only.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    text: str
    label: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("LiteralTextInputRequest requires non-empty text content.")


@dataclass(frozen=True)
class FileInputRequest:
    """Describe a single file that should be ingested into the critique pipeline.

    Args:
        path: Absolute or relative path to the file on disk.
        label: Optional label to carry into metadata for downstream consumers.

    Raises:
        ValueError: If ``path`` is empty.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    path: Path
    label: Optional[str] = None

    def __post_init__(self) -> None:
        if not str(self.path):
            raise ValueError("FileInputRequest.path must not be empty.")


@dataclass(frozen=True)
class DirectoryInputRequest:
    """Describe a directory tree that should be aggregated into a pipeline input.

    Args:
        root: Directory containing source files.
        include: Glob patterns identifying files to include.
        exclude: Glob patterns identifying files to exclude.
        recursive: Whether to traverse sub-directories.
        order: Optional explicit ordering of file names relative to ``root``.
        order_file: Optional path to a file containing order definitions.
        max_files: Maximum number of files to ingest; ``None`` disables the cap.
        max_chars: Maximum cumulative character count; ``None`` disables the cap.
        section_separator: String inserted between file contents.
        label_sections: Whether repositories should add heading labels per file.

    Raises:
        ValueError: If mutually exclusive options ``order`` and ``order_file`` are
            both provided.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    root: Path
    include: Sequence[str] = field(default_factory=tuple)
    exclude: Sequence[str] = field(default_factory=tuple)
    recursive: bool = True
    order: Optional[Sequence[str]] = None
    order_file: Optional[Path] = None
    max_files: Optional[int] = None
    max_chars: Optional[int] = None
    section_separator: str = "\n\n"
    label_sections: bool = True

    def __post_init__(self) -> None:
        if self.order and self.order_file is not None:
            raise ValueError("Provide either 'order' or 'order_file', not both.")

    @property
    def include_patterns(self) -> Tuple[str, ...]:
        """Return include globs as an immutable tuple."""

        return tuple(self.include)

    @property
    def exclude_patterns(self) -> Tuple[str, ...]:
        """Return exclude globs as an immutable tuple."""

        return tuple(self.exclude)

    @property
    def explicit_order(self) -> Optional[Tuple[str, ...]]:
        """Return explicit order values as an immutable tuple when provided."""

        if self.order is None:
            return None
        return tuple(self.order)


__all__ = [
    "DirectoryInputRequest",
    "FileInputRequest",
    "LiteralTextInputRequest",
]
