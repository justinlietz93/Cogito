"""Prompt builder tests for preflight workflows.

Purpose:
    Validate that the extraction and query planning prompt builders emit the
    required guardrails, schema instructions, and contextual metadata mandated by
    the preflight checklist.
External Dependencies:
    Uses only project-local modules alongside Python's standard library.
Fallback Semantics:
    The tests verify pure string composition; no fallback logic is exercised.
Timeout Strategy:
    Not applicable. Prompt construction is CPU-bound and incurs no blocking I/O.
"""

from __future__ import annotations

from typing import Mapping

from src.application.preflight.prompts import (
    PromptBundle,
    build_extraction_prompt,
    build_query_plan_prompt,
)
from src.domain.preflight import ExtractedPoint, ExtractionResult
from src.pipeline_input import PipelineInput


def _example_schema() -> Mapping[str, object]:
    """Return a minimal JSON Schema snippet for prompt embedding.

    Returns:
        Mapping representing a bare-bones JSON Schema used to verify that the
        prompt builders include schema content verbatim.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the mapping is static.
    """

    return {
        "title": "ExampleSchema",
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
        "required": ["items"],
    }


def _example_extraction_result() -> ExtractionResult:
    """Build a deterministic extraction result for prompt formatting checks.

    Returns:
        An :class:`ExtractionResult` containing two :class:`ExtractedPoint`
        instances to ensure the prompt formatting enumerates points correctly.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; the domain objects are created synchronously.
    """

    return ExtractionResult(
        points=(
            ExtractedPoint(
                id="point-1",
                title="Key Insight",
                summary="Critical finding described in detail.",
                evidence_refs=("doc:1",),
                confidence=0.9,
                tags=("safety",),
            ),
            ExtractedPoint(
                id="point-2",
                title="Secondary Insight",
                summary="Supporting evidence captured here.",
                evidence_refs=("doc:2", "doc:3"),
                confidence=0.75,
                tags=(),
            ),
        ),
        truncated=True,
    )


def test_build_extraction_prompt_includes_limits_and_metadata() -> None:
    """Ensure extraction prompts expose limit clauses, metadata, and schema text.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If the prompt omits the limit clause, metadata block, or
            schema snippet required for downstream validation.

    Side Effects:
        None.

    Timeout:
        Not applicable; prompt generation is deterministic.
    """

    pipeline_input = PipelineInput(
        content="Important breakthrough details.",
        source="whitepaper.pdf",
        metadata={"truncated": True, "files": ["a.py", "b.py"]},
    )
    prompts = build_extraction_prompt(
        pipeline_input,
        _example_schema(),
        max_points=5,
    )

    assert isinstance(prompts, PromptBundle)
    assert "Return no more than 5 points even if more appear relevant." in prompts.system
    assert "Return no more than 5 points." in prompts.user
    assert "Source: whitepaper.pdf" in prompts.user
    assert "Repository truncation: true" in prompts.user
    assert "Files aggregated: 2" in prompts.user
    assert '"title": "ExampleSchema"' in prompts.user
    assert '"type": "object"' in prompts.user


def test_build_query_plan_prompt_formats_points_and_context() -> None:
    """Verify query plan prompts include formatted points and contextual data.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If the prompt omits enumerated points, contextual
            metadata, or the limit instructions required by the checklist.

    Side Effects:
        None.

    Timeout:
        Not applicable; prompt generation is deterministic.
    """

    pipeline_input = PipelineInput(
        content="Repository summary.",
        source="repo",
        metadata={"files": ["README.md"], "truncated": False},
    )
    extraction = _example_extraction_result()
    prompts = build_query_plan_prompt(
        extraction,
        _example_schema(),
        pipeline_input=pipeline_input,
        max_queries=3,
    )

    assert isinstance(prompts, PromptBundle)
    assert "Limit the plan to 3 queries prioritised by impact." in prompts.system
    assert "Return no more than 3 queries." in prompts.user
    assert "[1] id=point-1" in prompts.user
    assert "summary=Critical finding described in detail." in prompts.user
    assert "Source: repo" in prompts.user
    assert '"title": "ExampleSchema"' in prompts.user
    assert '"type": "object"' in prompts.user
