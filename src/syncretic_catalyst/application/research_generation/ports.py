"""Ports for the research proposal generation workflow."""
from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import ProjectDocument, ResearchProposalResult


class ContentGenerator(Protocol):
    """Generates long-form content based on supplied prompts."""

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Return generated content for the provided prompts."""


class ProjectDocumentRepository(Protocol):
    """Provides access to the project documents."""

    def load_documents(self) -> Sequence[ProjectDocument]:
        """Return the available project documents in priority order."""


class ProposalRepository(Protocol):
    """Persists the artefacts produced by the generator."""

    def persist_generation(self, result: ResearchProposalResult) -> None:
        """Persist the combined generation result."""
