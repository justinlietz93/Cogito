"""Tests for the research enhancement service."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))

from src.syncretic_catalyst.application.research_enhancement import (
    ProjectDocumentsNotFound,
    ResearchEnhancementService,
)
from src.syncretic_catalyst.domain import (
    EnhancedProposal,
    KeyConcept,
    ProjectDocument,
    ResearchGapAnalysis,
    ResearchPaper,
)


@dataclass
class _StubRepository:
    documents: Sequence[ProjectDocument]
    saved_concepts: Sequence[KeyConcept] | None = None
    saved_papers: Sequence[ResearchPaper] | None = None
    saved_gap: ResearchGapAnalysis | None = None
    saved_proposal: EnhancedProposal | None = None

    def load_documents(self) -> Sequence[ProjectDocument]:
        return self.documents

    def persist_key_concepts(self, concepts: Sequence[KeyConcept]) -> None:
        self.saved_concepts = list(concepts)

    def persist_papers(self, papers: Sequence[ResearchPaper]) -> None:
        self.saved_papers = list(papers)

    def persist_gap_analysis(self, analysis: ResearchGapAnalysis) -> None:
        self.saved_gap = analysis

    def persist_enhanced_proposal(self, proposal: EnhancedProposal) -> None:
        self.saved_proposal = proposal


class _StubReferenceService:
    def __init__(self, responses: Iterable[Sequence[ResearchPaper]]) -> None:
        self._responses = list(responses)
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
        self.queries.append((query, max_results))
        if self._responses:
            return self._responses.pop(0)
        return []


class _StubGenerator:
    def __init__(self, responses: Iterable[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, int]] = []

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens))
        if not self._responses:
            raise AssertionError("Unexpected generator invocation")
        return self._responses.pop(0)


def _paper(identifier: str) -> ResearchPaper:
    return ResearchPaper(
        identifier=identifier,
        title=f"Title {identifier}",
        authors=("Author",),
        published="2024-05-01",
        summary="Summary text",
        raw_payload={"id": identifier},
    )


def test_enhance_generates_outputs_and_persists_results() -> None:
    documents = [
        ProjectDocument(
            name="CONTEXT_CONSTRAINTS.md",
            content="# Heading\n\n### Plasma Containment Strategy\n- Maintain magnetic field",
        ),
        ProjectDocument(
            name="BREAKTHROUGH_BLUEPRINT.md",
            content="# Stellar Fusion Initiative\n\nVisionary description.",
        ),
    ]

    repository = _StubRepository(documents)
    reference_service = _StubReferenceService(
        [
            [_paper("primary")],
            [_paper("primary"), _paper("secondary")],
            [_paper("tertiary")],
        ]
    )
    generator = _StubGenerator(["gap-analysis", "enhanced-proposal"])

    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    result = service.enhance(max_papers=3, max_concepts=2)

    assert result.project_title == "Stellar Fusion Initiative"
    assert len(result.key_concepts) == 2
    assert {paper.identifier for paper in result.papers} == {"primary", "secondary", "tertiary"}
    assert result.gap_analysis.content == "gap-analysis"
    assert result.enhanced_proposal.content == "enhanced-proposal"

    assert repository.saved_concepts is not None and len(repository.saved_concepts) == 2
    assert repository.saved_papers is not None and len(repository.saved_papers) == 3
    assert repository.saved_gap == ResearchGapAnalysis("gap-analysis")
    assert repository.saved_proposal == EnhancedProposal("enhanced-proposal")

    assert generator.calls[0][0].startswith("You are a research scientist")
    assert "Research Gap Analysis" in generator.calls[0][1]
    assert generator.calls[1][0].startswith("You are an expert academic writer")
    assert "Research Proposal Enhancement" in generator.calls[1][1]

    first_query, first_limit = reference_service.queries[0]
    assert first_limit == 1  # half of target papers rounded down then clamped to 1
    assert "Context Constraints" in first_query


def test_enhance_requires_documents() -> None:
    repository = _StubRepository(documents=[])
    reference_service = _StubReferenceService([])
    generator = _StubGenerator(["gap", "proposal"])

    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    with pytest.raises(ProjectDocumentsNotFound):
        service.enhance()


def test_order_documents_skips_empty_and_unknown_entries() -> None:
    service = ResearchEnhancementService(
        reference_service=_StubReferenceService([]),
        project_repository=_StubRepository([]),
        content_generator=_StubGenerator([]),
    )

    documents = [
        ProjectDocument(name="UNLISTED_NOTE.md", content="Observations."),
        ProjectDocument(name="CONTEXT_CONSTRAINTS.md", content="   "),
        ProjectDocument(name="CONTEXT_CONSTRAINTS.md", content="Key constraints content."),
        ProjectDocument(name="IMPLEMENTATION_PATH.md", content="Implementation plan."),
        ProjectDocument(name="BREAKTHROUGH_BLUEPRINT.md", content=""),
    ]

    ordered = service._order_documents(documents)
    assert [doc.name for doc in ordered] == [
        "CONTEXT_CONSTRAINTS.md",
        "IMPLEMENTATION_PATH.md",
        "UNLISTED_NOTE.md",
    ]


def test_extract_key_concepts_handles_duplicates_and_formatting() -> None:
    service = ResearchEnhancementService(
        reference_service=_StubReferenceService([]),
        project_repository=_StubRepository([]),
        content_generator=_StubGenerator([]),
        max_concepts=5,
    )

    complex_content = (
        "# Plasma Containment Strategy\n"
        "## Duplicate Name\n"
        "- Maintain magnetic field\n"
        "- Maintain magnetic field\n"
        "* Advanced Containment\n"
        "__Quantum Loop Stabilization__\n"
        "We advance the Stellar Fusion Initiative with Multi-Beam Focusing arrays."
    )

    concepts = service._extract_key_concepts(complex_content, max_concepts=5)
    assert concepts == [
        "Plasma Containment Strategy",
        "Duplicate Name",
        "Maintain magnetic field",
        "Advanced Containment",
        "Quantum Loop Stabilization",
    ]

