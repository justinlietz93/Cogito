"""Domain models for the research enhancement workflow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .thesis import ResearchPaper


DEFAULT_DOCUMENT_ORDER: tuple[str, ...] = (
    "CONTEXT_CONSTRAINTS.md",
    "DIVERGENT_SOLUTIONS.md",
    "DEEP_DIVE_MECHANISMS.md",
    "SELF_CRITIQUE_SYNERGY.md",
    "BREAKTHROUGH_BLUEPRINT.md",
    "IMPLEMENTATION_PATH.md",
    "NOVELTY_CHECK.md",
    "ELABORATIONS.md",
)


@dataclass(frozen=True)
class ProjectDocument:
    """Represents a single project document used for enhancement."""

    name: str
    content: str


@dataclass(frozen=True)
class ProjectCorpus:
    """Collection of project documents available for enhancement."""

    documents: Sequence[ProjectDocument]


@dataclass(frozen=True)
class KeyConcept:
    """Identified key concept extracted from the project corpus."""

    value: str


@dataclass(frozen=True)
class ResearchGapAnalysis:
    """Narrative analysis describing the research gaps."""

    content: str


@dataclass(frozen=True)
class EnhancedProposal:
    """Enhanced research proposal content."""

    content: str


@dataclass(frozen=True)
class ResearchEnhancementResult:
    """Aggregated outcome of the research enhancement workflow."""

    project_title: str
    key_concepts: Sequence[KeyConcept]
    papers: Sequence[ResearchPaper]
    gap_analysis: ResearchGapAnalysis
    enhanced_proposal: EnhancedProposal

