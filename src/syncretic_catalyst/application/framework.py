"""Definitions for the breakthrough walkthrough steps."""
from __future__ import annotations

from typing import List

from ..domain import FrameworkStep
from ...prompt_texts import (
    BREAKTHROUGH_STEP_1_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_1_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_2_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_2_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_3_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_3_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_4_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_4_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_5_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_5_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_6_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_6_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_7_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_7_USER_PROMPT_TEMPLATE,
    BREAKTHROUGH_STEP_8_SYSTEM_PROMPT,
    BREAKTHROUGH_STEP_8_USER_PROMPT_TEMPLATE,
)


def build_breakthrough_steps() -> List[FrameworkStep]:
    """Return the ordered set of framework steps for the workflow."""
    return [
        FrameworkStep(
            index=1,
            phase_name="1) Context & Constraints Clarification",
            system_prompt=BREAKTHROUGH_STEP_1_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_1_USER_PROMPT_TEMPLATE,
            output_file="doc/CONTEXT_CONSTRAINTS.md",
        ),
        FrameworkStep(
            index=2,
            phase_name="2) Divergent Brainstorm of Solutions",
            system_prompt=BREAKTHROUGH_STEP_2_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_2_USER_PROMPT_TEMPLATE,
            output_file="doc/DIVERGENT_SOLUTIONS.md",
        ),
        FrameworkStep(
            index=3,
            phase_name="3) Deep-Dive on Each Idea's Mechanism",
            system_prompt=BREAKTHROUGH_STEP_3_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_3_USER_PROMPT_TEMPLATE,
            output_file="doc/DEEP_DIVE_MECHANISMS.md",
        ),
        FrameworkStep(
            index=4,
            phase_name="4) Self-Critique for Gaps & Synergy",
            system_prompt=BREAKTHROUGH_STEP_4_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_4_USER_PROMPT_TEMPLATE,
            output_file="doc/SELF_CRITIQUE_SYNERGY.md",
        ),
        FrameworkStep(
            index=5,
            phase_name="5) Merged Breakthrough Blueprint",
            system_prompt=BREAKTHROUGH_STEP_5_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_5_USER_PROMPT_TEMPLATE,
            output_file="doc/BREAKTHROUGH_BLUEPRINT.md",
        ),
        FrameworkStep(
            index=6,
            phase_name="6) Implementation Path & Risk Minimization",
            system_prompt=BREAKTHROUGH_STEP_6_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_6_USER_PROMPT_TEMPLATE,
            output_file="doc/IMPLEMENTATION_PATH.md",
        ),
        FrameworkStep(
            index=7,
            phase_name="7) Cross-Checking with Prior Knowledge",
            system_prompt=BREAKTHROUGH_STEP_7_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_7_USER_PROMPT_TEMPLATE,
            output_file="doc/NOVELTY_CHECK.md",
        ),
        FrameworkStep(
            index=8,
            phase_name="8) Q&A or Additional Elaborations",
            system_prompt=BREAKTHROUGH_STEP_8_SYSTEM_PROMPT,
            user_prompt_template=BREAKTHROUGH_STEP_8_USER_PROMPT_TEMPLATE,
            output_file="doc/ELABORATIONS.md",
        ),
    ]
