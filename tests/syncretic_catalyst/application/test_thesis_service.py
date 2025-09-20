from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MethodType
from typing import Iterable, Sequence

import pytest

from syncretic_catalyst.application.thesis.services import ThesisBuilderService
from syncretic_catalyst.domain import AgentProfile, ResearchPaper


@dataclass
class FakeReferenceService:
    primary_results: Sequence[ResearchPaper]
    secondary_result: ResearchPaper

    def __post_init__(self) -> None:
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
        self.queries.append((query, max_results))
        if len(self.queries) == 1:
            return list(self.primary_results[:max_results])
        return [self.secondary_result]


class FakeOutputRepository:
    def __init__(self) -> None:
        self.persisted_papers: Sequence[ResearchPaper] | None = None
        self.agent_outputs: list[tuple[str, AgentProfile, str]] = []
        self.persisted_thesis: tuple[str, str, str] | None = None
        self.persisted_report: tuple[str, str] | None = None

    def persist_papers(self, research_id: str, papers: Sequence[ResearchPaper]) -> None:
        self.persisted_papers = list(papers)

    def persist_agent_output(self, research_id: str, agent: AgentProfile, content: str) -> None:
        self.agent_outputs.append((research_id, agent, content))

    def persist_thesis(self, research_id: str, concept: str, thesis: str) -> None:
        self.persisted_thesis = (research_id, concept, thesis)

    def persist_report(self, research_id: str, report: str) -> None:
        self.persisted_report = (research_id, report)


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
        first_line = system_prompt.splitlines()[0]
        return f"{first_line} output"


class FakeClock:
    def now(self) -> datetime:
        return datetime(2024, 1, 1, 12, 0, 0)


def make_paper(identifier: str, title: str) -> ResearchPaper:
    return ResearchPaper(
        identifier=identifier,
        title=title,
        authors=("Ada", "Lin"),
        published="2024-01-01T00:00:00",
        summary="Summary",
        raw_payload={"id": identifier},
    )


def make_profile(name: str) -> AgentProfile:
    return AgentProfile(name=name, role=f"Role for {name}", system_prompt=f"{name} system prompt")


def test_build_thesis_runs_all_agents() -> None:
    papers = [make_paper("primary", "Primary Paper")]
    secondary = make_paper("secondary", "Secondary Paper")
    reference_service = FakeReferenceService(papers, secondary)
    output_repository = FakeOutputRepository()
    generator = FakeContentGenerator()
    clock = FakeClock()

    agent_profiles = [
        make_profile("Explorer"),
        make_profile("Analyst"),
        make_profile("SynthesisArbitrator"),
    ]

    service = ThesisBuilderService(
        reference_service=reference_service,
        output_repository=output_repository,
        content_generator=generator,
        clock=clock,
        agent_profiles=agent_profiles,
        max_tokens=1024,
    )

    result = service.build_thesis("Quantum Networking with Graph Embeddings", max_papers=3)

    assert result.concept == "Quantum Networking with Graph Embeddings"
    assert result.research_id == "20240101_120000"
    assert len(result.papers) == 2
    assert result.thesis and "SynthesisArbitrator" in result.thesis
    assert len(result.agent_outputs) == 3
    assert output_repository.persisted_papers == list(result.papers)
    assert output_repository.persisted_thesis[0] == result.research_id
    assert output_repository.persisted_report and "Comprehensive Research Report" in output_repository.persisted_report[1]
    assert reference_service.queries[0][0].startswith("Quantum Networking")
    assert len(output_repository.agent_outputs) == len(agent_profiles) - 1


def test_collect_papers_truncates_secondary_results_on_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CrowdedReferenceService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
            self.calls.append((query, max_results))
            if len(self.calls) == 1:
                return []
            return [
                make_paper("s1", "Secondary One"),
                make_paper("s2", "Secondary Two"),
                make_paper("s3", "Secondary Three"),
                make_paper("s4", "Secondary Four"),
            ]

    reference_service = CrowdedReferenceService()
    service = ThesisBuilderService(
        reference_service=reference_service,
        output_repository=FakeOutputRepository(),
        content_generator=FakeContentGenerator(),
        clock=FakeClock(),
        agent_profiles=[make_profile("SynthesisArbitrator")],
    )

    def fake_extract(self, concept: str, *, max_terms: int = 5) -> Sequence[str]:
        return ["Quantum Catalysis"]

    monkeypatch.setattr(
        service,
        "_extract_key_terms",
        MethodType(fake_extract, service),
    )

    collected = service._collect_papers("Quantum Catalysis", max_papers=3)

    assert [paper.identifier for paper in collected] == ["s1", "s2", "s3"]
    assert len(reference_service.calls) == 2


def test_collect_papers_breaks_before_querying_additional_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TrackingReferenceService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
            self.calls.append((query, max_results))
            if len(self.calls) == 1:
                return [make_paper("primary", "Primary")] 
            return [make_paper("secondary", "Secondary")]

    reference_service = TrackingReferenceService()
    service = ThesisBuilderService(
        reference_service=reference_service,
        output_repository=FakeOutputRepository(),
        content_generator=FakeContentGenerator(),
        clock=FakeClock(),
        agent_profiles=[make_profile("SynthesisArbitrator"), make_profile("Explorer")],
    )

    def fake_extract(self, concept: str, *, max_terms: int = 5) -> Sequence[str]:
        return ["first", "second"]

    monkeypatch.setattr(
        service,
        "_extract_key_terms",
        MethodType(fake_extract, service),
    )

    collected = service._collect_papers("Concept", max_papers=2)

    assert [paper.identifier for paper in collected] == ["primary", "secondary"]
    assert len(reference_service.calls) == 2


def test_extract_key_terms_deduplicates_case_insensitive() -> None:
    reference_service = FakeReferenceService(
        [make_paper("p", "Primary")],
        make_paper("s", "Secondary"),
    )
    service = ThesisBuilderService(
        reference_service=reference_service,
        output_repository=FakeOutputRepository(),
        content_generator=FakeContentGenerator(),
        clock=FakeClock(),
        agent_profiles=[make_profile("SynthesisArbitrator")],
    )

    terms = service._extract_key_terms(
        "Quantum Networks and quantum networks for Systems",
        max_terms=5,
    )

    lowered = [term.lower() for term in terms]
    assert len(lowered) == len(set(lowered))


def test_summarise_output_returns_first_paragraph() -> None:
    summary = ThesisBuilderService._summarise_output(
        "First paragraph.\n\nSecond paragraph."  # two paragraphs trigger the early return
    )

    assert summary == "First paragraph."
