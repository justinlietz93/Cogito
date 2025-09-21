"""Unit tests for the OpenAI-backed preflight gateways."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pytest

from src.domain.preflight import ExtractedPoint, ExtractionResult
from src.infrastructure.preflight.openai_gateway import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    OpenAIPointExtractorGateway,
    OpenAIQueryBuilderGateway,
)
from src.pipeline_input import PipelineInput


LOGGER = logging.getLogger(__name__)

LONG_CONTENT = "Example content " * 6


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


def test_point_extractor_returns_empty_result_for_blank_input() -> None:
    LOGGER.info("Verifying extractor short-circuits for empty pipeline input.")
    """Ensure blank content returns no points without contacting the provider."""

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={})
    pipeline_input = PipelineInput(content="   ", source="unit-test")

    result = gateway.extract_points(pipeline_input)

    assert call.calls == []
    assert result.points == ()
    assert result.validation_errors == ()
    assert result.truncated is False
    assert result.source_stats["skip_reason"] == "empty_content"


def test_point_extractor_skips_when_content_below_threshold() -> None:
    LOGGER.info("Ensuring extractor avoids model calls for very small content blocks.")
    """Confirm minimal content triggers a skipped result with diagnostics."""

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={})
    pipeline_input = PipelineInput(content="Short summary.", source="unit-test")

    result = gateway.extract_points(pipeline_input)

    assert call.calls == []
    assert result.points == ()
    assert result.validation_errors == ()
    assert result.truncated is False
    assert result.source_stats["skip_reason"] == "content_below_min_threshold"


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
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

    result = gateway.extract_points(pipeline_input)

    assert len(call.calls) == 1
    assert result.points[0].id == "p-1"
    assert result.validation_errors == ()


def test_point_extractor_marks_truncated_when_limit_reached() -> None:
    LOGGER.info("Checking extractor flags truncation when limits cap the output size.")
    """Ensure hitting max_points marks the extraction result as truncated."""

    payload = _make_valid_extraction_payload()
    payload["truncated"] = False
    call = DummyCall([payload])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=0)
    pipeline_input = PipelineInput(content="Long content " * 20, source="unit-test")

    result = gateway.extract_points(pipeline_input, max_points=1)

    assert result.truncated is True
    assert result.source_stats["characters"] == len(pipeline_input.content)


def test_point_extractor_chunks_large_inputs() -> None:
    LOGGER.info("Validating chunked extraction splits oversized inputs into multiple calls.")
    """Ensure large inputs trigger chunked processing with aggregated results."""

    first_payload = _make_valid_extraction_payload()
    first_payload["points"][0]["id"] = "chunk-1"
    first_payload["points"][0]["title"] = "Chunk 1"
    first_payload["points"][0]["summary"] = "Summary for the first chunk."
    second_payload = _make_valid_extraction_payload()
    second_payload["points"][0]["id"] = "chunk-2"
    second_payload["points"][0]["title"] = "Chunk 2"
    second_payload["points"][0]["summary"] = "Summary for the second chunk."
    call = DummyCall([first_payload, second_payload])
    config = {
        "preflight": {
            "extract": {
                "chunking": {
                    "max_characters": 120,
                    "overlap_characters": 0,
                    "max_points_per_chunk": 2,
                }
            }
        }
    }
    gateway = OpenAIPointExtractorGateway(call_model=call, config=config, max_retries=0)
    content = (
        "Chunk-one sentinel paragraph describing the first portion of the corpus.\n\n"
        "Chunk-two sentinel paragraph highlighting the remaining context to ensure chunking."
    )
    pipeline_input = PipelineInput(content=content, source="unit-test")

    result = gateway.extract_points(pipeline_input, max_points=4)

    assert len(call.calls) == 2
    assert {point.id for point in result.points} == {"chunk-1", "chunk-2"}
    stats = result.source_stats["chunking"]
    assert stats["chunk_count"] == 2
    assert stats["map_points_before_merge"] == 2
    assert stats["selected_points"] == 2
    assert result.source_stats["characters"] == len(content)


def test_point_extractor_chunking_enforces_global_limit() -> None:
    LOGGER.info("Ensuring chunked extraction honours the global max_points setting.")
    """Verify chunked outputs are trimmed to the configured global limit."""

    lower_confidence = _make_valid_extraction_payload()
    lower_confidence["points"][0]["id"] = "chunk-low"
    lower_confidence["points"][0]["confidence"] = 0.4
    lower_confidence["points"][0]["title"] = "Lower confidence chunk"
    lower_confidence["points"][0]["summary"] = "Details originating from the lower-confidence segment."
    higher_confidence = _make_valid_extraction_payload()
    higher_confidence["points"][0]["id"] = "chunk-high"
    higher_confidence["points"][0]["confidence"] = 0.95
    higher_confidence["points"][0]["title"] = "Higher confidence chunk"
    higher_confidence["points"][0]["summary"] = "Findings captured in the higher-confidence segment."
    call = DummyCall([lower_confidence, higher_confidence])
    config = {
        "preflight": {
            "extract": {
                "chunking": {
                    "max_characters": 90,
                    "overlap_characters": 0,
                    "max_points_per_chunk": 2,
                }
            }
        }
    }
    gateway = OpenAIPointExtractorGateway(call_model=call, config=config, max_retries=0)
    content = (
        "A detailed first section discussing requirements and findings.\n\n"
        "A follow-up section providing additional corroborating details."
    )
    pipeline_input = PipelineInput(content=content, source="unit-test")

    result = gateway.extract_points(pipeline_input, max_points=1)

    assert len(call.calls) == 2
    assert len(result.points) == 1
    assert result.points[0].id == "chunk-high"
    assert result.truncated is True
    stats = result.source_stats["chunking"]
    assert stats["unique_candidates"] == 2
    assert stats["selected_points"] == 1
    assert stats["global_point_limit"] == 1


def test_point_extractor_chunking_aggregates_validation_errors() -> None:
    LOGGER.info("Checking chunked extraction surfaces validation errors from individual chunks.")
    """Confirm fallback metadata from chunk retries is propagated to the aggregate result."""

    invalid_payload = "not-json"
    valid_payload = _make_valid_extraction_payload()
    call = DummyCall([invalid_payload, valid_payload])
    config = {
        "preflight": {
            "extract": {
                "chunking": {
                    "max_characters": 90,
                    "overlap_characters": 0,
                    "max_points_per_chunk": 1,
                }
            }
        }
    }
    gateway = OpenAIPointExtractorGateway(call_model=call, config=config, max_retries=0)
    content = (
        "First section intentionally triggers fallback handling.\n\n"
        "Second section remains valid and should populate the final result."
    )
    pipeline_input = PipelineInput(content=content, source="unit-test")

    result = gateway.extract_points(pipeline_input)

    assert len(call.calls) == 2
    assert len(result.points) == 1
    assert result.validation_errors
    assert any(message.startswith("chunk[1]:") for message in result.validation_errors)
    assert result.source_stats["chunking"]["fallback_chunks"] == 1
    assert result.raw_response is not None
    fallback_payload = json.loads(result.raw_response)
    assert fallback_payload["chunk_fallbacks"][0]["index"] == 0
    assert fallback_payload["chunk_fallbacks"][0]["raw_response"] == invalid_payload


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
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

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
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

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


def test_point_extractor_emits_single_fallback_log(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Validating fallback logging occurs exactly once per extraction run.")
    """Ensure fallback diagnostics are emitted a single time when retries fail."""

    invalid_first = "not json"
    invalid_second = json.dumps({"points": []})
    call = DummyCall([invalid_first, invalid_second])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=1)
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

    caplog.set_level(logging.WARNING, logger="src.infrastructure.preflight.openai_gateway")
    result = gateway.extract_points(pipeline_input)

    fallback_logs = [
        record.message
        for record in caplog.records
        if "event=provider_fallback_returned" in record.message
    ]
    assert len(fallback_logs) == 1
    assert result.validation_errors


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
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

    gateway.extract_points(
        pipeline_input,
        metadata={"max_output_tokens": 1234},
    )

    assert call.calls[0]["overrides"]["max_tokens"] == 1234


def test_point_extractor_applies_configured_token_cap() -> None:
    LOGGER.info("Ensuring extractor forwards configured max token caps to the provider.")
    """Verify that configuration defaults restrict provider token emission.

    Returns:
        None.

    Raises:
        AssertionError: If the configured token cap is not forwarded to the
            provider invocation.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(
        call_model=call,
        config={"api": {"openai": {"max_tokens": 2048}}},
        max_retries=0,
    )
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

    gateway.extract_points(pipeline_input)

    assert call.calls[0]["overrides"]["max_tokens"] == 2048


def test_point_extractor_uses_default_token_cap_when_missing() -> None:
    LOGGER.info("Confirming extractor falls back to the default max token limit.")
    """Ensure the fallback token cap applies when configuration omits a value.

    Returns:
        None.

    Raises:
        AssertionError: If the default token cap is not forwarded to the
            provider invocation.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=0)
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

    gateway.extract_points(pipeline_input)

    assert call.calls[0]["overrides"]["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS


def test_gateway_logs_exclude_sensitive_values(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Ensuring gateway logs omit sensitive content and secret values.")
    """Confirm provider logging excludes pipeline content and API keys.

    Args:
        caplog: Pytest fixture for capturing log output during execution.

    Returns:
        None.

    Raises:
        AssertionError: If any captured log message contains sensitive
            substrings such as pipeline content or API keys.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    call = DummyCall([_make_valid_extraction_payload()])
    gateway = OpenAIPointExtractorGateway(call_model=call, config={}, max_retries=0)
    pipeline_input = PipelineInput(
        content="Secret corpus body",
        source="unit-test",
        metadata={"api_key": "sk-input"},
    )
    metadata = {
        "api_key": "sk-meta",
        "provider_overrides": {"api_key": "sk-override"},
    }

    caplog.set_level(logging.INFO, logger="src.infrastructure.preflight.openai_gateway")
    gateway.extract_points(pipeline_input, metadata=metadata)

    sensitive_strings = {"Secret corpus body", "sk-input", "sk-meta", "sk-override"}
    for record in caplog.records:
        if record.name == "src.infrastructure.preflight.openai_gateway":
            message = record.getMessage()
            for value in sensitive_strings:
                assert value not in message


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
    pipeline_input = PipelineInput(content=LONG_CONTENT, source="unit-test")

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
