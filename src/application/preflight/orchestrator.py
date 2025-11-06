"""Orchestrator for coordinating preflight extraction and query planning.

Purpose:
    Provide a thin coordination layer that sequences the extraction and query
    building services ahead of the main critique pipeline. The orchestrator
    ensures configuration toggles are honoured and that downstream callers
    receive structured artefacts alongside recommended output locations.
External Dependencies:
    Relies exclusively on application-layer services and domain DTOs; no
    framework or infrastructure modules are imported.
Fallback Semantics:
    Fallback handling is delegated to the injected services and their
    respective gateways. This orchestrator simply propagates exceptions so the
    caller can decide how to recover.
Timeout Strategy:
    The orchestrator does not enforce timeouts directly. Callers should wrap
    invocations using :func:`src.infrastructure.timeouts.operation_timeout`
    when coordinating with external providers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional

from ...domain.preflight import ExtractionResult, QueryPlan
from ...pipeline_input import PipelineInput
from .services import ExtractionService, QueryBuildingService


_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PreflightOptions:
    """Configuration toggles supplied to the preflight orchestrator.

    Attributes:
        enable_extraction: Flag indicating whether point extraction should run.
        enable_query_building: Flag indicating whether query planning should
            execute after extraction. Query building requires extraction to be
            enabled to provide source points.
        max_points: Optional limit to enforce when extracting points. ``None``
            delegates limit selection to the extraction service defaults.
        max_queries: Optional cap for the number of queries produced. ``None``
            delegates to the query building service defaults.
        metadata: Optional mapping propagated to both services to aid logging
            or observability. A defensive copy is made before delegation.
        extraction_artifact_name: Recommended relative path for persisting the
            extraction result JSON. ``None`` disables artefact registration for
            the extraction stage.
        query_artifact_name: Recommended relative path for persisting the query
            plan JSON. ``None`` disables artefact registration for the query
            stage.
    """

    enable_extraction: bool = False
    enable_query_building: bool = False
    max_points: Optional[int] = None
    max_queries: Optional[int] = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    extraction_artifact_name: Optional[str] = "artifacts/points.json"
    query_artifact_name: Optional[str] = "artifacts/queries.json"


@dataclass
class PreflightRunResult:
    """Container capturing the outputs of the preflight orchestrator.

    Attributes:
        extraction: Structured extraction result when the extraction stage ran.
        query_plan: Structured query plan when query building was executed.
        artifact_paths: Mapping of logical artefact identifiers to recommended
            relative output paths within a run's artefacts directory. Callers
            may mutate the mapping after persisting files to record absolute
            paths.
    """

    extraction: Optional[ExtractionResult] = None
    query_plan: Optional[QueryPlan] = None
    artifact_paths: Dict[str, str] = field(default_factory=dict)

    def has_outputs(self) -> bool:
        """Return ``True`` when at least one preflight stage produced output."""

        return self.extraction is not None or self.query_plan is not None


@dataclass(slots=True)
class PreflightOrchestrator:
    """Sequence extraction and query planning according to supplied options."""

    extraction_service: ExtractionService
    query_service: QueryBuildingService

    def run(self, pipeline_input: PipelineInput, options: PreflightOptions) -> PreflightRunResult:
        """Execute preflight stages based on the provided options.

        Args:
            pipeline_input: Normalised corpus supplied to both services.
            options: Configuration toggles describing which stages to execute
                and how to label resulting artefacts.

        Returns:
            Populated :class:`PreflightRunResult` describing generated artefacts
            and recommended output paths.

        Raises:
            ValueError: If query building is requested without enabling
                extraction first.
            RuntimeError: Propagated from the underlying services when
                extraction or query planning fail.

        Side Effects:
            Delegates to services that may perform network I/O.

        Timeout:
            Not enforced. Callers should provide their own timeout management.
        """

        if options.enable_query_building and not options.enable_extraction:
            raise ValueError("Query building requires extraction to be enabled.")

        artifact_paths: Dict[str, str] = {}
        extraction_result: Optional[ExtractionResult] = None
        query_plan: Optional[QueryPlan] = None
        metadata_copy = dict(options.metadata)

        if options.enable_extraction:
            extraction_started = time.perf_counter()
            extraction_result = self.extraction_service.run(
                pipeline_input,
                max_points=options.max_points,
                metadata=metadata_copy or None,
            )
            extraction_duration_ms = (time.perf_counter() - extraction_started) * 1000.0
            _LOGGER.info(
                (
                    "event=preflight_extraction_summary points_count=%d "
                    "truncated=%s fallback_used=%s validation_error_count=%d time_ms=%.2f"
                ),
                len(extraction_result.points),
                str(extraction_result.truncated).lower(),
                str(bool(extraction_result.validation_errors)).lower(),
                len(extraction_result.validation_errors),
                extraction_duration_ms,
            )
            if options.extraction_artifact_name:
                artifact_paths["extraction"] = options.extraction_artifact_name

        if options.enable_query_building:
            query_started = time.perf_counter()
            query_plan = self.query_service.run(
                extraction_result,
                pipeline_input,
                max_queries=options.max_queries,
                metadata=metadata_copy or None,
            )
            query_duration_ms = (time.perf_counter() - query_started) * 1000.0
            dependencies_present = any(query.depends_on_ids for query in query_plan.queries)
            _LOGGER.info(
                (
                    "event=preflight_query_summary queries_count=%d "
                    "dependencies_present=%s fallback_used=%s validation_error_count=%d time_ms=%.2f"
                ),
                len(query_plan.queries),
                str(dependencies_present).lower(),
                str(bool(query_plan.validation_errors)).lower(),
                len(query_plan.validation_errors),
                query_duration_ms,
            )
            if options.query_artifact_name:
                artifact_paths["query_plan"] = options.query_artifact_name

        return PreflightRunResult(
            extraction=extraction_result,
            query_plan=query_plan,
            artifact_paths=artifact_paths,
        )


__all__ = ["PreflightOptions", "PreflightOrchestrator", "PreflightRunResult"]
