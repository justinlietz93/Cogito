"""Service that generates complete research proposals from project documents."""
from __future__ import annotations

from typing import Sequence

from ...domain import (
    DEFAULT_DOCUMENT_ORDER,
    DEFAULT_PROJECT_TITLE,
    GeneratedProposal,
    ProposalPrompt,
    ProjectDocument,
    ResearchProposalResult,
)
from src.prompt_texts import (
    RESEARCH_GENERATION_SYSTEM_PROMPT,
    RESEARCH_PROPOSAL_PROMPT_TEMPLATE,
)
from .exceptions import ProjectDocumentsNotFound
from .ports import ContentGenerator, ProjectDocumentRepository, ProposalRepository

class ResearchProposalGenerationService:
    """Coordinates the research proposal generation workflow."""

    def __init__(
        self,
        *,
        project_repository: ProjectDocumentRepository,
        output_repository: ProposalRepository,
        content_generator: ContentGenerator,
        document_order: Sequence[str] | None = None,
        max_tokens: int = 20_000,
        system_prompt: str | None = None,
    ) -> None:
        self._project_repository = project_repository
        self._output_repository = output_repository
        self._generator = content_generator
        self._document_order = tuple(document_order or DEFAULT_DOCUMENT_ORDER)
        self._max_tokens = max(1, max_tokens)
        self._system_prompt = system_prompt or RESEARCH_GENERATION_SYSTEM_PROMPT

    def generate_proposal(self, *, max_tokens: int | None = None) -> ResearchProposalResult:
        """Generate a research proposal from the available project documents."""

        documents = list(self._project_repository.load_documents())
        ordered_documents = self._order_documents(documents)
        if not ordered_documents:
            raise ProjectDocumentsNotFound(
                "No project documents were found for proposal generation."
            )

        project_title = self._extract_project_title(ordered_documents)
        prompt_text = self._build_prompt(ordered_documents, project_title)
        prompt = ProposalPrompt(prompt_text)

        tokens = self._normalise_tokens(max_tokens)
        proposal_text = self._generator.generate(
            system_prompt=self._system_prompt,
            user_prompt=prompt_text,
            max_tokens=tokens,
        )
        cleaned_proposal = self._validate_response(proposal_text)

        result = ResearchProposalResult(
            project_title=project_title,
            prompt=prompt,
            proposal=GeneratedProposal(cleaned_proposal),
        )
        self._output_repository.persist_generation(result)
        return result

    def _order_documents(self, documents: Sequence[ProjectDocument]) -> list[ProjectDocument]:
        order_lookup = {name: index for index, name in enumerate(self._document_order)}
        ordered = sorted(
            documents,
            key=lambda doc: order_lookup.get(doc.name, len(self._document_order)),
        )
        return [doc for doc in ordered if doc.content.strip()]

    def _extract_project_title(self, documents: Sequence[ProjectDocument]) -> str:
        for document in documents:
            if document.name != "BREAKTHROUGH_BLUEPRINT.md":
                continue
            for line in document.content.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    if title:
                        return title
        return DEFAULT_PROJECT_TITLE

    def _build_prompt(
        self, documents: Sequence[ProjectDocument], project_title: str
    ) -> str:
        document_sections: list[str] = []
        for document in documents:
            section_name = document.name.replace(".md", "").replace("_", " ").title()
            document_sections.append(f"===== {section_name} =====")
            document_sections.append(document.content.rstrip())
            document_sections.append("")

        combined_sections = "\n".join(document_sections).strip()
        prompt = RESEARCH_PROPOSAL_PROMPT_TEMPLATE.format(
            project_title=project_title,
            document_sections=combined_sections,
        )
        return prompt.strip() + "\n"

    def _normalise_tokens(self, override: int | None) -> int:
        if override is None:
            return self._max_tokens
        return max(1, override)

    def _validate_response(self, response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("ERROR from"):
            raise RuntimeError(f"AI provider returned an error: {cleaned}")
        return cleaned
