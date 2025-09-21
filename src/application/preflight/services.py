"""Application services orchestrating preflight extraction workflows.

Purpose:
    Provide thin, testable coordinators that delegate heavy lifting to gateway
    interfaces. The services expose a straightforward API for presentation and
    orchestration layers to trigger extraction and query planning while keeping
    business logic free from framework concerns.
External Dependencies:
    Uses only Python standard library modules ``dataclasses`` and ``typing``
    alongside internal domain DTOs and pipeline primitives.
Fallback Semantics:
    Fallback and retry strategies are owned by the injected gateway
    implementations. The services propagate errors to the caller so they can
    decide how to respond (retry, fallback, or abort).
Timeout Strategy:
    No explicit timeouts are enforced in this module. Callers should manage
    timing concerns using higher-level ``operation_timeout`` utilities when
    interacting with external systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ...domain.preflight import ExtractionResult, QueryPlan
from ...pipeline_input import PipelineInput
from .ports import PointExtractorGateway, QueryBuilderGateway


def _validate_limit(limit: Optional[int], *, parameter_name: str) -> Optional[int]:
    """Validate numeric limits supplied to service operations.

    Args:
        limit: Optional numeric limit to validate.
        parameter_name: Human-readable name used in error messages.

    Returns:
        The original ``limit`` when valid.

    Raises:
        ValueError: If ``limit`` is provided and evaluates to zero or a negative
            number.
    """

    if limit is None:
        return None
    if limit <= 0:
        raise ValueError(f"{parameter_name} must be a positive integer when provided")
    return limit


@dataclass(slots=True)
class ExtractionService:
    """Coordinates calls to the :class:`PointExtractorGateway`.

    The service centralises handling of default configuration such as maximum
    point counts while leaving extraction details to the gateway. The dataclass
    is declared with ``slots`` to keep instances lightweight and to discourage
    runtime mutation of attributes outside the declared fields.
    """

    gateway: PointExtractorGateway
    default_max_points: Optional[int] = None

    def run(
        self,
        pipeline_input: PipelineInput,
        *,
        max_points: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> ExtractionResult:
        """Execute the point extraction workflow.

        Args:
            pipeline_input: Normalised representation of the corpus to analyse.
            max_points: Optional override for the number of points to request.
            metadata: Optional contextual data for downstream logging or
                providers. A defensive copy is created to prevent accidental
                mutation by callers during gateway execution.

        Returns:
            Structured extraction result produced by the gateway.

        Raises:
            ValueError: If ``max_points`` is provided but not positive.
            RuntimeError: Propagated from the gateway implementation when
                extraction fails.

        Side Effects:
            The gateway may perform I/O or invoke external services. The service
            itself does not have additional side effects.

        Timeout:
            Not enforced. Callers are expected to handle timeouts externally if
            required.
        """

        effective_limit = _validate_limit(
            max_points if max_points is not None else self.default_max_points,
            parameter_name="max_points",
        )
        metadata_copy = dict(metadata) if metadata is not None else None
        return self.gateway.extract_points(
            pipeline_input,
            max_points=effective_limit,
            metadata=metadata_copy,
        )


@dataclass(slots=True)
class QueryBuildingService:
    """Coordinates calls to the :class:`QueryBuilderGateway`.

    Similar to :class:`ExtractionService`, this service enforces lightweight
    validation and default handling before delegating to the gateway. Keeping the
    logic concentrated here simplifies testing and ensures presentation code can
    remain thin.
    """

    gateway: QueryBuilderGateway
    default_max_queries: Optional[int] = None

    def run(
        self,
        extraction: ExtractionResult,
        pipeline_input: Optional[PipelineInput] = None,
        *,
        max_queries: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> QueryPlan:
        """Execute the query building workflow.

        Args:
            extraction: Structured extraction result that contains the points used
                for planning queries.
            pipeline_input: Optional original corpus to supply extra context to
                the gateway.
            max_queries: Optional override for limiting the number of queries.
            metadata: Optional mapping of contextual hints. A defensive copy is
                passed to downstream components to avoid shared mutation.

        Returns:
            Query plan produced by the gateway.

        Raises:
            ValueError: If ``max_queries`` is provided but not positive.
            RuntimeError: Propagated from the gateway implementation.

        Side Effects:
            The gateway may interact with external providers or record
            observability data.

        Timeout:
            Determined by the gateway or caller-supplied wrappers.
        """

        effective_limit = _validate_limit(
            max_queries if max_queries is not None else self.default_max_queries,
            parameter_name="max_queries",
        )
        metadata_copy = dict(metadata) if metadata is not None else None
        return self.gateway.build_queries(
            extraction,
            pipeline_input,
            max_queries=effective_limit,
            metadata=metadata_copy,
        )


__all__ = ["ExtractionService", "QueryBuildingService"]
