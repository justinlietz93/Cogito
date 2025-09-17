"""Domain models for the Syncretic Catalyst workflows."""

from .models import FrameworkStep, ProjectFile
from .research_enhancement import (
    DEFAULT_DOCUMENT_ORDER,
    EnhancedProposal,
    KeyConcept,
    ProjectCorpus,
    ProjectDocument,
    ResearchEnhancementResult,
    ResearchGapAnalysis,
)
from .research_generation import (
    DEFAULT_PROJECT_TITLE,
    GeneratedProposal,
    ProposalPrompt,
    ResearchProposalResult,
)
from .thesis import AgentOutput, AgentProfile, ResearchPaper, ThesisResearchResult
from .thesis_agents import DEFAULT_AGENT_PROFILES

__all__ = [
    "AgentOutput",
    "AgentProfile",
    "DEFAULT_DOCUMENT_ORDER",
    "DEFAULT_AGENT_PROFILES",
    "DEFAULT_PROJECT_TITLE",
    "EnhancedProposal",
    "FrameworkStep",
    "GeneratedProposal",
    "KeyConcept",
    "ProjectFile",
    "ProjectCorpus",
    "ProjectDocument",
    "ProposalPrompt",
    "ResearchPaper",
    "ResearchEnhancementResult",
    "ResearchProposalResult",
    "ResearchGapAnalysis",
    "ThesisResearchResult",
]
