"""Domain models for the thesis builder workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence


@dataclass(frozen=True)
class AgentProfile:
    """Describes a specialized research agent."""

    name: str
    role: str
    system_prompt: str


@dataclass(frozen=True)
class ResearchPaper:
    """Minimal metadata captured for a research paper."""

    identifier: str | None
    title: str
    authors: Sequence[str]
    published: str | None = None
    summary: str | None = None
    raw_payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentOutput:
    """Stores the generated output for a given agent."""

    agent: AgentProfile
    content: str


@dataclass(frozen=True)
class ThesisResearchResult:
    """Aggregated result of a thesis-building run."""

    concept: str
    research_id: str
    timestamp: datetime
    papers: Sequence[ResearchPaper]
    agent_outputs: Sequence[AgentOutput]
    thesis: str | None = None
