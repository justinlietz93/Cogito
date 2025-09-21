"""Shared schema validation utilities for preflight structured outputs.

Purpose:
    Provide reusable helpers for parsing JSON payloads emitted by large language
    models and validating them according to the expected structural constraints.
    These utilities are intentionally domain-agnostic so both extraction and
    query planning parsers can reuse them without duplicating logic.
External Dependencies:
    Python standard library only (``dataclasses``, ``json``, and ``typing``).
Fallback Semantics:
    Validation helpers report structured issues rather than raising exceptions.
    Callers are responsible for implementing retry or fallback behaviour.
Timeout Strategy:
    Not applicable; the module performs only in-memory operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Generic, Iterable, Mapping, Optional, Sequence, Tuple, TypeVar


@dataclass(frozen=True)
class ValidationIssue:
    """Represents a single schema validation issue detected in a payload."""

    path: Tuple[str, ...]
    message: str

    def format(self) -> str:
        """Render the issue into a human-readable string.

        Returns:
            String describing the validation error with its JSON pointer-like
            location.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable; the method performs simple string concatenation.
        """

        location = "/".join(self.path) if self.path else "<root>"
        return f"{location}: {self.message}"


T = TypeVar("T")


@dataclass(frozen=True)
class StructuredParseResult(Generic[T]):
    """Container summarising the outcome of parsing and validation."""

    raw_text: str
    parsed_payload: Optional[Any]
    validation_errors: Tuple[ValidationIssue, ...]
    model: Optional[T]

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when parsing succeeded and the model instance is available.

        Returns:
            ``True`` when ``model`` is populated and no validation errors were
            recorded, otherwise ``False``.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable; property evaluation is instantaneous.
        """

        return self.model is not None and not self.validation_errors


def parse_json_payload(raw_text: str) -> StructuredParseResult[Any]:
    """Attempt to parse ``raw_text`` as JSON without schema validation.

    Args:
        raw_text: Raw string returned by the language model invocation.

    Returns:
        :class:`StructuredParseResult` with the parsed payload populated on
        success. When parsing fails the result contains a corresponding
        :class:`ValidationIssue` and ``parsed_payload`` is ``None``.

    Raises:
        None. Parsing errors are captured in the returned result.

    Side Effects:
        None.

    Timeout:
        Not applicable; JSON parsing operates synchronously in memory.
    """

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised in tests
        issue = ValidationIssue(
            path=(),
            message=(
                f"Invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}. "
                "Ensure the response is raw JSON without commentary."
            ),
        )
        return StructuredParseResult(
            raw_text=raw_text,
            parsed_payload=None,
            validation_errors=(issue,),
            model=None,
        )

    return StructuredParseResult(
        raw_text=raw_text,
        parsed_payload=payload,
        validation_errors=(),
        model=None,
    )


def require_keys(
    data: Mapping[str, Any],
    required: Sequence[str],
    *,
    path: Tuple[str, ...],
    issues: list[ValidationIssue],
) -> None:
    """Ensure that ``required`` keys exist within ``data``.

    Args:
        data: Mapping being inspected.
        required: Sequence of key names that must be present.
        path: Location of ``data`` within the overall payload, used for error
            reporting.
        issues: Mutable list that collects encountered validation problems.

    Returns:
        ``None``. Issues are appended to ``issues`` when violations occur.

    Raises:
        None.

    Side Effects:
        Appends :class:`ValidationIssue` instances to ``issues`` when keys are
        missing.

    Timeout:
        Not applicable; the check iterates over a finite sequence synchronously.
    """

    for key in required:
        if key not in data:
            issues.append(
                ValidationIssue(path=path + (key,), message="Missing required property."),
            )


def reject_additional_keys(
    data: Mapping[str, Any],
    allowed: Iterable[str],
    *,
    path: Tuple[str, ...],
    issues: list[ValidationIssue],
) -> None:
    """Ensure ``data`` does not expose properties outside ``allowed``.

    Args:
        data: Mapping being validated.
        allowed: Iterable of property names that are permitted.
        path: Location of ``data`` within the larger payload.
        issues: Mutable list receiving validation problems.

    Returns:
        ``None``. Any unexpected properties are appended to ``issues``.

    Raises:
        None.

    Side Effects:
        Appends :class:`ValidationIssue` entries to ``issues`` for disallowed
        properties.

    Timeout:
        Not applicable; the function iterates deterministically over ``data``.
    """

    allowed_set = set(allowed)
    for key in data:
        if key not in allowed_set:
            issues.append(
                ValidationIssue(
                    path=path + (key,),
                    message="Property is not allowed by the schema.",
                )
            )


def validate_string_array(
    value: Any,
    *,
    path: Tuple[str, ...],
    issues: list[ValidationIssue],
    allow_empty: bool = True,
) -> Tuple[str, ...]:
    """Validate that ``value`` represents a sequence of non-empty strings.

    Args:
        value: Candidate array value.
        path: Location of the array in the payload for diagnostics.
        issues: Mutable list capturing validation problems.
        allow_empty: When ``False`` the array must contain at least one string.

    Returns:
        Tuple of strings extracted from ``value`` when validation succeeds. When
        validation fails an empty tuple is returned and issues are appended to
        ``issues``.

    Raises:
        None.

    Side Effects:
        Appends :class:`ValidationIssue` entries to ``issues`` when validation
        fails.

    Timeout:
        Not applicable; iteration is bounded by the size of ``value``.
    """

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        issues.append(
            ValidationIssue(path=path, message="Expected an array of strings."),
        )
        return ()

    items: list[str] = []
    for index, element in enumerate(value):
        if not isinstance(element, str) or not element.strip():
            issues.append(
                ValidationIssue(
                    path=path + (str(index),),
                    message="Each entry must be a non-empty string.",
                )
            )
        else:
            items.append(element)

    if not allow_empty and not items:
        issues.append(ValidationIssue(path=path, message="Array must not be empty."))

    return tuple(items)


__all__ = [
    "ValidationIssue",
    "StructuredParseResult",
    "parse_json_payload",
    "reject_additional_keys",
    "require_keys",
    "validate_string_array",
]
