from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import pytest

from syncretic_catalyst.application.research_enhancement.exceptions import (
    ProjectDocumentsNotFound,
)
from syncretic_catalyst.application.research_enhancement.services import (
    ResearchEnhancementService,
)
from syncretic_catalyst.domain import (
    EnhancedProposal,
    KeyConcept,
    ProjectDocument,
    ResearchGapAnalysis,
    ResearchPaper,
)


@dataclass
class FakeRepository:
    documents: Sequence[ProjectDocument]
    persisted_key_concepts: Sequence[KeyConcept] | None = None
    persisted_papers: Sequence[ResearchPaper] | None = None
    persisted_gap: ResearchGapAnalysis | None = None
    persisted_proposal: EnhancedProposal | None = None

    def load_documents(self) -> Sequence[ProjectDocument]:
        return list(self.documents)

    def persist_key_concepts(self, concepts: Sequence[KeyConcept]) -> None:
        self.persisted_key_concepts = list(concepts)

    def persist_papers(self, papers: Sequence[ResearchPaper]) -> None:
        self.persisted_papers = list(papers)

    def persist_gap_analysis(self, analysis: ResearchGapAnalysis) -> None:
        self.persisted_gap = analysis

    def persist_enhanced_proposal(self, proposal: EnhancedProposal) -> None:
        self.persisted_proposal = proposal


class FakeReferenceService:
    def __init__(self, papers: Sequence[ResearchPaper]) -> None:
        self._primary_papers = list(papers)
        self._fallback_paper = ResearchPaper(
            identifier="secondary",
            title="Secondary Result",
            authors=("Quinn",),
            summary="Secondary",
            published="2024-02-01T00:00:00",
            raw_payload={"id": "secondary"},
        )
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
        self.queries.append((query, max_results))
        if not self.queries or len(self.queries) == 1:
            return self._primary_papers[:max_results]
        return [self._fallback_paper]


class FakeContentGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
            }
        )
        if "Gap Analysis" in system_prompt or "research scientist" in system_prompt:
            return "Gap analysis content"
        return "Enhanced proposal content"


def make_document(name: str, content: str) -> ProjectDocument:
    return ProjectDocument(name=name, content=content)


def make_paper(identifier: str, title: str) -> ResearchPaper:
    return ResearchPaper(
        identifier=identifier,
        title=title,
        authors=("Ada", "Turing"),
        summary="Summary of " + title,
        published="2024-01-01T00:00:00",
        raw_payload={"id": identifier},
    )


def test_enhance_generates_complete_result() -> None:
    documents = [
        make_document("CONTEXT_CONSTRAINTS.md", "## Overview\n- Data Pipelines\nThe **Syncretic Engine** operates."),
        make_document("BREAKTHROUGH_BLUEPRINT.md", "# HyperLoop Research\nBody of the blueprint."),
    ]
    repository = FakeRepository(documents)
    reference_service = FakeReferenceService([make_paper("primary", "Primary Paper")])
    generator = FakeContentGenerator()

    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
        max_concepts=3,
    )

    result = service.enhance(max_papers=2)

    assert result.project_title == "HyperLoop Research"
    concept_values = {concept.value for concept in result.key_concepts}
    assert {"Context Constraints", "Syncretic Engine"}.issubset(concept_values)
    assert repository.persisted_key_concepts == list(result.key_concepts)
    assert repository.persisted_gap and repository.persisted_gap.content == "Gap analysis content"
    assert repository.persisted_proposal and repository.persisted_proposal.content == "Enhanced proposal content"
    assert repository.persisted_papers and len(repository.persisted_papers) == 2
    assert reference_service.queries and any("Syncretic Engine" in query for query, _ in reference_service.queries)


def test_enhance_raises_when_no_documents() -> None:
    repository = FakeRepository([make_document("CONTEXT_CONSTRAINTS.md", "   ")])
    reference_service = FakeReferenceService([])
    generator = FakeContentGenerator()

    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    with pytest.raises(ProjectDocumentsNotFound):
        service.enhance()


def test_collect_papers_handles_duplicates_and_secondary_queries() -> None:
    primary = [make_paper("dup", "First"), make_paper("dup", "Duplicate")]
    secondary = make_paper("secondary", "Secondary")
    reference_service = FakeReferenceService(primary)
    reference_service._fallback_paper = secondary  # type: ignore[attr-defined]
    repository = FakeRepository([])
    generator = FakeContentGenerator()
    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    collected = service._collect_papers("content", ["concept"], max_papers=2)

    assert [paper.identifier for paper in collected] == ["dup", "secondary"]


def test_collect_papers_returns_when_no_key_concepts() -> None:
    reference_service = FakeReferenceService([])
    repository = FakeRepository([])
    generator = FakeContentGenerator()
    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    result = service._collect_papers("content", [], max_papers=1)

    assert result == []


def test_collect_papers_stops_when_target_met() -> None:
    class SimpleReferenceService(FakeReferenceService):
        def __init__(self) -> None:
            super().__init__([make_paper("p1", "Primary"), make_paper("p2", "Second")])

    service = ResearchEnhancementService(
        reference_service=SimpleReferenceService(),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    collected = service._collect_papers("content", ["concept"], max_papers=1)

    assert [paper.identifier for paper in collected] == ["p1"]


def test_collect_papers_breaks_secondary_loop_when_limit_reached() -> None:
    class SecondaryService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def search(self, query: str, *, max_results: int):
            self.calls.append(query)
            if len(self.calls) == 1:
                return [make_paper("primary", "Primary")]
            return [make_paper("s1", "Secondary One"), make_paper("s2", "Secondary Two")]

    service = ResearchEnhancementService(
        reference_service=SecondaryService(),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    collected = service._collect_papers("content", ["concept"], max_papers=2)

    assert [paper.identifier for paper in collected] == ["primary", "s1"]


def test_collect_papers_skips_duplicate_primary_results() -> None:
    class DuplicateService:
        def __init__(self) -> None:
            self.calls = 0

        def search(self, query: str, *, max_results: int):
            self.calls += 1
            if self.calls == 1:
                return [make_paper("dup", "First"), make_paper("dup", "Duplicate")]
            return []

    service = ResearchEnhancementService(
        reference_service=DuplicateService(),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    collected = service._collect_papers("content", ["concept"], max_papers=3)

    assert [paper.identifier for paper in collected] == ["dup"]


def test_collect_papers_skips_secondary_duplicates() -> None:
    class SecondaryDuplicateService:
        def __init__(self) -> None:
            self.calls = 0

        def search(self, query: str, *, max_results: int):
            self.calls += 1
            if self.calls == 1:
                return [make_paper("primary", "Primary")]
            return [
                make_paper("primary", "Duplicate"),
                make_paper("secondary", "Secondary"),
            ][:max_results]

    service = ResearchEnhancementService(
        reference_service=SecondaryDuplicateService(),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    collected = service._collect_papers("content", ["concept"], max_papers=3)

    assert [paper.identifier for paper in collected] == ["primary", "secondary"]


def test_extract_project_title_returns_unknown() -> None:
    repository = FakeRepository([])
    reference_service = FakeReferenceService([])
    generator = FakeContentGenerator()
    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    unknown = service._extract_project_title([make_document("OTHER.md", "No title")])
    assert unknown == "Unknown Project"


def test_extract_key_concepts_covers_paragraph_detection() -> None:
    service = ResearchEnhancementService(
        reference_service=FakeReferenceService([]),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
        max_concepts=3,
    )

    content = "Paragraph about Machine Learning Advances across industries. Another on Deep Insights."

    concepts = service._extract_key_concepts(content, max_concepts=2)
    assert concepts[0].startswith("Machine Learning Advances")


def test_truncate_appends_ellipsis() -> None:
    result = ResearchEnhancementService._truncate("x" * 10, limit=5)
    assert result == "xxxxx..."


def test_extract_key_concepts_returns_early_when_limit_reached() -> None:
    service = ResearchEnhancementService(
        reference_service=FakeReferenceService([]),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    content = "The **Important Concept** is emphasised."
    concepts = service._extract_key_concepts(content, max_concepts=1)

    assert any("Important Concept" in item for item in concepts)


def test_extract_key_concepts_stops_paragraph_loop_when_limit_reached() -> None:
    service = ResearchEnhancementService(
        reference_service=FakeReferenceService([]),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    content = "First paragraph cites Quantum Computing Advances. Next mentions Deep Insights."
    concepts = service._extract_key_concepts(content, max_concepts=1)

    assert len(concepts) == 1


def test_extract_key_concepts_breaks_before_processing_additional_paragraphs() -> None:
    service = ResearchEnhancementService(
        reference_service=FakeReferenceService([]),
        project_repository=FakeRepository([]),
        content_generator=FakeContentGenerator(),
    )

    content = (
        "Quantum Computing Advances are accelerating.\n\n"
        "Deep Insights emerge in follow-up discussions."
    )

    concepts = service._extract_key_concepts(content, max_concepts=1)

    assert concepts == ["Quantum Computing Advances"]
