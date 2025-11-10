"""Single-file content repository implementations and factory wiring.

Purpose:
    Provide the infrastructure components that read single files for critique
    pipelines and a factory capable of producing both file and directory
    repositories on demand.
External Dependencies:
    Python standard library module ``hashlib``.
Fallback Semantics:
    No fallbacks are executed. Errors surface to callers as explicit exceptions.
Timeout Strategy:
    Not managed here. Callers should wrap invocations in timeout helpers when
    necessary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from ...application.critique.ports import ContentRepository, ContentRepositoryFactory
from ...application.critique.requests import DirectoryInputRequest, FileInputRequest
from ...pipeline_input import (
    AggregatedContentMetadata,
    EmptyPipelineInputError,
    FileSegmentMetadata,
    PipelineInput,
    pipeline_input_from_aggregated_content,
)

__all__ = [
    "FileSystemContentRepositoryFactory",
    "SingleFileContentRepository",
]


@dataclass
class FileSystemContentRepositoryFactory(ContentRepositoryFactory):
    """Factory producing repository instances for file-system backed inputs."""

    encoding: str = "utf-8"

    def create_for_file(self, request: FileInputRequest) -> ContentRepository:
        """Instantiate a repository for single-file inputs.
    
        Defensive hardening:
        - If the supplied path resolves to a directory, coerce to a
          DirectoryContentRepository so the pipeline can ingest multiple files.
        """
        resolved = request.path.expanduser().resolve()
        if resolved.exists() and resolved.is_dir():
            # Coerce to directory repository for robustness
            from .directory_repository import DirectoryContentRepository  # local import to avoid module import cycles
            return DirectoryContentRepository(DirectoryInputRequest(root=resolved), encoding=self.encoding)
    
        return SingleFileContentRepository(request, encoding=self.encoding)

    def create_for_directory(self, request: DirectoryInputRequest) -> ContentRepository:
        """Instantiate a repository for directory-based inputs."""

        from .directory_repository import DirectoryContentRepository

        return DirectoryContentRepository(request, encoding=self.encoding)


@dataclass
class SingleFileContentRepository(ContentRepository):
    """Load pipeline input from a single UTF-8 text file."""

    request: FileInputRequest
    encoding: str = "utf-8"

    def load_input(self) -> PipelineInput:
        """Read the configured file and return a ``PipelineInput`` instance.

        Returns:
            Pipeline input populated with file content and metadata describing the
            source file.

        Raises:
            FileNotFoundError: When the path does not exist or is not a regular file.
            UnicodeDecodeError: If the file cannot be decoded using the configured
                encoding.
            EmptyPipelineInputError: When the file contains only whitespace.

        Side Effects:
            Reads the target file from disk.

        Timeout:
            Not enforced; callers may wrap invocations as required.
        """

        resolved = self.request.path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Input file not found: {resolved}")
        if not resolved.is_file():
            raise FileNotFoundError(f"Input path is not a file: {resolved}")
        if resolved.is_symlink():
            raise FileNotFoundError(f"Symlinks are not supported for critique inputs: {resolved}")

        data = resolved.read_bytes()
        try:
            text = data.decode(self.encoding)
        except UnicodeDecodeError as exc:
            raise UnicodeDecodeError(
                exc.encoding or self.encoding,
                exc.object,
                exc.start,
                exc.end,
                f"{exc.reason} (while decoding {resolved})",
            ) from exc

        if not text.strip():
            raise EmptyPipelineInputError("Resolved file is empty.")

        digest = hashlib.sha256(data).hexdigest()
        segment = FileSegmentMetadata(
            path=resolved.name,
            start_offset=0,
            end_offset=len(text),
            byte_count=len(data),
            sha256_digest=digest,
        )
        aggregated = AggregatedContentMetadata.from_segments(
            input_type="file",
            segments=[segment],
            additional_info={"source_path": str(resolved)},
        )

        extra_metadata = {"source_path": str(resolved)}
        if self.request.label:
            extra_metadata["input_label"] = self.request.label

        return pipeline_input_from_aggregated_content(
            content=text,
            source=str(resolved),
            aggregated_metadata=aggregated,
            extra_metadata=extra_metadata,
        )
