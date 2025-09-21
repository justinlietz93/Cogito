"""Prompt builders for preflight extraction and query planning requests.

Purpose:
    Provide reusable functions that assemble deterministic system and user
    prompts for the preflight workflows. The functions embed JSON Schemas and
    guardrails so large language model providers can emit structured outputs that
    map cleanly to the domain DTOs defined for extraction and query planning.
External Dependencies:
    Python standard library modules only (``json`` and ``textwrap``).
Fallback Semantics:
    Prompt construction is pure and has no fallbacks. Higher layers are expected
    to perform retries when model outputs fail validation.
Timeout Strategy:
    Not applicable. Prompt generation performs no blocking I/O and therefore
    does not require timeout handling.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Optional
import textwrap

from ...domain.preflight import ExtractionResult
from ...pipeline_input import PipelineInput


@dataclass(frozen=True)
class PromptBundle:
    """Container holding the system and user prompt for a model request."""

    system: str
    user: str


def _serialise_schema(schema: Mapping[str, object]) -> str:
    """Return a deterministic JSON representation of a JSON Schema.

    Args:
        schema: Parsed JSON Schema mapping.

    Returns:
        Readable JSON string formatted with two-space indentation for embedding
        into prompts.

    Raises:
        TypeError: If ``schema`` contains objects that cannot be serialised to
            JSON by :func:`json.dumps`.

    Side Effects:
        None.

    Timeout:
        Not applicable; the operation is CPU-bound and runs synchronously.
    """

    return json.dumps(schema, indent=2, sort_keys=True)


def _build_extraction_system_prompt(max_points: Optional[int]) -> str:
    """Create the system prompt for the extraction workflow.

    Args:
        max_points: Optional hard limit on the number of points to return.

    Returns:
        String instructing the model on its role, guardrails, and format
        requirements.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the function performs only string formatting.
    """

    limit_clause = (
        f" Return no more than {max_points} points even if more appear relevant."
        if max_points is not None
        else " Respect any explicit point limits communicated in the user instructions."
    )
    return textwrap.dedent(
        f"""
        You are an expert research analyst tasked with extracting the most
        consequential findings from technical documents. Prioritise factual
        accuracy, cite supporting evidence, and avoid speculation.{limit_clause}
        Respond strictly in JSON that conforms to the provided schema. Do not
        include markdown fences, commentary, or additional explanations.
        """
    ).strip()


def _format_pipeline_metadata(pipeline_input: PipelineInput) -> str:
    """Render a short metadata block describing the pipeline input source.

    Args:
        pipeline_input: Canonical pipeline input for the run.

    Returns:
        Human-readable description including source hints and metadata flags.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the routine is CPU-bound and executes synchronously.
    """

    metadata = dict(pipeline_input.metadata or {})
    source = pipeline_input.source or "unspecified-source"
    truncated = metadata.get("truncated") or metadata.get("is_truncated")
    char_count = len(pipeline_input.content)
    lines = [f"Source: {source}"]
    lines.append(f"Characters: {char_count}")
    if truncated:
        lines.append("Repository truncation: true")
    if "files" in metadata:
        try:
            file_count = len(metadata["files"])  # type: ignore[index]
            lines.append(f"Files aggregated: {file_count}")
        except TypeError:
            lines.append("Files aggregated: unknown")
    return "\n".join(lines)


def build_extraction_prompt(
    pipeline_input: PipelineInput,
    schema: Mapping[str, object],
    *,
    max_points: Optional[int] = None,
) -> PromptBundle:
    """Construct the prompt bundle for the extraction gateway call.

    Args:
        pipeline_input: Normalised pipeline input containing the content corpus.
        schema: Parsed JSON Schema describing the expected response structure.
        max_points: Optional cap on the number of points to request from the
            model.

    Returns:
        :class:`PromptBundle` containing system and user prompts ready to send to
        a provider client.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution performs only string composition.
    """

    schema_json = _serialise_schema(schema)
    system_prompt = _build_extraction_system_prompt(max_points)
    limit_instructions = (
        f"Return no more than {max_points} points. " if max_points is not None else ""
    )
    user_prompt = textwrap.dedent(
        f"""
        Extract the most salient points from the provided content. {limit_instructions}
        Each point must include a stable identifier, a concise title, a detailed
        summary, supporting evidence references, a confidence score between 0 and
        1, and optional thematic tags. If you must omit potentially relevant
        points due to limits or token constraints, set "truncated" to true and
        include the strongest points first.

        === Pipeline Input Metadata ===
        {_format_pipeline_metadata(pipeline_input)}

        === Content ===
        {pipeline_input.content}

        === Required JSON Schema ===
        {schema_json}
        """
    ).strip()
    return PromptBundle(system=system_prompt, user=user_prompt)


def _build_query_system_prompt(max_queries: Optional[int]) -> str:
    """Create the system prompt for the query planning workflow.

    Args:
        max_queries: Optional cap on the number of queries to produce.

    Returns:
        System message instructing the model on planning responsibilities.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the function performs deterministic string formatting.
    """

    limit_clause = (
        f" Limit the plan to {max_queries} queries prioritised by impact."
        if max_queries is not None
        else " Ensure the plan is concise and prioritised."
    )
    return textwrap.dedent(
        f"""
        You are a research planning assistant. Review the extracted points and
        design precise follow-up queries that close knowledge gaps or validate
        critical claims.{limit_clause} Provide structured output only and respect
        declared dependencies between queries.
        """
    ).strip()


def _format_points_for_prompt(extraction: ExtractionResult) -> str:
    """Render extracted points into a compact text block for prompts.

    Args:
        extraction: Structured extraction result from the upstream workflow.

    Returns:
        Multi-line string describing each point with identifiers and summaries.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the function iterates over in-memory data only.
    """

    lines = []
    for index, point in enumerate(extraction.points, start=1):
        evidence = ", ".join(point.evidence_refs) or "(no evidence references)"
        tags = ", ".join(point.tags) or "(no tags)"
        lines.append(
            textwrap.dedent(
                f"""
                [{index}] id={point.id}
                title={point.title}
                summary={point.summary}
                evidence={evidence}
                confidence={point.confidence}
                tags={tags}
                """
            ).strip()
        )
    if not lines:
        return "(no points extracted)"
    return "\n\n".join(lines)


def build_query_plan_prompt(
    extraction: ExtractionResult,
    schema: Mapping[str, object],
    *,
    pipeline_input: Optional[PipelineInput] = None,
    max_queries: Optional[int] = None,
) -> PromptBundle:
    """Construct the prompt bundle for the query planning gateway call.

    Args:
        extraction: Structured extraction result containing the points to use.
        schema: Parsed JSON Schema describing the query plan response.
        pipeline_input: Optional original pipeline input to provide additional
            context for crafting queries.
        max_queries: Optional cap on the number of queries to request.

    Returns:
        :class:`PromptBundle` containing the system and user prompts.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution composes strings synchronously.
    """

    schema_json = _serialise_schema(schema)
    system_prompt = _build_query_system_prompt(max_queries)
    limit_instructions = (
        f"Return no more than {max_queries} queries. " if max_queries is not None else ""
    )
    contextual_blurb = (
        textwrap.dedent(
            f"""
            === Pipeline Input Metadata ===
            {_format_pipeline_metadata(pipeline_input)}

            === Content ===
            {pipeline_input.content}
            """
        ).strip()
        if pipeline_input is not None
        else ""
    )
    user_prompt = textwrap.dedent(
        f"""
        Review the extracted points and build a follow-up query plan. {limit_instructions}
        Every query must describe its purpose, priority, and any dependencies on
        earlier queries. Prefer concrete, actionable questions tied to specific
        evidence. Recommend specialised tooling when it meaningfully improves the
        investigation.

        === Extracted Points ===
        {_format_points_for_prompt(extraction)}

        {contextual_blurb}

        === Required JSON Schema ===
        {schema_json}
        """
    ).strip()
    return PromptBundle(system=system_prompt, user=user_prompt)


__all__ = ["PromptBundle", "build_extraction_prompt", "build_query_plan_prompt"]
