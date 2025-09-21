"""Unit tests for the OpenAI-backed preflight gateways."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pytest

from src.domain.preflight import ExtractedPoint, ExtractionResult
from src.infrastructure.preflight.openai_gateway import (
    OpenAIPointExtractorGateway,
    OpenAIQueryBuilderGateway,
)
from src.pipeline_input import PipelineInput


LOGGER = logging.getLogger(__name__)


class DummyCall:
    """Test double that simulates the OpenAI client."""

    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses = iter(responses)
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self,
        *,
        prompt_template: str,
        context: Mapping[str, Any],
        config: Mapping[str, Any],
        is_structured: bool,
        system_message: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[Any, str]:
        """Return the next prepared response while recording invocation metadata.

        Args:
            prompt_template: User prompt supplied to the provider.
            context: Prompt rendering context (unused but recorded for tests).
            config: Provider configuration mapping forwarded by the gateway.
            is_structured: Flag indicating whether structured output is
                expected.
            system_message: Optional system prompt supplied by the gateway.
            **kwargs: Additional provider overrides such as ``max_tokens``.

        Returns:
            Tuple containing the prepared payload and a fixed model name.

        Raises:
            AssertionError: If the call is invoked more times than prepared
                responses.

        Side Effects:
            Appends metadata to ``self.calls`` for later inspection.

        Timeout:
            Not applicable.
        """

        self.calls.append(
            {
                "prompt": prompt_template,
                "context": dict(context),
                "config": dict(config),
                "is_structured": is_structured,
                "system": system_message,
                "overrides": dict(kwargs),
            }
        )
        try:
            payload = next(self._responses)
        except StopIteration:  # pragma: no cover - defensive
            raise AssertionError("DummyCall invoked more times than expected")
        return payload, "gpt-5"


def _make_valid_extraction_payload() -> Dict[str, Any]:
    """Return a payload that satisfies the extraction schema."""

    return {
        "points": [
            {
                "id": "p-1",
                "title": "Discovery",
                "summary": "Key finding summarised for downstream steps.",
                "evidence_refs": ["paper.md#L10"],
                "confidence": 0.9,
                "tags": ["physics"],
            }
        ],
        "source_stats": {"characters": 42},
        "truncated": False,
    }


def _make_valid_query_payload() -> Dict[str, Any]:
    """Return a payload that satisfies the query plan schema."""

    return {
        "queries": [
            {
                "id": "q-1",
                "text": "What experimental setups support the claim?",
                "purpose": "Validate experimental backing.",
                "priority": 1,
                "depends_on_ids": [],
                "target_audience": "reviewer",
                "suggested_tooling": ["web_search"],
            }
        ],
        "rationale": "Focus on reproducibility first.",
        "assumptions": [],
        "risks": ["Limited experimental details provided."],
    }


def test_point_extractor_success_single_attempt() -> None:
    LOGGER.info("Validating extractor returns structured result on first attempt.")
    """Verify success when the initial extraction attempt is valid.

    Returns:
        None.

    Raises:
        AssertionError: If the gateway does not return the expected point.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={})
    pipeline_input = PipelineInput(content="Example content", source="unit-test")

    result = gateway.extract_points(pipeline_input)

    assert len(call.calls) == 1
    assert result.points[0].id == "p-1"
    assert result.validation_errors == ()


def test_point_extractor_retries_on_validation_error() -> None:
    LOGGER.info("Ensuring extractor performs a retry after validation issues.")
    """Ensure a retry occurs when the first response fails validation.

    Returns:
        None.

    Raises:
        AssertionError: If the retry does not occur or the result is invalid.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    invalid = "{invalid json"
    call = DummyCall([invalid, _make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=1)
    pipeline_input = PipelineInput(content="Example content", source="unit-test")

    result = gateway.extract_points(pipeline_input)

    assert len(call.calls) == 2
    assert result.points[0].id == "p-1"
    assert result.validation_errors == ()


def test_point_extractor_returns_fallback_after_retry_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    LOGGER.info("Checking fallback metadata surfaces when retries remain invalid.")
    """Confirm the fallback artefact is returned when retries fail.

    Returns:
        None.

    Raises:
        AssertionError: If fallback metadata is not exposed as expected.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    invalid_first = "not json"
    invalid_second = json.dumps({"points": []})
    call = DummyCall([invalid_first, invalid_second])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=1)
    pipeline_input = PipelineInput(content="Example content", source="unit-test")

    caplog.set_level(logging.WARNING, logger="src.infrastructure.preflight.openai_gateway")
    result = gateway.extract_points(pipeline_input)

    assert len(call.calls) == 2
    assert result.points == ()
    assert result.raw_response == invalid_second
    assert result.validation_errors
    fallback_logs = [
        record.message
        for record in caplog.records
        if record.name == "src.infrastructure.preflight.openai_gateway"
    ]
    assert any("event=provider_fallback_returned" in message for message in fallback_logs)


def test_point_extractor_honours_metadata_overrides() -> None:
    LOGGER.info("Verifying metadata overrides propagate to provider parameters.")
    """Validate that metadata can override provider token limits.

    Returns:
        None.

    Raises:
        AssertionError: If the override is not forwarded to the provider call.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=0)
    pipeline_input = PipelineInput(content="Example content", source="unit-test")

    gateway.extract_points(
        pipeline_input,
        metadata={"max_output_tokens": 1234},
    )

    assert call.calls[0]["overrides"]["max_tokens"] == 1234


def test_query_builder_successful_execution() -> None:
    LOGGER.info("Validating query builder parses successful payloads without retries.")
    """Verify successful query plan parsing without retries.

    Returns:
        None.

    Raises:
        AssertionError: If the parsed plan does not match expectations.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall([_make_valid_query_payload()])
    gateway = OpenAIQueryBuilderGateway(call_model=call, config={})
    extraction = ExtractionResult(
        points=(
            ExtractedPoint(
                id="p-1",
                title="Discovery",
                summary="Key finding",
                evidence_refs=("paper.md#L10",),
                confidence=0.9,
            ),
        )
    )

    plan = gateway.build_queries(extraction)

    assert len(call.calls) == 1
    assert plan.queries[0].id == "q-1"
    assert plan.validation_errors == ()


def test_query_builder_retries_before_fallback(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Ensuring query builder logs fallback usage when validation continues failing.")
    """Ensure query builder retries and returns fallback when still invalid.

    Returns:
        None.

    Raises:
        AssertionError: If retries or fallback behaviour are incorrect.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall(["not json", "{}"])  # Second payload lacks required fields
    gateway = OpenAIQueryBuilderGateway(call_model=call, config={}, max_retries=1)
    extraction = ExtractionResult(points=())

    caplog.set_level(logging.WARNING, logger="src.infrastructure.preflight.openai_gateway")
    plan = gateway.build_queries(extraction)

    assert len(call.calls) == 2
    assert plan.queries == ()
    assert plan.raw_response == "{}"
    assert plan.validation_errors
    fallback_logs = [
        record.message
        for record in caplog.records
        if record.name == "src.infrastructure.preflight.openai_gateway"
    ]
    assert any(
        "event=provider_fallback_returned" in message and "operation=preflight_query_planning" in message
        for message in fallback_logs
    )


def test_point_extractor_logs_timeout_error(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Verifying timeout errors emit structured provider diagnostics.")

    def raising_call(**_: Any) -> Tuple[Any, str]:
        raise TimeoutError("simulated timeout")

    gateway = OpenAIPointExtractorGateway(call_model=raising_call, config={}, max_retries=0)
    pipeline_input = PipelineInput(content="Example content", source="unit-test")

    caplog.set_level(logging.ERROR, logger="src.infrastructure.preflight.openai_gateway")
    with pytest.raises(TimeoutError):
        gateway.extract_points(pipeline_input)

    error_logs = [
        record.message
        for record in caplog.records
        if record.name == "src.infrastructure.preflight.openai_gateway"
    ]
    failure = next(msg for msg in error_logs if "event=provider_call_failed" in msg)
    assert "operation=preflight_extraction" in failure
    assert "failure_class=TimeoutError" in failure
    assert "fallback_used=false" in failure
