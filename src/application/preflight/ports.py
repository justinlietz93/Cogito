"""Interface contracts for preflight extraction and query planning.

Purpose:
    Define framework-agnostic ports that decouple presentation and
    infrastructure layers from the orchestration logic required for point
    extraction and query building. These protocols allow adapters to depend on
    abstractions owned by the application layer, satisfying the project's clean
    architecture rules.
External Dependencies:
    Relies exclusively on Python's standard library ``typing`` module and shared
    domain DTOs.
Fallback Semantics:
    No fallback logic is expressed at the contract level. Implementations may
    supply retries or degrade gracefully while reporting structured errors.
Timeout Strategy:
    Timeouts are not enforced within the interfaces. Callers are expected to wrap
    blocking calls using higher-level ``operation_timeout`` utilities when
    coordinating with external providers.
"""

from __future__ import annotations

from typing import Mapping, Optional, Protocol

from ...pipeline_input import PipelineInput
from ...domain.preflight import ExtractionResult, QueryPlan


class PointExtractorGateway(Protocol):
    """Abstraction responsible for converting raw input into structured points."""

    def extract_points(
        self,
        pipeline_input: PipelineInput,
        *,
        max_points: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> ExtractionResult:
        """Extract salient points from the supplied pipeline input.

        Args:
            pipeline_input: Normalised representation of the corpus to analyse.
            max_points: Optional cap applied by orchestration logic. Implementers
                must respect the limit when provided.
            metadata: Optional contextual hints such as run identifiers or
                selection strategies. Implementations should treat the mapping as
                read-only.

        Returns:
            Structured extraction result containing zero or more points.

        Raises:
            RuntimeError: Implementations may raise when provider operations fail
                irrecoverably. The type should be implementation-specific to aid
                diagnostics.

        Side Effects:
            May invoke external providers or perform I/O depending on the
            concrete adapter.

        Timeout:
            Determined by implementations. Callers should apply ``operation_timeout``
            at higher layers when needed.
        """


class QueryBuilderGateway(Protocol):
    """Abstraction responsible for deriving follow-up queries from points."""

    def build_queries(
        self,
        extraction: ExtractionResult,
        pipeline_input: Optional[PipelineInput] = None,
        *,
        max_queries: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> QueryPlan:
        """Construct a query plan based on extracted points and optional context.

        Args:
            extraction: Result produced by :class:`PointExtractorGateway`.
            pipeline_input: Optional original corpus for reference when crafting
                queries.
            max_queries: Optional cap for the number of queries generated.
            metadata: Optional contextual hints or run metadata.

        Returns:
            Query plan enumerating queries, rationale, and related context.

        Raises:
            RuntimeError: When the gateway encounters unrecoverable provider
                issues.

        Side Effects:
            May call external services or log structured observability data.

        Timeout:
            Managed by the implementation or by caller-supplied wrappers.
        """


__all__ = ["PointExtractorGateway", "QueryBuilderGateway"]
