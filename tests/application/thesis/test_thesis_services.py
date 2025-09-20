from datetime import datetime
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, os.fspath(ROOT))

from src.syncretic_catalyst.application.thesis.services import ThesisBuilderService
from src.syncretic_catalyst.domain import AgentProfile, ResearchPaper


class StubReferenceService:
    def __init__(self, responses):
        self._responses = list(responses)
        self.queries = []

    def search(self, query: str, *, max_results: int):
        if not self._responses:
            return []
        self.queries.append((query, max_results))
        return self._responses.pop(0)


class StubGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return f"response-for-{system_prompt.split()[-1]}"


class RecordingRepository:
    def __init__(self):
        self.papers_calls = []
        self.agent_calls = []
        self.thesis_calls = []
        self.report_calls = []

    def persist_papers(self, research_id: str, papers):
        self.papers_calls.append((research_id, list(papers)))

    def persist_agent_output(self, research_id: str, agent: AgentProfile, content: str):
        self.agent_calls.append((research_id, agent, content))

    def persist_thesis(self, research_id: str, concept: str, thesis: str):
        self.thesis_calls.append((research_id, concept, thesis))

    def persist_report(self, research_id: str, report: str):
        self.report_calls.append((research_id, report))


class FixedClock:
    def now(self) -> datetime:
        return datetime(2024, 1, 1, 12, 0, 0)


@pytest.fixture
def sample_papers():
    return [
        [
            ResearchPaper(
                identifier="id-1",
                title="Paper One",
                authors=("Alice",),
                published="2023-01-01T00:00:00Z",
                summary="Summary one",
                raw_payload={},
            )
        ],
        [
            ResearchPaper(
                identifier="id-2",
                title="Paper Two",
                authors=("Bob",),
                published="2022-05-05T00:00:00Z",
                summary="Summary two",
                raw_payload={},
            )
        ],
    ]


def test_build_thesis_runs_agents_and_persists_outputs(sample_papers):
    reference = StubReferenceService(sample_papers)
    generator = StubGenerator()
    repository = RecordingRepository()
    clock = FixedClock()
    profiles = [
        AgentProfile(name="Explorer", role="Explores", system_prompt="system explorer"),
        AgentProfile(name="SynthesisArbitrator", role="Synthesises", system_prompt="system synth"),
    ]

    service = ThesisBuilderService(
        reference_service=reference,
        output_repository=repository,
        content_generator=generator,
        clock=clock,
        agent_profiles=profiles,
    )

    result = service.build_thesis("Quantum Flux Resonator", max_papers=2)

    assert result.concept == "Quantum Flux Resonator"
    assert result.research_id == "20240101_120000"
    assert len(result.papers) == 2
    assert len(result.agent_outputs) == 2
    assert result.thesis == "response-for-synth"

    assert reference.queries[0] == ("Quantum Flux Resonator", 1)
    assert len(reference.queries) >= 2
    assert repository.papers_calls[0][0] == "20240101_120000"
    assert len(repository.agent_calls) == 1  # synthesis output uses persist_thesis instead
    assert repository.thesis_calls[0][1] == "Quantum Flux Resonator"
    assert repository.report_calls[0][0] == "20240101_120000"

    # Generator called for both the explorer and synthesis agents
    assert len(generator.calls) == 2
    assert generator.calls[0][0] == "system explorer"
    assert generator.calls[1][0] == "system synth"


def test_build_thesis_handles_reference_service_without_results():
    reference = StubReferenceService([[]])
    generator = StubGenerator()
    repository = RecordingRepository()
    clock = FixedClock()
    profiles = [
        AgentProfile(name="Explorer", role="Explores", system_prompt="system explorer"),
        AgentProfile(name="SynthesisArbitrator", role="Synthesises", system_prompt="system synth"),
    ]

    service = ThesisBuilderService(
        reference_service=reference,
        output_repository=repository,
        content_generator=generator,
        clock=clock,
        agent_profiles=profiles,
    )

    result = service.build_thesis("Novelty Analysis", max_papers=2)

    assert result.papers == []
    assert repository.papers_calls[0][1] == []
    assert result.thesis == "response-for-synth"
    assert any(call[0] == "20240101_120000" for call in repository.report_calls)


def test_build_thesis_propagates_generator_errors(sample_papers):
    reference = StubReferenceService(sample_papers)

    class FailingGenerator(StubGenerator):
        def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
            raise RuntimeError("generation failed")

    generator = FailingGenerator()
    repository = RecordingRepository()
    clock = FixedClock()
    profiles = [
        AgentProfile(name="Explorer", role="Explores", system_prompt="system explorer"),
        AgentProfile(name="SynthesisArbitrator", role="Synthesises", system_prompt="system synth"),
    ]

    service = ThesisBuilderService(
        reference_service=reference,
        output_repository=repository,
        content_generator=generator,
        clock=clock,
        agent_profiles=profiles,
    )

    with pytest.raises(RuntimeError, match="generation failed"):
        service.build_thesis("Quantum Flux Resonator", max_papers=2)
    assert repository.agent_calls == []
