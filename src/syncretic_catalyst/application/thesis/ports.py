"""Abstractions required by the thesis builder application layer."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from ...domain import AgentProfile, ResearchPaper


class ContentGenerator(Protocol):
    """Generates content for a research agent."""

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Return generated content for the provided prompts."""


class ReferenceService(Protocol):
    """Retrieves research papers for a given query."""

    def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
        """Return up to ``max_results`` papers that match the query."""


class ThesisOutputRepository(Protocol):
    """Persists the artefacts generated during thesis construction."""

    def persist_papers(self, research_id: str, papers: Sequence[ResearchPaper]) -> None:
        """Persist the retrieved papers for later inspection."""

    def persist_agent_output(self, research_id: str, agent: AgentProfile, content: str) -> None:
        """Persist the generated content for a single agent."""

    def persist_thesis(self, research_id: str, concept: str, thesis: str) -> None:
        """Persist the synthesized thesis output."""

    def persist_report(self, research_id: str, report: str) -> None:
        """Persist the final consolidated report."""


class Clock(Protocol):
    """Provides timestamps for generated artefacts."""

    def now(self) -> datetime:
        """Return the current timestamp."""
