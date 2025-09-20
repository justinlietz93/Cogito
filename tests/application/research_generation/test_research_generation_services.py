from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))

from src.syncretic_catalyst.application.research_generation.exceptions import (
    ProjectDocumentsNotFound,
)
from src.syncretic_catalyst.application.research_generation.services import (
    ResearchProposalGenerationService,
)
from src.syncretic_catalyst.domain import ProjectDocument


class _InMemoryRepository:
    def __init__(self, documents: list[ProjectDocument]):
        self._documents = documents
        self.persisted = None

    def load_documents(self) -> list[ProjectDocument]:
        return list(self._documents)

    def persist_generation(self, result) -> None:
        self.persisted = result


class _FakeGenerator:
    def __init__(self, response: str = "Generated proposal"):
        self.calls: list[tuple[str, str, int]] = []
        self._response = response

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return self._response


def _build_documents() -> list[ProjectDocument]:
    return [
        ProjectDocument(
            name="CONTEXT_CONSTRAINTS.md",
            content="Context details",
        ),
        ProjectDocument(
            name="BREAKTHROUGH_BLUEPRINT.md",
            content="# Incredible Project\nSome description",
        ),
    ]


def test_generate_proposal_persists_result_and_returns_value():
    documents = _build_documents()
    repository = _InMemoryRepository(documents)
    generator = _FakeGenerator(response=" Final proposal ")
    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=repository,
        content_generator=generator,
        max_tokens=50,
    )

    result = service.generate_proposal(max_tokens=75)

    assert result.project_title == "Incredible Project"
    assert "===== Context Constraints =====" in result.prompt.content
    assert result.proposal.content == "Final proposal"

    assert repository.persisted is result
    assert len(generator.calls) == 1
    system_prompt, prompt_text, tokens = generator.calls[0]
    assert prompt_text == result.prompt.content
    assert tokens == 75
    assert system_prompt


def test_generate_proposal_without_documents_raises():
    repository = _InMemoryRepository(documents=[])
    generator = _FakeGenerator()
    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=repository,
        content_generator=generator,
    )

    with pytest.raises(ProjectDocumentsNotFound):
        service.generate_proposal()


def test_error_responses_raise_runtime_error():
    documents = _build_documents()
    repository = _InMemoryRepository(documents)
    generator = _FakeGenerator(response="ERROR from provider: something failed")
    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=repository,
        content_generator=generator,
    )

    with pytest.raises(RuntimeError):
        service.generate_proposal()

    assert repository.persisted is None
