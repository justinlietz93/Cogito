from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pytest

from syncretic_catalyst.application.research_generation.exceptions import (
    ProjectDocumentsNotFound,
)
from syncretic_catalyst.application.research_generation.services import (
    ResearchProposalGenerationService,
)
from syncretic_catalyst.domain import (
    DEFAULT_PROJECT_TITLE,
    ProjectDocument,
    ResearchProposalResult,
)


@dataclass
class FakeProjectRepository:
    documents: Sequence[ProjectDocument]

    def load_documents(self) -> Sequence[ProjectDocument]:
        return list(self.documents)


class FakeProposalRepository:
    def __init__(self) -> None:
        self.persisted: ResearchProposalResult | None = None

    def persist_generation(self, result: ResearchProposalResult) -> None:
        self.persisted = result


class FakeContentGenerator:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
            }
        )
        return self.response


def make_document(name: str, content: str) -> ProjectDocument:
    return ProjectDocument(name=name, content=content)


def test_generate_proposal_produces_result() -> None:
    repository = FakeProjectRepository(
        [
            make_document("CONTEXT_CONSTRAINTS.md", "Context"),
            make_document("BREAKTHROUGH_BLUEPRINT.md", "# Vision Title\nContent"),
        ]
    )
    output_repository = FakeProposalRepository()
    generator = FakeContentGenerator(" Proposal Content ")

    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=output_repository,
        content_generator=generator,
        max_tokens=5000,
    )

    result = service.generate_proposal(max_tokens=123)

    assert result.project_title == "Vision Title"
    assert result.proposal.content == "Proposal Content"
    assert output_repository.persisted == result
    assert generator.calls[0]["max_tokens"] == 123


def test_generate_proposal_raises_when_no_documents() -> None:
    repository = FakeProjectRepository([make_document("CONTEXT_CONSTRAINTS.md", "  ")])
    output_repository = FakeProposalRepository()
    generator = FakeContentGenerator("content")

    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=output_repository,
        content_generator=generator,
    )

    with pytest.raises(ProjectDocumentsNotFound):
        service.generate_proposal()


def test_generate_proposal_raises_on_error_response() -> None:
    repository = FakeProjectRepository(
        [make_document("BREAKTHROUGH_BLUEPRINT.md", "# Title\nBody")]
    )
    output_repository = FakeProposalRepository()
    generator = FakeContentGenerator("ERROR from provider: failure")

    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=output_repository,
        content_generator=generator,
    )

    with pytest.raises(RuntimeError):
        service.generate_proposal()


def test_generate_proposal_uses_default_title_when_missing_blueprint() -> None:
    repository = FakeProjectRepository([make_document("CONTEXT_CONSTRAINTS.md", "Context")])
    output_repository = FakeProposalRepository()
    generator = FakeContentGenerator("content")

    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=output_repository,
        content_generator=generator,
    )

    result = service.generate_proposal()

    assert result.project_title == DEFAULT_PROJECT_TITLE
