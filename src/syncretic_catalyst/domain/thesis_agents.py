"""Agent profiles used by the thesis builder workflow."""
from __future__ import annotations

from typing import Sequence

from .thesis import AgentProfile
from ...prompt_texts import (
    THESIS_AGENT_FOUNDATIONALLITERATUREEXPLORER_SYSTEM_PROMPT,
    THESIS_AGENT_MODERNRESEARCHSYNTHESIZER_SYSTEM_PROMPT,
    THESIS_AGENT_METHODOLOGICALVALIDATOR_SYSTEM_PROMPT,
    THESIS_AGENT_INTERDISCIPLINARYCONNECTOR_SYSTEM_PROMPT,
    THESIS_AGENT_MATHEMATICALFORMULATOR_SYSTEM_PROMPT,
    THESIS_AGENT_EVIDENCEANALYST_SYSTEM_PROMPT,
    THESIS_AGENT_IMPLICATIONEXPLORER_SYSTEM_PROMPT,
    THESIS_AGENT_SYNTHESISARBITRATOR_SYSTEM_PROMPT,
)


DEFAULT_AGENT_PROFILES: Sequence[AgentProfile] = (
    AgentProfile(
        name="FoundationalLiteratureExplorer",
        role=(
            "Explores historical and foundational literature relevant to the concept"
        ),
        system_prompt=THESIS_AGENT_FOUNDATIONALLITERATUREEXPLORER_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="ModernResearchSynthesizer",
        role="Analyzes current research landscape and identifies cutting-edge developments",
        system_prompt=THESIS_AGENT_MODERNRESEARCHSYNTHESIZER_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="MethodologicalValidator",
        role="Develops and validates methodological approaches for the concept",
        system_prompt=THESIS_AGENT_METHODOLOGICALVALIDATOR_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="InterdisciplinaryConnector",
        role="Explores connections across different disciplines and identifies novel applications",
        system_prompt=THESIS_AGENT_INTERDISCIPLINARYCONNECTOR_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="MathematicalFormulator",
        role="Develops mathematical frameworks and formal representations of the concept",
        system_prompt=THESIS_AGENT_MATHEMATICALFORMULATOR_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="EvidenceAnalyst",
        role="Gathers and analyzes empirical evidence related to the concept",
        system_prompt=THESIS_AGENT_EVIDENCEANALYST_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="ImplicationExplorer",
        role="Explores broader implications, applications, and future directions",
        system_prompt=THESIS_AGENT_IMPLICATIONEXPLORER_SYSTEM_PROMPT,
    ),
    AgentProfile(
        name="SynthesisArbitrator",
        role="Synthesizes inputs from all agents and creates a coherent thesis",
        system_prompt=THESIS_AGENT_SYNTHESISARBITRATOR_SYSTEM_PROMPT,
    ),
)
