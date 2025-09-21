"""Query plan response parsing utilities for preflight workflows.

Purpose:
    Validate structured query plans emitted by language models and convert them
    into domain objects suitable for downstream orchestration. The module keeps
    the validation logic for :class:`~src.domain.preflight.QueryPlan` centralised
    so higher layers can remain thin.
External Dependencies:
    Python standard library modules ``textwrap`` and ``typing`` alongside local
    schema validation helpers.
Fallback Semantics:
    The parser surfaces structured validation errors and produces fallback
    artefacts containing the raw provider response together with formatted error
    messages. Callers can persist the fallback result while signalling that the
    payload failed schema validation.
Timeout Strategy:
    Not applicable; parsing and validation operate entirely in memory.
"""

from __future__ import annotations

import textwrap
from typing import Any, Mapping, Optional, Sequence, Tuple

from ...domain.preflight import BuiltQuery, QueryPlan
from .schema_validation import (
    StructuredParseResult,
    ValidationIssue,
    parse_json_payload,
    reject_additional_keys,
    require_keys,
    validate_string_array,
)


def _validate_built_query(
    item: Any,
    *,
    index: int,
    issues: list[ValidationIssue],
) -> Optional[BuiltQuery]:
    """Validate and convert a potential built query payload."""

    path = ("queries", str(index))
    if not isinstance(item, Mapping):
        issues.append(
            ValidationIssue(
                path=path,
                message="Each query must be an object with the documented properties.",
            )
        )
        return None

    required = ["id", "text", "purpose", "priority"]
    allowed = [
        "id",
        "text",
        "purpose",
        "priority",
        "depends_on_ids",
        "target_audience",
        "suggested_tooling",
    ]
    require_keys(item, required, path=path, issues=issues)
    reject_additional_keys(item, allowed, path=path, issues=issues)

    id_value = item.get("id")
    text_value = item.get("text")
    purpose_value = item.get("purpose")
    priority_value = item.get("priority")

    for key, value in ("id", id_value), ("text", text_value), ("purpose", purpose_value):
        if not isinstance(value, str) or not value.strip():
            issues.append(
                ValidationIssue(
                    path=path + (key,),
                    message="Value must be a non-empty string.",
                )
            )

    if not isinstance(priority_value, int):
        issues.append(
            ValidationIssue(
                path=path + ("priority",),
                message="priority must be an integer.",
            )
        )

    depends_on: Tuple[str, ...] = ()
    if "depends_on_ids" in item:
        depends_on = validate_string_array(
            item["depends_on_ids"],
            path=path + ("depends_on_ids",),
            issues=issues,
        )

    suggested_tooling: Tuple[str, ...] = ()
    if "suggested_tooling" in item:
        suggested_tooling = validate_string_array(
            item["suggested_tooling"],
            path=path + ("suggested_tooling",),
            issues=issues,
        )

    target_audience = item.get("target_audience")
    if target_audience is not None and not isinstance(target_audience, str):
        issues.append(
            ValidationIssue(
                path=path + ("target_audience",),
                message="target_audience must be null or a string.",
            )
        )

    if any(issue.path[:2] == path[:2] for issue in issues):
        return None

    return BuiltQuery(
        id=str(id_value),
        text=str(text_value),
        purpose=str(purpose_value),
        priority=int(priority_value) if isinstance(priority_value, int) else 0,
        depends_on_ids=depends_on,
        target_audience=target_audience if isinstance(target_audience, str) else None,
        suggested_tooling=suggested_tooling,
    )


def _format_validation_messages(issues: Sequence[ValidationIssue]) -> Tuple[str, ...]:
    """Return formatted string representations of validation issues.

    Args:
        issues: Validation problems encountered while parsing model output.

    Returns:
        Tuple containing human-readable error descriptions. Returns an empty
        tuple when no issues were supplied.

    Raises:
        None.

    Side Effects:
        None. The function performs deterministic string formatting only.

    Timeout:
        Not applicable; execution is CPU-bound and synchronous.
    """

    return tuple(issue.format() for issue in issues)


def _build_fallback_plan(
    raw_text: str,
    issues: Sequence[ValidationIssue],
) -> QueryPlan:
    """Construct a fallback query plan when validation fails.

    Args:
        raw_text: Raw JSON or JSON-like string returned by the language model.
        issues: Validation errors detected while parsing ``raw_text``.

    Returns:
        :class:`QueryPlan` instance containing no structured queries but
        preserving the raw response and formatted validation error messages for
        downstream observability.

    Raises:
        None.

    Side Effects:
        None. A new domain object is returned without mutating external state.

    Timeout:
        Not applicable; the helper performs simple data transformations.
    """

    return QueryPlan(
        queries=(),
        rationale="",
        assumptions=(),
        risks=(),
        raw_response=raw_text,
        validation_errors=_format_validation_messages(issues),
    )


def _validate_query_plan_payload(payload: Any) -> Tuple[ValidationIssue, ...]:
    """Return validation issues for a potential query plan payload."""

    issues: list[ValidationIssue] = []
    if not isinstance(payload, Mapping):
        issues.append(
            ValidationIssue(path=(), message="Root payload must be a JSON object."),
        )
        return tuple(issues)

    required = ["queries", "rationale"]
    allowed = ["queries", "rationale", "assumptions", "risks"]
    require_keys(payload, required, path=(), issues=issues)
    reject_additional_keys(payload, allowed, path=(), issues=issues)

    queries_value = payload.get("queries")
    if isinstance(queries_value, Sequence) and not isinstance(queries_value, (str, bytes)):
        for index, item in enumerate(queries_value):
            _validate_built_query(item, index=index, issues=issues)
    else:
        issues.append(
            ValidationIssue(
                path=("queries",),
                message="queries must be an array of objects.",
            )
        )

    rationale_value = payload.get("rationale")
    if not isinstance(rationale_value, str):
        issues.append(
            ValidationIssue(
                path=("rationale",),
                message="rationale must be a string (can be empty).",
            )
        )

    for array_key in ("assumptions", "risks"):
        if array_key in payload:
            validate_string_array(
                payload[array_key],
                path=(array_key,),
                issues=issues,
            )

    return tuple(issues)


def _convert_to_query_plan(payload: Mapping[str, Any]) -> QueryPlan:
    """Convert a validated payload to :class:`QueryPlan`."""

    queries_payload = payload.get("queries", [])
    queries = tuple(
        BuiltQuery(
            id=str(item["id"]),
            text=str(item["text"]),
            purpose=str(item["purpose"]),
            priority=int(item["priority"]),
            depends_on_ids=tuple(str(dep) for dep in item.get("depends_on_ids", [])),
            target_audience=(
                str(item["target_audience"])
                if isinstance(item.get("target_audience"), str)
                else None
            ),
            suggested_tooling=tuple(str(tool) for tool in item.get("suggested_tooling", [])),
        )
        for item in queries_payload
    )
    return QueryPlan(
        queries=queries,
        rationale=str(payload.get("rationale", "")),
        assumptions=tuple(str(item) for item in payload.get("assumptions", [])),
        risks=tuple(str(item) for item in payload.get("risks", [])),
    )


class QueryPlanResponseParser:
    """Parser that validates query plan responses and emits domain objects."""

    def __init__(self, *, schema_name: str = "query_plan.schema.json") -> None:
        self._schema_name = schema_name

    def parse(self, raw_text: str) -> StructuredParseResult[QueryPlan]:
        """Parse and validate a query plan response payload.

        Args:
            raw_text: Raw JSON-like string emitted by the query planning model.

        Returns:
            :class:`StructuredParseResult` with the parsed payload, any
            validation issues, and a :class:`QueryPlan` instance when validation
            is successful. When validation fails the returned result embeds a
            fallback :class:`QueryPlan` carrying the raw response and formatted
            error messages so callers can persist observability data while
            reacting to the failure.

        Raises:
            None. Validation feedback is surfaced within the returned result.

        Side Effects:
            None.

        Timeout:
            Not applicable; execution is CPU-bound and synchronous.
        """

        parsed = parse_json_payload(raw_text)
        if parsed.validation_errors:
            fallback = _build_fallback_plan(raw_text, parsed.validation_errors)
            return StructuredParseResult(
                raw_text=raw_text,
                parsed_payload=parsed.parsed_payload,
                validation_errors=parsed.validation_errors,
                model=fallback,
            )

        assert parsed.parsed_payload is not None
        validation_issues = _validate_query_plan_payload(parsed.parsed_payload)
        if validation_issues:
            fallback = _build_fallback_plan(raw_text, validation_issues)
            return StructuredParseResult(
                raw_text=raw_text,
                parsed_payload=parsed.parsed_payload,
                validation_errors=validation_issues,
                model=fallback,
            )

        plan = _convert_to_query_plan(parsed.parsed_payload)
        return StructuredParseResult(
            raw_text=raw_text,
            parsed_payload=parsed.parsed_payload,
            validation_errors=(),
            model=plan,
        )

    def build_retry_message(self, issues: Sequence[ValidationIssue]) -> str:
        """Render validation issues into guidance for a retry prompt.

        Args:
            issues: Collection of validation errors that must be addressed before
                accepting the response.

        Returns:
            String containing retry guidance for the model, including the list of
            issues that should be resolved.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable; the method formats strings synchronously.
        """

        if not issues:
            return (
                "Previous response was valid; no retry guidance necessary."
            )

        formatted = "\n".join(f"- {issue.format()}" for issue in issues)
        return textwrap.dedent(
            f"""
            The previous response failed validation against {self._schema_name}.
            Address the problems listed below and resend a corrected JSON payload:
            {formatted}
            Output only the corrected JSON with no additional commentary.
            """
        ).strip()


__all__ = ["QueryPlanResponseParser"]
