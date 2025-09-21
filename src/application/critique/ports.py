"""Ports for coordinating critique runs."""

from __future__ import annotations

from typing import Any, Dict, Protocol

from ...pipeline_input import PipelineInput, PipelineInputError


class CritiqueGateway(Protocol):
    """Abstraction over the critique execution pipeline."""

    def run(
        self,
        input_data: Any,
        config: Dict[str, Any],
        peer_review: bool,
        scientific_mode: bool,
    ) -> str:
        """Execute the critique and return a formatted report."""


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
        """


__all__ = ["ContentRepository", "CritiqueGateway"]
