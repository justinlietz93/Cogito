"""Domain models for preflight extraction and query planning artifacts.

Purpose:
    Provide immutable data structures describing the outcomes of preflight
    extraction and query planning workflows. The models are intentionally
    lightweight and independent from framework code so they can be reused across
    the application, presentation, and infrastructure layers without creating
    dependency cycles.
External Dependencies:
    Python standard library modules ``dataclasses`` and ``typing`` only.
Fallback Semantics:
    Domain objects may capture fallback metadata such as raw provider responses
    and validation error messages so that application services can continue
    operating even when strict validation fails. They do not implement fallback
    logic themselves.
Timeout Strategy:
    Not applicable. Domain objects do not manage or enforce timeout policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class ExtractedPoint:
    """Represents a salient point identified during preflight extraction.

    Attributes:
        id: Stable identifier that allows points to be referenced by later
            processing stages. Implementations should prefer deterministic
            identifiers such as UUIDs or hashes derived from the source
            artefacts.
        title: Human-readable heading summarising the point.
        summary: Multi-sentence narrative expanding on the title and providing
            sufficient context for downstream processing steps.
        evidence_refs: Collection of references (for example file paths or
            citation anchors) that support the point.
        confidence: Normalised score in the ``[0.0, 1.0]`` range expressing the
            extractor's certainty about the point's accuracy and relevance.
        tags: Optional thematic labels applied by the extractor. Tags enable
            filtering and prioritisation when building follow-up queries.

    Raises:
        ValueError: If ``confidence`` falls outside the inclusive ``[0.0, 1.0]``
            interval.
    """

    id: str
    title: str
    summary: str
    evidence_refs: Tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    tags: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate invariants defined for extracted points.

        Raises:
            ValueError: If the configured ``confidence`` is not normalised to the
                ``[0.0, 1.0]`` range.
        """

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be a normalised value between 0.0 and 1.0")


@dataclass(frozen=True)
class ExtractionResult:
    """Container aggregating the results of a point extraction run.

    Attributes:
        points: Ordered collection of :class:`ExtractedPoint` instances emitted by
            the extractor.
        source_stats: Optional metadata describing the processed corpus such as
            byte counts, token usage, or truncation markers. Downstream services
            may use these statistics for observability and to inform retries.
        truncated: Flag indicating whether the extractor truncated points due to
            limits like ``max_points`` or model token caps.
        raw_response: Optional raw JSON string returned by the provider when
            validation failed and a fallback artefact had to be generated.
        validation_errors: Tuple of formatted validation error messages used to
            describe why structured parsing failed. An empty tuple indicates that
            the result satisfied schema validation.
    """

    points: Tuple[ExtractedPoint, ...] = field(default_factory=tuple)
    source_stats: Mapping[str, Any] = field(default_factory=dict)
    truncated: bool = False
    raw_response: Optional[str] = None
    validation_errors: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BuiltQuery:
    """Represents a follow-up query derived from extracted points.

    Attributes:
        id: Stable identifier for referencing the query in dependency graphs.
        text: Natural-language query or instruction to be executed during later
            stages.
        purpose: Short description capturing why the query is necessary.
        priority: Integer representing the execution order preference. Lower
            numbers can represent higher priority depending on orchestration
            policy.
        depends_on_ids: Identifiers of prerequisite queries that must complete
            before this query executes.
        target_audience: Optional descriptor indicating the intended responder
            (for example ``"author"``, ``"reviewer"`` or a specific tool name).
        suggested_tooling: Optional set of tool identifiers that best suit the
            query. The field supports multiple suggestions to allow fallbacks.
    """

    id: str
    text: str
    purpose: str
    priority: int
    depends_on_ids: Tuple[str, ...] = field(default_factory=tuple)
    target_audience: Optional[str] = None
    suggested_tooling: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QueryPlan:
    """Aggregates all queries and related context for downstream orchestration.

    Attributes:
        queries: Ordered collection of :class:`BuiltQuery` items that form the
            plan.
        rationale: Narrative description of the strategy behind the plan.
        assumptions: Optional list of assumptions that influenced the plan.
        risks: Optional list describing potential pitfalls or uncertainties.
        raw_response: Optional raw JSON string captured when validation failed
            but the application chose to continue with a fallback artefact.
        validation_errors: Tuple of formatted validation error messages. An empty
            tuple signals that the plan passed validation successfully.
    """

    queries: Tuple[BuiltQuery, ...] = field(default_factory=tuple)
    rationale: str = ""
    assumptions: Tuple[str, ...] = field(default_factory=tuple)
    risks: Tuple[str, ...] = field(default_factory=tuple)
    raw_response: Optional[str] = None
    validation_errors: Tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "BuiltQuery",
    "ExtractedPoint",
    "ExtractionResult",
    "QueryPlan",
]
