"""Utilities for CLI preflight configuration and artefact handling.

Purpose:
    Provide lightweight helpers that map configuration defaults and runtime
    overrides into :class:`src.application.preflight.orchestrator.PreflightOptions`
    instances and persist resulting artefacts to disk. The module keeps
    presentation-layer parsing and persistence logic separate from the CLI
    controller to maintain readability while respecting clean architecture
    boundaries.
External Dependencies:
    Python standard library modules ``argparse``, ``dataclasses``, ``json``,
    ``logging``, and ``pathlib`` only.
Fallback Semantics:
    When configuration values are missing or invalid, the helpers fall back to
    conservative defaults that disable preflight stages until explicitly
    enabled by the user.
Timeout Strategy:
    Not applicable. All functions perform deterministic, CPU-bound
    transformations without I/O.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from ...application.preflight.orchestrator import PreflightOptions, PreflightRunResult
from ...domain.preflight import BuiltQuery, ExtractionResult, ExtractedPoint, QueryPlan


def _coerce_optional_int(value: Any) -> Optional[int]:
    """Attempt to convert ``value`` into a positive integer.

    Args:
        value: Potential integer-like value supplied via configuration or CLI
            overrides.

    Returns:
        ``None`` when ``value`` is ``None`` or cannot be converted. Otherwise,
        returns the integer when positive. Non-positive integers are treated as
        missing values.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the function executes synchronously without I/O.
    """

    if value is None:
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0:
        return None
    return converted


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    """Return ``value`` when it is a mapping, otherwise an empty dict.

    Args:
        value: Candidate object that may represent a mapping.

    Returns:
        A shallow copy of ``value`` when it implements the mapping protocol,
        otherwise an empty dictionary.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    if isinstance(value, Mapping):
        return dict(value)
    return {}


@dataclass(frozen=True)
class PreflightCliDefaults:
    """Immutable configuration defaults used by the CLI when building options.

    Attributes:
        provider: Name of the provider configured for preflight stages.
        extract_enabled: Whether extraction runs when the user does not supply
            explicit overrides.
        query_enabled: Whether query planning runs when overrides are absent.
        max_points: Optional default limit for extracted points.
        max_queries: Optional default limit for planned queries.
        points_artifact: Relative path for storing extraction artefacts.
        queries_artifact: Relative path for storing query plan artefacts.
        metadata: Mapping propagated to the orchestrator for observability.
    """

    provider: str = "openai"
    extract_enabled: bool = False
    query_enabled: bool = False
    max_points: Optional[int] = None
    max_queries: Optional[int] = None
    points_artifact: str = "artifacts/points.json"
    queries_artifact: str = "artifacts/queries.json"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreflightCliOverrides:
    """Container describing CLI-supplied overrides for preflight settings.

    Attributes:
        enable_extraction: Optional boolean override for enabling extraction.
        enable_query_building: Optional boolean override controlling query
            planning.
        points_artifact: Optional path override for the extraction artefact.
        queries_artifact: Optional path override for the query plan artefact.
        max_points: Optional override for the extraction point limit.
        max_queries: Optional override for the query plan limit.
    """

    enable_extraction: Optional[bool] = None
    enable_query_building: Optional[bool] = None
    points_artifact: Optional[str] = None
    queries_artifact: Optional[str] = None
    max_points: Optional[int] = None
    max_queries: Optional[int] = None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace | None) -> "PreflightCliOverrides":
        """Create overrides from the parsed CLI namespace.

        Args:
            args: Parsed namespace produced by :mod:`argparse`. ``None`` yields
                a default instance with no overrides.

        Returns:
            Populated :class:`PreflightCliOverrides` representing CLI
            preferences.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable.
        """

        if args is None:
            return cls()

        return cls(
            enable_extraction=getattr(args, "preflight_extract", None),
            enable_query_building=getattr(args, "preflight_build_queries", None),
            points_artifact=getattr(args, "points_out", None),
            queries_artifact=getattr(args, "queries_out", None),
            max_points=_coerce_optional_int(getattr(args, "max_points", None)),
            max_queries=_coerce_optional_int(getattr(args, "max_queries", None)),
        )


def load_preflight_defaults(config: Mapping[str, Any]) -> PreflightCliDefaults:
    """Extract CLI defaults for preflight stages from ``config``.

    Args:
        config: Mapping produced from ``config.json``.

    Returns:
        Instance of :class:`PreflightCliDefaults` populated with safe defaults.

    Raises:
        None. Invalid or missing entries fall back to conservative defaults.

    Side Effects:
        None.

    Timeout:
        Not applicable; only dictionary lookups are performed.
    """

    preflight_section = _safe_mapping(config.get("preflight"))
    extract_section = _safe_mapping(preflight_section.get("extract"))
    query_section = _safe_mapping(preflight_section.get("queries"))

    return PreflightCliDefaults(
        provider=str(preflight_section.get("provider", "openai")),
        extract_enabled=bool(extract_section.get("enabled", False)),
        query_enabled=bool(query_section.get("enabled", False)),
        max_points=_coerce_optional_int(extract_section.get("max_points")),
        max_queries=_coerce_optional_int(query_section.get("max_queries")),
        points_artifact=str(extract_section.get("artifact_path", "artifacts/points.json")),
        queries_artifact=str(query_section.get("artifact_path", "artifacts/queries.json")),
        metadata=_safe_mapping(preflight_section.get("metadata")),
    )


def build_preflight_options(
    defaults: PreflightCliDefaults | None,
    overrides: PreflightCliOverrides,
) -> PreflightOptions | None:
    """Merge defaults and overrides into :class:`PreflightOptions`.

    Args:
        defaults: Baseline configuration derived from ``config.json``. When
            ``None``, preflight execution is disabled regardless of overrides.
        overrides: CLI-supplied overrides parsed from runtime arguments.

    Returns:
        Populated :class:`PreflightOptions` when at least one stage is enabled;
        otherwise ``None``.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    if defaults is None:
        return None

    enable_extraction = (
        overrides.enable_extraction
        if overrides.enable_extraction is not None
        else defaults.extract_enabled
    )
    enable_query = (
        overrides.enable_query_building
        if overrides.enable_query_building is not None
        else defaults.query_enabled
    )

    if enable_query and not enable_extraction:
        enable_extraction = True

    if not (enable_extraction or enable_query):
        return None

    max_points = overrides.max_points if overrides.max_points is not None else defaults.max_points
    max_queries = (
        overrides.max_queries if overrides.max_queries is not None else defaults.max_queries
    )

    metadata = dict(defaults.metadata)

    return PreflightOptions(
        enable_extraction=enable_extraction,
        enable_query_building=enable_query,
        max_points=max_points,
        max_queries=max_queries,
        metadata=metadata,
        extraction_artifact_name=(
            overrides.points_artifact if overrides.points_artifact else defaults.points_artifact
        ),
        query_artifact_name=(
            overrides.queries_artifact if overrides.queries_artifact else defaults.queries_artifact
        ),
    )


def _resolve_artifact_path(output_dir: Path, candidate: Optional[str], fallback: str) -> Path:
    """Resolve an artefact path relative to ``output_dir`` when necessary.

    Args:
        output_dir: Directory where artefacts should be stored.
        candidate: Optional candidate path supplied by the orchestrator.
        fallback: Default relative path when ``candidate`` is ``None``.

    Returns:
        Absolute :class:`Path` pointing to the resolved location.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    name = candidate or fallback
    path = Path(name)
    if not path.is_absolute():
        path = output_dir / path
    return path


def _write_json_payload(
    path: Path,
    payload: Mapping[str, Any],
    *,
    logger: logging.Logger,
    description: str,
) -> bool:
    """Serialise ``payload`` as JSON and persist it to ``path``.

    Args:
        path: Destination file path for the artefact.
        payload: Mapping that will be encoded as JSON.
        logger: Logger capturing failures for diagnostics.
        description: Human-readable artefact description for log messages.

    Returns:
        ``True`` when writing succeeds, otherwise ``False``.

    Raises:
        None.

    Side Effects:
        Creates parent directories when needed and writes files to disk.

    Timeout:
        Not applicable.
    """

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Failed to prepare directory for %s", description)
        return False
    try:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.exception("Failed to write %s", description)
        return False
    return True


def _serialise_extracted_points(points: Iterable[ExtractedPoint]) -> list[Dict[str, Any]]:
    """Convert extracted point models into schema-compliant dictionaries.

    Args:
        points: Iterable collection of :class:`ExtractedPoint` instances emitted by
            the extraction stage.

    Returns:
        List of dictionaries ready for JSON serialisation that only includes
        schema-supported fields.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the conversion iterates deterministically over a finite
        collection.
    """

    serialised: list[Dict[str, Any]] = []
    for point in points:
        serialised.append(
            {
                "id": point.id,
                "title": point.title,
                "summary": point.summary,
                "evidence_refs": list(point.evidence_refs),
                "confidence": point.confidence,
                "tags": list(point.tags),
            }
        )
    return serialised


def _serialise_queries(queries: Iterable[BuiltQuery]) -> list[Dict[str, Any]]:
    """Convert built query models into schema-compliant dictionaries.

    Args:
        queries: Iterable of :class:`BuiltQuery` instances composing a query plan.

    Returns:
        List of dictionaries containing only the properties permitted by the
        query plan schema.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the conversion performs synchronous iteration.
    """

    serialised: list[Dict[str, Any]] = []
    for query in queries:
        serialised.append(
            {
                "id": query.id,
                "text": query.text,
                "purpose": query.purpose,
                "priority": query.priority,
                "depends_on_ids": list(query.depends_on_ids),
                "target_audience": query.target_audience,
                "suggested_tooling": list(query.suggested_tooling),
            }
        )
    return serialised


def _serialise_extraction_result(result: ExtractionResult) -> Dict[str, Any]:
    """Transform an extraction result into a JSON-serialisable mapping.

    Args:
        result: Fully populated :class:`ExtractionResult` produced by the
            orchestrator.

    Returns:
        Dictionary compatible with ``extraction.schema.json`` where only schema
        sanctioned fields are emitted.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable.
    """

    return {
        "points": _serialise_extracted_points(result.points),
        "source_stats": dict(result.source_stats),
        "truncated": bool(result.truncated),
    }


def _serialise_query_plan(plan: QueryPlan) -> Dict[str, Any]:
    """Serialise a query plan without emitting fallback-specific metadata.

    Args:
        plan: :class:`QueryPlan` instance describing planned queries and context.

    Returns:
        Mapping that conforms to ``query_plan.schema.json`` and omits raw
        provider payload details that are tracked separately in the domain
        model.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; computation is purely in-memory.
    """

    return {
        "queries": _serialise_queries(plan.queries),
        "rationale": plan.rationale,
        "assumptions": list(plan.assumptions),
        "risks": list(plan.risks),
    }


def persist_preflight_artifacts(
    preflight: PreflightRunResult,
    output_dir: Path,
    defaults: PreflightCliDefaults,
    *,
    logger: logging.Logger,
    notify: Callable[[str], None],
) -> Dict[str, str]:
    """Persist preflight artefacts and return updated path mappings.

    Args:
        preflight: Orchestrator result containing extraction and query artefacts.
        output_dir: Directory where artefacts should be written.
        defaults: Default configuration controlling fallback artefact paths.
        logger: Logger used to record failures during persistence.
        notify: Callable used to surface success or failure messages to the user.

    Returns:
        Mapping of artefact keys to the absolute paths that were successfully
        written. Entries are omitted when persistence fails.

    Raises:
        None. Failures are logged and surfaced via ``notify``.

    Side Effects:
        Writes JSON files to disk and emits user-facing notifications.

    Timeout:
        Not applicable; operations rely on the filesystem without explicit timeouts.
    """

    resolved: Dict[str, str] = {}

    if preflight.extraction is not None:
        path = _resolve_artifact_path(
            output_dir,
            preflight.artifact_paths.get("extraction"),
            defaults.points_artifact,
        )
        payload = _serialise_extraction_result(preflight.extraction)
        if _write_json_payload(path, payload, logger=logger, description="preflight extraction"):
            notify(f"Preflight points saved to {path}")
            resolved["extraction"] = str(path)
        else:
            notify(f"Warning: Could not write preflight extraction to {path}.")

    if preflight.query_plan is not None:
        path = _resolve_artifact_path(
            output_dir,
            preflight.artifact_paths.get("query_plan"),
            defaults.queries_artifact,
        )
        payload = _serialise_query_plan(preflight.query_plan)
        if _write_json_payload(path, payload, logger=logger, description="preflight query plan"):
            notify(f"Preflight queries saved to {path}")
            resolved["query_plan"] = str(path)
        else:
            notify(f"Warning: Could not write preflight query plan to {path}.")

    return resolved


def update_preflight_metadata(
    result: Any,
    output_dir: Path,
    defaults: PreflightCliDefaults,
    *,
    logger: logging.Logger,
    notify: Callable[[str], None],
) -> None:
    """Persist artefacts and refresh metadata for a critique result.

    Args:
        result: Object with ``preflight`` and ``pipeline_input`` attributes
            matching :class:`src.application.critique.services.CritiqueRunResult`.
        output_dir: Directory where artefacts should be written.
        defaults: Default CLI configuration for artefact handling.
        logger: Logger used to record persistence issues.
        notify: Callable used to display user-facing messages.

    Returns:
        None.

    Raises:
        None.

    Side Effects:
        Writes JSON artefacts and mutates the result's metadata mapping.

    Timeout:
        Not applicable.
    """

    preflight = getattr(result, "preflight", None)
    if not isinstance(preflight, PreflightRunResult) or not preflight.has_outputs():
        return

    resolved_paths = persist_preflight_artifacts(
        preflight,
        output_dir,
        defaults,
        logger=logger,
        notify=notify,
    )
    if resolved_paths:
        preflight.artifact_paths.update(resolved_paths)

    pipeline_input = getattr(result, "pipeline_input", None)
    if pipeline_input is not None and hasattr(pipeline_input, "metadata"):
        pipeline_input.metadata["preflight_artifacts"] = dict(preflight.artifact_paths)


__all__ = [
    "PreflightCliDefaults",
    "PreflightCliOverrides",
    "persist_preflight_artifacts",
    "update_preflight_metadata",
    "build_preflight_options",
    "load_preflight_defaults",
]

