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
from .exceptions import ProjectDocumentsNotFound
from .ports import ContentGenerator, ProjectDocumentRepository, ProposalRepository

_SYSTEM_PROMPT = (
    "You are an expert software engineer and technical writer specializing in creating "
    "practical, step-by-step implementation guides that focus on building and creation "
    "rather than theory."
)


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
        self._system_prompt = system_prompt or _SYSTEM_PROMPT

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
        sections: list[str] = [
            f"Create a formal academic research proposal for a project titled \"{project_title}\".",
            "",
            "Use the following content from previous design documents to create a comprehensive, well-structured academic research proposal.",
            "Format it according to standard academic conventions with proper sections, citations, and academic tone.",
            "",
            "The research proposal should include:",
            "1. Title Page",
            "2. Abstract",
            "3. Introduction and Problem Statement",
            "4. Literature Review",
            "5. Research Questions and Objectives",
            "6. Methodology and Technical Approach",
            "7. Implementation Plan and Timeline",
            "8. Expected Results and Impact",
            "9. Conclusion",
            "10. References",
            "",
            "Below are the source documents to synthesize into the proposal:",
            "",
        ]

        for document in documents:
            section_name = document.name.replace(".md", "").replace("_", " ").title()
            sections.append(f"===== {section_name} =====")
            sections.append(document.content.rstrip())
            sections.append("")

        sections.extend(
            [
                "Create a cohesive, professionally formatted academic research proposal that integrates these materials.",
                "Use formal academic language and structure. Ensure proper citation of external works where appropriate.",
                "Focus on presenting this as a serious, innovative research initiative with clear methodology and expected outcomes.",
                "The proposal should be comprehensive enough for submission to a major research funding organization.",
            ]
        )
        return "\n".join(sections).strip() + "\n"

    def _normalise_tokens(self, override: int | None) -> int:
        if override is None:
            return self._max_tokens
        return max(1, override)

    def _validate_response(self, response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("ERROR from"):
            raise RuntimeError(f"AI provider returned an error: {cleaned}")
        return cleaned
