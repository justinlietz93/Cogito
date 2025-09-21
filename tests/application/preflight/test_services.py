"""Tests covering the preflight application services.

Purpose:
    Validate that ``ExtractionService`` and ``QueryBuildingService`` orchestrate
    gateway interactions by enforcing limit validation, applying defaults, and
    isolating caller-provided metadata.
External Dependencies:
    Relies on ``pytest`` and project-local domain/application modules only.
Fallback Semantics:
    Exercises service behaviour without simulating gateway fallbacks; tests focus
    on ensuring that services propagate gateway results transparently.
Timeout Strategy:
    No timeouts are triggered during these tests. Blocking operations are not
    performed because gateways are replaced with in-memory stubs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

import pytest

from src.application.preflight.services import ExtractionService, QueryBuildingService
from src.domain.preflight import ExtractionResult, QueryPlan
from src.pipeline_input import PipelineInput


@dataclass(slots=True)
class StubPointExtractor:
    """Capture invocations made by :class:`ExtractionService` for assertions.

    Attributes:
        result: Extraction result instance returned for every invocation.
        calls: Sequence capturing dictionaries of call metadata for assertions.
    """

    result: ExtractionResult
    calls: List[Dict[str, object]]

    def __init__(self, result: ExtractionResult) -> None:
        """Initialise the stub with a precomputed result and empty call log.

        Args:
            result: Precomputed extraction result returned to the caller.

        Returns:
            None.

        Raises:
            None.

        Side Effects:
            Initialises the ``calls`` list used for assertions.

        Timeout:
            Not applicable.
        """

        self.result = result
        self.calls = []

    def extract_points(
        self,
        pipeline_input: PipelineInput,
        *,
        max_points: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> ExtractionResult:
        """Store call arguments and return the configured result.

        Args:
            pipeline_input: Pipeline input instance supplied by the service.
            max_points: Optional limit forwarded from the service under test.
            metadata: Optional metadata mapping passed by the service.

        Returns:
            The preconfigured :class:`ExtractionResult` object.

        Raises:
            None.

        Side Effects:
            Appends a dictionary describing the invocation to ``calls`` for
            later inspection.

        Timeout:
            Not applicable.
        """

        self.calls.append(
            {
                "pipeline_input": pipeline_input,
                "max_points": max_points,
                "metadata": metadata,
            }
        )
        return self.result


@dataclass(slots=True)
class StubQueryBuilder:
    """Capture invocations made by :class:`QueryBuildingService` for assertions.

    Attributes:
        result: Query plan instance returned to callers for every invocation.
        calls: Sequence capturing dictionaries of call metadata for assertions.
    """

    result: QueryPlan
    calls: List[Dict[str, object]]

    def __init__(self, result: QueryPlan) -> None:
        """Initialise the stub with a precomputed result and empty call log.

        Args:
            result: Precomputed query plan returned to callers.

        Returns:
            None.

        Raises:
            None.

        Side Effects:
            Initialises the ``calls`` list used to assert invocation data.

        Timeout:
            Not applicable.
        """

        self.result = result
        self.calls = []

    def build_queries(
        self,
        extraction: ExtractionResult,
        pipeline_input: Optional[PipelineInput] = None,
        *,
        max_queries: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> QueryPlan:
        """Store call arguments and return the configured result.

        Args:
            extraction: Extraction result forwarded by the service under test.
            pipeline_input: Optional pipeline input forwarded by the service.
            max_queries: Optional limit forwarded by the service.
            metadata: Optional metadata mapping provided by the service.

        Returns:
            The preconfigured :class:`QueryPlan` object.

        Raises:
            None.

        Side Effects:
            Appends a dictionary describing the invocation to ``calls`` for
            later inspection.

        Timeout:
            Not applicable.
        """

        self.calls.append(
            {
                "extraction": extraction,
                "pipeline_input": pipeline_input,
                "max_queries": max_queries,
                "metadata": metadata,
            }
        )
        return self.result


def test_extraction_service_uses_override_and_copies_metadata() -> None:
    """Ensure overrides take precedence and metadata is defensively copied.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If the override limit or metadata copy behaviour is
            incorrect.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    pipeline_input = PipelineInput(content="example")
    metadata: Dict[str, object] = {"run": "abc"}
    result = ExtractionResult()
    stub = StubPointExtractor(result)
    service = ExtractionService(gateway=stub, default_max_points=3)

    returned = service.run(pipeline_input, max_points=5, metadata=metadata)

    assert returned is result
    assert stub.calls[0]["pipeline_input"] is pipeline_input
    assert stub.calls[0]["max_points"] == 5
    assert stub.calls[0]["metadata"] == {"run": "abc"}
    assert stub.calls[0]["metadata"] is not metadata
    metadata["run"] = "changed"
    assert stub.calls[0]["metadata"] == {"run": "abc"}


def test_extraction_service_rejects_non_positive_limits() -> None:
    """Verify that invalid limits raise ``ValueError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If ``ValueError`` is not raised as expected.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    pipeline_input = PipelineInput(content="example")
    stub = StubPointExtractor(ExtractionResult())
    service = ExtractionService(gateway=stub)

    with pytest.raises(ValueError):
        service.run(pipeline_input, max_points=0)


def test_query_service_applies_default_limit_when_override_missing() -> None:
    """Ensure default limits are used when explicit overrides are absent.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If the default limit is not forwarded to the gateway.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    extraction = ExtractionResult()
    query_plan = QueryPlan()
    stub = StubQueryBuilder(query_plan)
    service = QueryBuildingService(gateway=stub, default_max_queries=7)

    returned = service.run(extraction)

    assert returned is query_plan
    assert stub.calls[0]["extraction"] is extraction
    assert stub.calls[0]["pipeline_input"] is None
    assert stub.calls[0]["max_queries"] == 7
    assert stub.calls[0]["metadata"] is None


def test_query_service_rejects_non_positive_limits() -> None:
    """Verify that invalid query limits raise ``ValueError``.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If ``ValueError`` is not raised as expected.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    extraction = ExtractionResult()
    stub = StubQueryBuilder(QueryPlan())
    service = QueryBuildingService(gateway=stub)

    with pytest.raises(ValueError):
        service.run(extraction, max_queries=0)

def test_extraction_service_preserves_truncated_results() -> None:
    """Confirm truncated results from the gateway propagate without mutation.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If the service fails to return the truncated artefact as
            provided by the gateway stub.

    Side Effects:
        None.

    Timeout:
        Not applicable; the stub executes synchronously.
    """

    pipeline_input = PipelineInput(content="example")
    result = ExtractionResult(truncated=True)
    stub = StubPointExtractor(result)
    service = ExtractionService(gateway=stub)

    returned = service.run(pipeline_input)

    assert returned is result
    assert returned.truncated is True
