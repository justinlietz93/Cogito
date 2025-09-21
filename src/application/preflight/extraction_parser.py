"""Extraction response parsing utilities for preflight workflows.

Purpose:
    Validate structured extraction outputs returned by language models and
    convert them into immutable domain objects. The module encapsulates the
    validation rules for :class:`~src.domain.preflight.ExtractionResult` so that
    orchestration services can remain concise.
External Dependencies:
    Python standard library modules ``textwrap`` and ``typing`` together with
    local schema validation helpers.
Fallback Semantics:
    The parser reports structured validation issues and, when validation fails,
    produces fallback artefacts that capture the raw provider response alongside
    formatted error messages. Callers can persist the fallback output while
    signalling that schema validation failed.
Timeout Strategy:
    Not applicable; all operations are CPU-bound and operate on in-memory data.
"""

from __future__ import annotations

import textwrap
from typing import Any, Mapping, Optional, Sequence, Tuple

from ...domain.preflight import ExtractedPoint, ExtractionResult
from .schema_validation import (
    StructuredParseResult,
    ValidationIssue,
    parse_json_payload,
    reject_additional_keys,
    require_keys,
    validate_string_array,
)


def _validate_extracted_point(
    point: Any,
    *,
    index: int,
    issues: list[ValidationIssue],
) -> Optional[ExtractedPoint]:
    """Validate and convert a potential extracted point payload.

    Args:
        point: Candidate point payload.
        index: Zero-based index of the point inside the ``points`` array.
        issues: Mutable list that accumulates validation problems.

    Returns:
        :class:`ExtractedPoint` when validation succeeds, otherwise ``None``.

    Raises:
        None. Validation issues are appended to ``issues``.

    Side Effects:
        Appends :class:`ValidationIssue` entries to ``issues`` when validation
        fails.

    Timeout:
        Not applicable; the function processes in-memory data synchronously.
    """

    path = ("points", str(index))
    if not isinstance(point, Mapping):
        issues.append(
            ValidationIssue(
                path=path,
                message="Each point must be an object with the documented properties.",
            )
        )
        return None

    required = ["id", "title", "summary", "evidence_refs", "confidence"]
    allowed = ["id", "title", "summary", "evidence_refs", "confidence", "tags"]
    require_keys(point, required, path=path, issues=issues)
    reject_additional_keys(point, allowed, path=path, issues=issues)

    tags: Tuple[str, ...] = ()
    if "tags" in point:
        tags = validate_string_array(point["tags"], path=path + ("tags",), issues=issues)

    evidence_refs: Tuple[str, ...] = ()
    if "evidence_refs" in point:
        evidence_refs = validate_string_array(
            point["evidence_refs"],
            path=path + ("evidence_refs",),
            issues=issues,
            allow_empty=True,
        )

    confidence_value = point.get("confidence")
    if isinstance(confidence_value, (int, float)):
        confidence = float(confidence_value)
        if not 0.0 <= confidence <= 1.0:
            issues.append(
                ValidationIssue(
                    path=path + ("confidence",),
                    message="Confidence must be between 0.0 and 1.0.",
                )
            )
    else:
        issues.append(
            ValidationIssue(
                path=path + ("confidence",),
                message="Confidence must be a numeric value between 0.0 and 1.0.",
            )
        )
        confidence = 0.0

    id_value = point.get("id")
    title_value = point.get("title")
    summary_value = point.get("summary")
    for key, value in ("id", id_value), ("title", title_value), ("summary", summary_value):
        if not isinstance(value, str) or not value.strip():
            issues.append(
                ValidationIssue(
                    path=path + (key,),
                    message="Value must be a non-empty string.",
                )
            )

    if any(issue.path[:2] == path[:2] for issue in issues):
        return None

    return ExtractedPoint(
        id=str(id_value),
        title=str(title_value),
        summary=str(summary_value),
        evidence_refs=evidence_refs,
        confidence=confidence,
        tags=tags,
    )


def _format_validation_messages(issues: Sequence[ValidationIssue]) -> Tuple[str, ...]:
    """Return formatted string representations of validation issues.

    Args:
        issues: Validation problems raised while parsing model output.

    Returns:
        Tuple containing human-readable error descriptions. An empty tuple is
        returned when ``issues`` is empty.

    Raises:
        None.

    Side Effects:
        None. The function performs deterministic string formatting.

    Timeout:
        Not applicable; execution is CPU-bound and synchronous.
    """

    return tuple(issue.format() for issue in issues)


def _build_fallback_result(
    raw_text: str,
    issues: Sequence[ValidationIssue],
) -> ExtractionResult:
    """Construct a fallback extraction result from invalid structured output.

    Args:
        raw_text: Original response returned by the language model.
        issues: Validation problems detected while parsing ``raw_text``.

    Returns:
        :class:`ExtractionResult` instance containing no structured points but
        preserving the raw response and formatted validation errors for
        observability purposes.

    Raises:
        None.

    Side Effects:
        None. A new domain object is created based solely on the provided data.

    Timeout:
        Not applicable; the function operates on in-memory data only.
    """

    return ExtractionResult(
        points=(),
        source_stats={},
        truncated=False,
        raw_response=raw_text,
        validation_errors=_format_validation_messages(issues),
    )


def _validate_extraction_payload(payload: Any) -> Tuple[ValidationIssue, ...]:
    """Return validation issues for a potential extraction payload."""

    issues: list[ValidationIssue] = []
    if not isinstance(payload, Mapping):
        issues.append(
            ValidationIssue(
                path=(),
                message="Root payload must be a JSON object.",
            )
        )
        return tuple(issues)

    required = ["points", "source_stats", "truncated"]
    allowed = required
    require_keys(payload, required, path=(), issues=issues)
    reject_additional_keys(payload, allowed, path=(), issues=issues)

    points_value = payload.get("points")
    if isinstance(points_value, Sequence) and not isinstance(points_value, (str, bytes)):
        for index, point in enumerate(points_value):
            _validate_extracted_point(point, index=index, issues=issues)
    else:
        issues.append(
            ValidationIssue(
                path=("points",),
                message="Points must be an array of objects.",
            )
        )

    source_stats = payload.get("source_stats")
    if not isinstance(source_stats, Mapping):
        issues.append(
            ValidationIssue(
                path=("source_stats",),
                message="source_stats must be an object (can be empty).",
            )
        )

    truncated_value = payload.get("truncated")
    if not isinstance(truncated_value, bool):
        issues.append(
            ValidationIssue(
                path=("truncated",),
                message="truncated must be a boolean flag.",
            )
        )

    return tuple(issues)


def _convert_to_extraction_result(payload: Mapping[str, Any]) -> ExtractionResult:
    """Convert a validated payload to :class:`ExtractionResult`."""

    points_payload = payload.get("points", [])
    points = tuple(
        ExtractedPoint(
            id=str(point["id"]),
            title=str(point["title"]),
            summary=str(point["summary"]),
            evidence_refs=tuple(str(item) for item in point.get("evidence_refs", [])),
            confidence=float(point["confidence"]),
            tags=tuple(str(item) for item in point.get("tags", [])),
        )
        for point in points_payload
    )
    source_stats = payload.get("source_stats")
    return ExtractionResult(
        points=points,
        source_stats=dict(source_stats or {}),
        truncated=bool(payload.get("truncated", False)),
    )


class ExtractionResponseParser:
    """Parser that validates extraction responses and emits domain objects."""

    def __init__(self, *, schema_name: str = "extraction.schema.json") -> None:
        self._schema_name = schema_name

    def parse(self, raw_text: str) -> StructuredParseResult[ExtractionResult]:
        """Parse and validate an extraction response payload.

        Args:
            raw_text: Raw string returned by the language model invocation.

        Returns:
            :class:`StructuredParseResult` capturing the parsed payload, detected
            validation issues, and a populated :class:`ExtractionResult` when
            validation succeeds. When validation fails the returned result still
            includes an :class:`ExtractionResult` carrying fallback metadata so
            callers can persist the raw response alongside formatted error
            messages.

        Raises:
            None. Validation errors are reported through the returned result.

        Side Effects:
            None.

        Timeout:
            Not applicable; parsing operates on in-memory strings synchronously.
        """

        parsed = parse_json_payload(raw_text)
        if parsed.validation_errors:
            fallback = _build_fallback_result(raw_text, parsed.validation_errors)
            return StructuredParseResult(
                raw_text=raw_text,
                parsed_payload=parsed.parsed_payload,
                validation_errors=parsed.validation_errors,
                model=fallback,
            )

        assert parsed.parsed_payload is not None
        validation_issues = _validate_extraction_payload(parsed.parsed_payload)
        if validation_issues:
            fallback = _build_fallback_result(raw_text, validation_issues)
            return StructuredParseResult(
                raw_text=raw_text,
                parsed_payload=parsed.parsed_payload,
                validation_errors=validation_issues,
                model=fallback,
            )

        result = _convert_to_extraction_result(parsed.parsed_payload)
        return StructuredParseResult(
            raw_text=raw_text,
            parsed_payload=parsed.parsed_payload,
            validation_errors=(),
            model=result,
        )

    def build_retry_message(self, issues: Sequence[ValidationIssue]) -> str:
        """Render validation issues into guidance for a retry prompt.

        Args:
            issues: Collection of validation problems reported from the previous
                parsing attempt.

        Returns:
            Formatted instructional string suitable for inclusion in a follow-up
            user message to the model.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable; the function performs deterministic string formatting.
        """

        if not issues:
            return (
                "Previous response was valid; no retry guidance necessary."
            )

        formatted = "\n".join(f"- {issue.format()}" for issue in issues)
        return textwrap.dedent(
            f"""
            The previous response failed validation against {self._schema_name}.
            Correct the issues listed below and resend the payload as strict JSON:
            {formatted}
            Output only the corrected JSON with no extra commentary.
            """
        ).strip()


__all__ = ["ExtractionResponseParser"]
