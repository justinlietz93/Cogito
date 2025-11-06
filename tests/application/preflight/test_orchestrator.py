"""Tests for the preflight orchestrator sequencing extraction and query planning.

Purpose:
    Validate that :class:`PreflightOrchestrator` delegates to the extraction and
    query building services according to the supplied options while capturing
    artefact metadata.
External Dependencies:
    Uses ``pytest`` and standard library modules only, alongside project-local
    application and domain packages.
Fallback Semantics:
    The tests rely on stub gateways that do not trigger fallback behaviours.
Timeout Strategy:
    No blocking operations are performed; timeouts are not exercised.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import pytest

from src.application.preflight.orchestrator import PreflightOptions, PreflightOrchestrator
from src.application.preflight.services import ExtractionService, QueryBuildingService
from src.domain.preflight import BuiltQuery, ExtractedPoint, ExtractionResult, QueryPlan
from src.pipeline_input import PipelineInput

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _StubExtractorGateway:
    """Record interactions from :class:`ExtractionService` for assertions."""

    result: ExtractionResult
    calls: List[Dict[str, object]]

    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.calls = []

    def extract_points(
        self,
        pipeline_input: PipelineInput,
        *,
        max_points: Optional[int] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ExtractionResult:
        self.calls.append(
            {
                "input": pipeline_input,
                "max_points": max_points,
                "metadata": metadata,
            }
        )
        return self.result


@dataclass(slots=True)
class _StubQueryGateway:
    """Record interactions from :class:`QueryBuildingService` for assertions."""

    result: QueryPlan
    calls: List[Dict[str, object]]

    def __init__(self, result: QueryPlan) -> None:
        self.result = result
        self.calls = []

    def build_queries(
        self,
        extraction: ExtractionResult,
        pipeline_input: Optional[PipelineInput] = None,
        *,
        max_queries: Optional[int] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> QueryPlan:
        self.calls.append(
            {
                "extraction": extraction,
                "pipeline_input": pipeline_input,
                "max_queries": max_queries,
                "metadata": metadata,
            }
        )
        return self.result


def _build_extraction_result() -> ExtractionResult:
    point = ExtractedPoint(
        id="p1",
        title="Point",
        summary="Summary",
        evidence_refs=("ref",),
        confidence=0.9,
        tags=("tag",),
    )
    return ExtractionResult(points=(point,))


def _build_query_plan() -> QueryPlan:
    query = BuiltQuery(
        id="q1",
        text="What next?",
        purpose="Explore",
        priority=1,
        depends_on_ids=(),
        target_audience=None,
        suggested_tooling=(),
    )
    return QueryPlan(queries=(query,), rationale="Plan")


def test_run_no_stages_returns_empty_result() -> None:
    LOGGER.info("Ensuring orchestrator returns empty results when no stages are enabled.")
    extractor = ExtractionService(gateway=_StubExtractorGateway(_build_extraction_result()))
    query_builder = QueryBuildingService(gateway=_StubQueryGateway(_build_query_plan()))
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(content="body")

    result = orchestrator.run(pipeline_input, PreflightOptions())

    assert result.extraction is None
    assert result.query_plan is None
    assert result.artifact_paths == {}


def test_run_with_extraction_only() -> None:
    LOGGER.info("Verifying extraction stage runs in isolation and registers default artefact path.")
    extraction_result = _build_extraction_result()
    extractor_gateway = _StubExtractorGateway(extraction_result)
    extractor = ExtractionService(gateway=extractor_gateway)
    query_builder = QueryBuildingService(gateway=_StubQueryGateway(_build_query_plan()))
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(content="body")

    options = PreflightOptions(enable_extraction=True, max_points=5)
    result = orchestrator.run(pipeline_input, options)

    assert result.extraction == extraction_result
    assert result.query_plan is None
    assert result.artifact_paths == {"extraction": "artifacts/points.json"}
    assert extractor_gateway.calls[0]["max_points"] == 5
    assert extractor_gateway.calls[0]["metadata"] is None


def test_run_with_extraction_and_query_custom_paths() -> None:
    LOGGER.info("Ensuring both stages execute and artefact paths honour custom configuration.")
    extraction_result = _build_extraction_result()
    query_plan = _build_query_plan()
    extractor_gateway = _StubExtractorGateway(extraction_result)
    query_gateway = _StubQueryGateway(query_plan)
    extractor = ExtractionService(gateway=extractor_gateway)
    query_builder = QueryBuildingService(gateway=query_gateway)
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(content="body")

    options = PreflightOptions(
        enable_extraction=True,
        enable_query_building=True,
        max_points=2,
        max_queries=3,
        metadata={"run_id": "abc"},
        extraction_artifact_name="artifacts/custom_points.json",
        query_artifact_name="artifacts/custom_queries.json",
    )
    result = orchestrator.run(pipeline_input, options)

    assert result.extraction == extraction_result
    assert result.query_plan == query_plan
    assert result.artifact_paths == {
        "extraction": "artifacts/custom_points.json",
        "query_plan": "artifacts/custom_queries.json",
    }
    assert extractor_gateway.calls[0]["metadata"] == {"run_id": "abc"}
    assert query_gateway.calls[0]["max_queries"] == 3
    assert query_gateway.calls[0]["metadata"] == {"run_id": "abc"}
    assert query_gateway.calls[0]["extraction"] is extraction_result


def test_run_raises_when_query_enabled_without_extraction() -> None:
    LOGGER.info("Validating query building without extraction raises a configuration error.")
    extractor = ExtractionService(gateway=_StubExtractorGateway(_build_extraction_result()))
    query_builder = QueryBuildingService(gateway=_StubQueryGateway(_build_query_plan()))
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(content="body")

    with pytest.raises(ValueError):
        orchestrator.run(pipeline_input, PreflightOptions(enable_query_building=True))


def test_run_logs_extraction_summary(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Confirming extraction summary logs include counts and timing metadata.")
    extraction_result = _build_extraction_result()
    extractor = ExtractionService(gateway=_StubExtractorGateway(extraction_result))
    query_builder = QueryBuildingService(gateway=_StubQueryGateway(_build_query_plan()))
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(content="body")

    caplog.set_level(logging.INFO, logger="src.application.preflight.orchestrator")
    orchestrator.run(pipeline_input, PreflightOptions(enable_extraction=True))

    messages = [
        record.message
        for record in caplog.records
        if record.name == "src.application.preflight.orchestrator"
    ]
    summary = next(msg for msg in messages if msg.startswith("event=preflight_extraction_summary"))
    assert "points_count=1" in summary
    assert "truncated=false" in summary
    assert "time_ms=" in summary


def test_run_logs_query_summary(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Validating query summary logs capture dependency information.")
    extraction_result = _build_extraction_result()
    dependent_query = BuiltQuery(
        id="q1",
        text="Follow-up?",
        purpose="Assess",
        priority=1,
        depends_on_ids=("q0",),
    )
    query_plan = QueryPlan(queries=(dependent_query,), rationale="Plan")
    extractor_gateway = _StubExtractorGateway(extraction_result)
    query_gateway = _StubQueryGateway(query_plan)
    extractor = ExtractionService(gateway=extractor_gateway)
    query_builder = QueryBuildingService(gateway=query_gateway)
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(content="body")

    caplog.set_level(logging.INFO, logger="src.application.preflight.orchestrator")
    orchestrator.run(
        pipeline_input,
        PreflightOptions(enable_extraction=True, enable_query_building=True),
    )

    messages = [
        record.message
        for record in caplog.records
        if record.name == "src.application.preflight.orchestrator"
    ]
    summary = next(msg for msg in messages if msg.startswith("event=preflight_query_summary"))
    assert "queries_count=1" in summary
    assert "dependencies_present=true" in summary
    assert "time_ms=" in summary


def test_run_logs_exclude_sensitive_values(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Ensuring orchestrator logs avoid leaking pipeline content or secrets.")
    """Validate that orchestrator summary logs do not include sensitive metadata.

    Args:
        caplog: Pytest fixture used to capture logging records for assertions.

    Returns:
        None.

    Raises:
        AssertionError: If sensitive values such as corpus content or API keys
            appear in the log records.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    extraction_result = _build_extraction_result()
    extractor = ExtractionService(gateway=_StubExtractorGateway(extraction_result))
    query_builder = QueryBuildingService(gateway=_StubQueryGateway(_build_query_plan()))
    orchestrator = PreflightOrchestrator(extractor, query_builder)
    pipeline_input = PipelineInput(
        content="Highly sensitive body text",
        metadata={"api_key": "sk-test"},
    )

    caplog.set_level(logging.INFO, logger="src.application.preflight.orchestrator")
    orchestrator.run(
        pipeline_input,
        PreflightOptions(
            enable_extraction=True,
            enable_query_building=True,
            metadata={"api_key": "sk-live-123", "run_id": "test-run"},
        ),
    )

    sensitive_strings = {"Highly sensitive body text", "sk-test", "sk-live-123"}
    for record in caplog.records:
        if record.name == "src.application.preflight.orchestrator":
            message = record.getMessage()
            for value in sensitive_strings:
                assert value not in message
