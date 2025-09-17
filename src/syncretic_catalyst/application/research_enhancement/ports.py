"""Ports for the research enhancement workflow."""
from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import (
    EnhancedProposal,
    KeyConcept,
    ProjectDocument,
    ResearchGapAnalysis,
    ResearchPaper,
)


class ContentGenerator(Protocol):
    """Generates long-form content based on supplied prompts."""

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Return generated content for the provided prompts."""


class ReferenceService(Protocol):
    """Retrieves research papers for a given query."""

    def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
        """Return up to ``max_results`` papers that match the query."""


class ProjectRepository(Protocol):
    """Provides access to project documents and persists enhancement artefacts."""

    def load_documents(self) -> Sequence[ProjectDocument]:
        """Return the available project documents in priority order."""

    def persist_key_concepts(self, concepts: Sequence[KeyConcept]) -> None:
        """Persist the extracted key concepts."""

    def persist_papers(self, papers: Sequence[ResearchPaper]) -> None:
        """Persist the retrieved research papers."""

    def persist_gap_analysis(self, analysis: ResearchGapAnalysis) -> None:
        """Persist the generated research gap analysis."""

    def persist_enhanced_proposal(self, proposal: EnhancedProposal) -> None:
        """Persist the enhanced research proposal."""

