"""Interfaces defining critique application ports.

Purpose:
    Provide framework-agnostic contracts that presentation code can rely on when
    orchestrating critique pipeline executions. These ports enable dependency
    inversion by forcing outer layers to depend on abstractions owned by the
    application layer.
External Dependencies:
    Python standard library only.
Fallback Semantics:
    No fallbacks are provided at this layer. Implementations are responsible for
    exposing explicit error handling strategies to callers.
Timeout Strategy:
    No timeouts are enforced within the protocols. Callers should wrap
    invocations using ``operation_timeout`` utilities when coordination with
    external systems is required.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol

from ...pipeline_input import PipelineInput, PipelineInputError
from .requests import DirectoryInputRequest, FileInputRequest


class CritiqueGateway(Protocol):
    """Abstraction over the critique execution pipeline.

    Implementations encapsulate the orchestration logic that coordinates
    pipeline components. Presentation adapters interact only with this interface
    to comply with the clean-architecture dependency rule.
    """

    def run(
        self,
        input_data: Any,
        config: Dict[str, Any],
        peer_review: bool,
        scientific_mode: bool,
    ) -> str:
        """Execute the critique workflow and return a formatted report.

        Args:
            input_data: Raw pipeline input DTO or content string.
            config: Pipeline configuration dictionary.
            peer_review: Flag indicating whether to include peer review steps.
            scientific_mode: Flag toggling scientific analysis heuristics.

        Returns:
            Rendered critique output in textual form.

        Raises:
            RuntimeError: Implementations may raise on unrecoverable pipeline
                failures.

        Side Effects:
            Implementations may read files, call APIs, or write outputs depending
            on the configured pipeline stages.

        Timeout:
            Determined by the concrete implementation; callers should apply
            ``operation_timeout`` if they require bounded execution time.
        """


class ContentRepository(Protocol):
    """Provides aggregated content for critique pipelines.

    Implementations encapsulate how raw input data is located and converted into
    :class:`PipelineInput`. This protocol enables the presentation layer to select
    an appropriate repository (single file, directory, literal text) while the
    application layer consumes a consistent abstraction. The contract explicitly
    enforces the dependency flow described in ``ARCHITECTURE_RULES.md`` where the
    presentation layer relies on application-defined interfaces rather than
    infrastructure details.
    """

    def load_input(self) -> PipelineInput:
        """Resolve and return a :class:`PipelineInput` instance.

        Returns:
            Aggregated pipeline input containing content and metadata describing
            the source of the data.

        Raises:
            PipelineInputError: If the aggregated content violates pipeline input
                constraints (for example empty content).
            OSError: If the underlying file system interactions fail. Concrete
                implementations may raise subclasses such as ``FileNotFoundError``
                or ``PermissionError``.

        Side Effects:
            Implementations typically perform file-system reads or other I/O to
            assemble the aggregated content.

        Timeout:
            Not enforced at the protocol level. Implementations should expose
            their own timeout handling or rely on caller-provided wrappers.
        """


class ContentRepositoryFactory(Protocol):
    """Factory responsible for building content repositories from requests.

    The factory itself lives in the infrastructure layer and is injected into
    the application service at composition time. This keeps repository selection
    logic out of the presentation layer.
    """

    def create_for_file(self, request: FileInputRequest) -> ContentRepository:
        """Build a repository that loads content from a single file.

        Args:
            request: Application DTO describing the file input parameters.

        Returns:
            Concrete repository capable of loading the requested file.

        Raises:
            OSError: Propagated when the repository cannot access the file.
        """

    def create_for_directory(self, request: DirectoryInputRequest) -> ContentRepository:
        """Build a repository that aggregates a directory tree.

        Args:
            request: Application DTO describing directory ingestion semantics.

        Returns:
            Repository capable of aggregating the directory into a
            :class:`PipelineInput`.

        Raises:
            OSError: Propagated when the underlying file system operations fail.
        """


__all__ = ["ContentRepository", "ContentRepositoryFactory", "CritiqueGateway"]
