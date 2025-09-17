"""Domain models for research proposal generation."""
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_PROJECT_TITLE = "NeuroCognitive Architecture (NCA): A Brain-Inspired LLM Framework"


@dataclass(frozen=True)
class ProposalPrompt:
    """The assembled prompt sent to the language model."""

    content: str


@dataclass(frozen=True)
class GeneratedProposal:
    """Final proposal returned by the language model."""

    content: str


@dataclass(frozen=True)
class ResearchProposalResult:
    """Aggregated artefacts produced by the generator workflow."""

    project_title: str
    prompt: ProposalPrompt
    proposal: GeneratedProposal
