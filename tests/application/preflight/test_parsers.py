"""Parser validation tests for preflight extraction and query planning.

Purpose:
    Exercise the extraction and query plan parsers to ensure valid payloads
    produce domain models while invalid payloads generate fallback artefacts with
    structured validation feedback.
External Dependencies:
    Depends on project-local application and domain modules in addition to the
    Python standard library.
Fallback Semantics:
    Tests cover fallback behaviour by asserting the presence of raw responses and
    validation error messages when schema validation fails.
Timeout Strategy:
    Not applicable; parsing and validation are CPU-bound operations.
"""

from __future__ import annotations

import json
from typing import Sequence

from src.application.preflight.extraction_parser import ExtractionResponseParser
from src.application.preflight.query_parser import QueryPlanResponseParser
from src.application.preflight.schema_validation import ValidationIssue
from src.domain.preflight import ExtractionResult, QueryPlan


def _valid_extraction_payload() -> dict[str, object]:
    """Return a JSON-serialisable payload satisfying the extraction schema."""

    return {
        "points": [
            {
                "id": "alpha",
                "title": "Alpha",
                "summary": "Detailed summary",
                "evidence_refs": ["doc:1"],
                "confidence": 0.8,
                "tags": ["tag"],
            }
        ],
        "source_stats": {"chars": 1234},
        "truncated": False,
    }


def _valid_query_plan_payload() -> dict[str, object]:
    """Return a JSON-serialisable payload satisfying the query plan schema."""

    return {
        "queries": [
            {
                "id": "q1",
                "text": "Investigate alpha",
                "purpose": "Validate claim",
                "priority": 1,
                "depends_on_ids": ["seed"],
                "target_audience": "reviewer",
                "suggested_tooling": ["browser"],
            }
        ],
        "rationale": "Follow-up necessary",
        "assumptions": ["data is current"],
        "risks": ["evidence sparse"],
    }


def test_extraction_parser_returns_valid_model() -> None:
    """Ensure valid extraction payloads produce populated domain models."""

    parser = ExtractionResponseParser()
    payload = _valid_extraction_payload()
    result = parser.parse(json.dumps(payload))

    assert result.is_valid
    assert isinstance(result.model, ExtractionResult)
    assert result.model.points[0].id == "alpha"
    assert result.model.source_stats == {"chars": 1234}
    assert result.model.truncated is False


def test_extraction_parser_reports_validation_errors_and_fallback() -> None:
    """Verify invalid extraction payloads yield fallback artefacts with errors."""

    parser = ExtractionResponseParser()
    invalid_payload = json.dumps({"points": [], "source_stats": {}, "truncated": "no"})

    result = parser.parse(invalid_payload)

    assert not result.is_valid
    assert result.validation_errors
    assert isinstance(result.model, ExtractionResult)
    assert result.model.raw_response == invalid_payload
    assert result.model.validation_errors


def test_extraction_retry_message_lists_issues() -> None:
    """Ensure retry guidance enumerates validation issues with schema context."""

    parser = ExtractionResponseParser()
    issues: Sequence[ValidationIssue] = (
        ValidationIssue(path=("points", "0", "title"), message="Missing required property."),
    )

    message = parser.build_retry_message(issues)

    assert "extraction.schema.json" in message
    assert "Missing required property" in message
    assert message.endswith("Output only the corrected JSON with no extra commentary.")


def test_extraction_retry_message_handles_successful_response() -> None:
    """Ensure retry guidance explains that no issues remain when validation passes."""

    parser = ExtractionResponseParser()

    message = parser.build_retry_message(())

    assert message == "Previous response was valid; no retry guidance necessary."


def test_query_plan_parser_returns_valid_model() -> None:
    """Ensure valid query plan payloads produce populated domain models."""

    parser = QueryPlanResponseParser()
    payload = _valid_query_plan_payload()
    result = parser.parse(json.dumps(payload))

    assert result.is_valid
    assert isinstance(result.model, QueryPlan)
    assert result.model.queries[0].id == "q1"
    assert result.model.rationale == "Follow-up necessary"
    assert result.model.assumptions == ("data is current",)


def test_query_plan_parser_reports_validation_errors_and_fallback() -> None:
    """Verify invalid query plans yield fallback artefacts with errors."""

    parser = QueryPlanResponseParser()
    invalid_payload = json.dumps({"queries": [], "rationale": 1})

    result = parser.parse(invalid_payload)

    assert not result.is_valid
    assert result.validation_errors
    assert isinstance(result.model, QueryPlan)
    assert result.model.raw_response == invalid_payload
    assert result.model.validation_errors


def test_query_plan_retry_message_lists_issues() -> None:
    """Ensure retry guidance enumerates validation issues with schema context."""

    parser = QueryPlanResponseParser()
    issues: Sequence[ValidationIssue] = (
        ValidationIssue(path=("queries", "0", "priority"), message="priority must be an integer."),
    )

    message = parser.build_retry_message(issues)

    assert "query_plan.schema.json" in message
    assert "priority must be an integer" in message
    assert message.endswith("Output only the corrected JSON with no additional commentary.")


def test_query_plan_retry_message_handles_successful_response() -> None:
    """Ensure retry guidance explains that no issues remain when validation passes."""

    parser = QueryPlanResponseParser()

    message = parser.build_retry_message(())

    assert message == "Previous response was valid; no retry guidance necessary."
