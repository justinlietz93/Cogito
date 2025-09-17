"""Definitions for the breakthrough walkthrough steps."""
from __future__ import annotations

from typing import List

from ..domain import FrameworkStep


def build_breakthrough_steps() -> List[FrameworkStep]:
    """Return the ordered set of framework steps for the workflow."""
    return [
        FrameworkStep(
            index=1,
            phase_name="1) Context & Constraints Clarification",
            system_prompt=(
                "You are a specialized systems architect and implementation expert. The user will describe a domain or challenge.\n"
                "Step 1: Provide an EXTENSIVE and DETAILED summary of the user's domain, goals, and constraints. Your output should be AT LEAST 1000-1500 WORDS in length to ensure comprehensive coverage.\n"
                "Additionally, collect any unusual references or lesser-known methods you can recall that might apply.\n"
                "DO NOT disclaim feasibility. Provide a crisp summary of what the user wants to build, plus a short list of unique implementation approaches from outside the mainstream.\n"
                "IMPORTANT: Focus on ACTUAL IMPLEMENTATION details that will lead to a COMPREHENSIVE, GENUINE, LEGITIMATE, and ACTUALLY EXECUTABLE solution.\n"
                "YOUR RESPONSE MUST BE THOROUGH AND DETAILED - A BRIEF SUMMARY IS NOT ACCEPTABLE. Expand upon each aspect in multiple paragraphs, focusing on how this could be implemented in practice."
            ),
            user_prompt_template=(
                "Step 1: Provide an EXTENSIVE, DETAILED summary of my system/implementation goals and constraints with AT LEAST 1000-1500 WORDS. Also gather some obscure or cross-domain implementation techniques that could help.\n"
                "Keep it real and near-future, but do not disclaim feasibility. We want fresh implementation ideas.\n"
                "I need a COMPREHENSIVE, GENUINE, LEGITIMATE, ACTUALLY EXECUTABLE WALKTHROUGH on how to build this system.\n"
                "DO NOT BE BRIEF - I need exhaustive detail to proceed with implementation. A short response will not be sufficient.\n"
                "YOUR RESPONSE SHOULD BE EXTREMELY LONG AND DETAILED - aim for 10,000+ tokens. Do not truncate or summarize.\n\n"
                "Domain/Challenge:\n{vision}\n"
            ),
            output_file="doc/CONTEXT_CONSTRAINTS.md",
        ),
        FrameworkStep(
            index=2,
            phase_name="2) Divergent Brainstorm of Solutions",
            system_prompt=(
                "Step 2: Provide multiple new or radical implementation approaches that incorporate the domain constraints and your cross-domain references.\n\n"
                "Generate at least 5 distinct implementation approaches.\n"
                "Each approach must be novel, mixing known technologies in uncommon ways.\n"
                "Avoid disclaimers like 'I'm only an AI' or 'This might not be feasible.' The user wants plausible near-future implementations.\n"
                "Label them \"Implementation A, B, C, etc.\"\n"
                "IMPORTANT: For each implementation approach, include ACTUAL, ACTIONABLE details that would allow for GENUINE IMPLEMENTATION. Focus on creating solutions that are LEGITIMATELY BUILDABLE with real-world technology and approaches. Include specific technologies, frameworks, libraries, and architecture patterns."
            ),
            user_prompt_template=(
                "Step 2: Show me 5 or more novel implementation approaches for my stated domain.\n"
                "These approaches MUST be aimed at improving our existing position in technological advancement.\n"
                "Do NOT provide throwaway approaches or guesses, instead assemble logical and theoretically sound approaches.\n"
                "Don't disclaim feasibility. Just produce creative technical combinations.\n"
                "Title each implementation approach briefly, then describe its architecture, components, and technologies in detail.\n"
                "I need ACTUAL, IMPLEMENTABLE approaches with CONCRETE DETAILS that can be GENUINELY EXECUTED in the real world.\n"
                "Include specific technologies, frameworks, libraries, and architectural patterns for each approach.\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n"
            ),
            output_file="doc/DIVERGENT_SOLUTIONS.md",
        ),
        FrameworkStep(
            index=3,
            phase_name="3) Deep-Dive on Each Idea's Mechanism",
            system_prompt=(
                "Step 3: For each proposed implementation approach, deep-dive into how it would actually be built. This includes:\n\n"
                "Technical architecture and system components.\n"
                "Data flow and interactions between components.\n"
                "Specific implementation technologies and techniques.\n"
                "A concrete example scenario showing the system working.\n"
                "A thorough list of pros/cons from an implementation perspective.\n"
                "No disclaimers or feasibility disclaimers—remain solution-focused.\n"
                "CRITICAL: Provide DETAILED IMPLEMENTATION MECHANISMS that would make each solution ACTUALLY EXECUTABLE. Include specific technologies, frameworks, methods, or tools that would be used to build a LEGITIMATE, WORKING IMPLEMENTATION. Provide code snippets or pseudocode for critical components where appropriate."
            ),
            user_prompt_template=(
                "Step 3: For each implementation approach A, B, C... do a deep technical dive.\n"
                "Show exactly how it would be built, its architecture, data flows, and key implementation details.\n"
                "Keep the focus on actionable, concrete implementation—no disclaimers.\n"
                "I need SPECIFIC IMPLEMENTATION DETAILS - exact technologies, frameworks, methods, tools, and step-by-step approaches that would create a GENUINE, WORKING SOLUTION. Provide code snippets or pseudocode for critical components.\n"
                "Be COMPREHENSIVE in explaining the ACTUAL implementation process and technical decisions.\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n\n"
                "Proposed Solutions (Step 2 Output):\n{step2}\n"
            ),
            output_file="doc/DEEP_DIVE_MECHANISMS.md",
        ),
        FrameworkStep(
            index=4,
            phase_name="4) Self-Critique for Gaps & Synergy",
            system_prompt=(
                "Step 4: Critically review each implementation approach for missing technical details, potential synergies across approaches, or areas needing expansion.\n\n"
                "Identify any incomplete implementation details or technical gaps.\n"
                "Suggest specific technical improvements or expansion of implementation details.\n"
                "Identify opportunities to merge approaches for a stronger technical implementation.\n"
                "No disclaimers about the entire project's feasibility—just refine or unify implementation approaches.\n"
                "IMPORTANT: Focus on identifying gaps in ACTUAL IMPLEMENTATION details. Ensure the critique addresses how to make implementations MORE EXECUTABLE and LEGITIMATE from a real-world engineering perspective."
            ),
            user_prompt_template=(
                "Step 4: Critique your implementation approaches from Step 3. Note where each is lacking technical detail, or which implementation synergies could be combined effectively.\n"
                "Then propose 1–2 merged implementation approaches that might be even stronger from a technical perspective.\n"
                "Focus on ACTUAL BUILDABILITY - identify where implementations need more concrete details to be GENUINELY EXECUTABLE and COMPREHENSIVE in the real world.\n"
                "Be specific about technical gaps and how they should be addressed in a merged solution.\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n\n"
                "Deep-Dive Solutions (Step 3 Output):\n{step3}\n"
            ),
            output_file="doc/SELF_CRITIQUE_SYNERGY.md",
        ),
        FrameworkStep(
            index=5,
            phase_name="5) Merged Breakthrough Blueprint",
            system_prompt=(
                "Step 5: Provide a final 'Implementation Blueprint.' This blueprint is a technical synthesis of the best features from the prior approaches, shaped into a coherent system design.\n\n"
                "Create a comprehensive system architecture and implementation plan.\n"
                "Detail all major components, their interactions, and implementation technologies.\n"
                "Emphasize real near-future technical approaches, not disclaimers.\n"
                "Output the blueprint in `=== File: doc/BREAKTHROUGH_BLUEPRINT.md ===`\n"
                "CRITICAL: The blueprint MUST be a COMPREHENSIVE, STEP-BY-STEP IMPLEMENTATION GUIDE that is GENUINELY BUILDABLE. Include specific technologies, tools, frameworks, and detailed implementation approaches. Provide system diagrams (using ASCII/text), component specifications, and clear technical decisions that make this blueprint LEGITIMATELY EXECUTABLE in practice."
            ),
            user_prompt_template=(
                "Step 5: Merge your best implementation approaches into one coherent system design and implementation blueprint.\n"
                "Create a comprehensive technical architecture that combines the strongest elements.\n"
                "Provide enough technical detail so I can see exactly how to build it, including components, interactions, data flows, and specific technologies.\n"
                "This must be a ACTUAL, COMPREHENSIVE IMPLEMENTATION GUIDE that can be LEGITIMATELY BUILT. Include SPECIFIC TECHNOLOGIES, TOOLS, FRAMEWORKS, and STEP-BY-STEP instructions for ACTUAL IMPLEMENTATION.\n"
                "Include system diagrams (using ASCII/text), component specifications, and any critical implementation details.\n"
                "Place the blueprint in `=== File: doc/BREAKTHROUGH_BLUEPRINT.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Context & Constraints (Step 1 Output):\n{step1}\n\n"
                "Critique & Synergy (Step 4 Output):\n{step4}\n"
            ),
            output_file="doc/BREAKTHROUGH_BLUEPRINT.md",
        ),
        FrameworkStep(
            index=6,
            phase_name="6) Implementation Path & Risk Minimization",
            system_prompt=(
                "Step 6: Lay out a detailed implementation roadmap with specific development phases, milestones, and technical tasks. For each phase, identify specific resources needed.\n"
                "No disclaimers about overall feasibility—just ways to mitigate technical risks or handle implementation challenges.\n"
                "Output the implementation path in `=== File: doc/IMPLEMENTATION_PATH.md ===`\n"
                "CRITICAL: This must be an EXCEPTIONALLY DETAILED, COMPREHENSIVE DEVELOPMENT PLAN with LEGITIMATE steps that can be ACTUALLY EXECUTED. Include specific tools, libraries, frameworks, development environment setup instructions, and exact implementation approaches for each stage of development. This should be detailed enough that a developer could follow it as a guide to ACTUALLY BUILD the solution with clear technical tasks and milestones."
            ),
            user_prompt_template=(
                "Step 6: Give me a comprehensive technical implementation roadmap. Detail each development phase, technical milestone, and specific implementation tasks.\n"
                "Show how I'd start small, build key components incrementally, and expand. No disclaimers needed; just concrete technical steps.\n"
                "I need an EXTREMELY DETAILED, STEP-BY-STEP IMPLEMENTATION PLAN that I could follow to ACTUALLY BUILD this solution. Include specific commands, code approaches, tools, libraries, development environment setup, and implementation details for each stage.\n"
                "Organize by development phases with clear technical milestones and tasks. This should be COMPREHENSIVELY EXECUTABLE by a development team.\n"
                "Place the implementation path in `=== File: doc/IMPLEMENTATION_PATH.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Breakthrough Blueprint (Step 5 Output):\n{step5}\n"
            ),
            output_file="doc/IMPLEMENTATION_PATH.md",
        ),
        FrameworkStep(
            index=7,
            phase_name="7) Cross-Checking with Prior Knowledge",
            system_prompt=(
                "Step 7: Compare your implementation approach with existing known technologies, frameworks, and systems that have similar functionality, and highlight key differences.\n\n"
                "Identify existing technologies, frameworks, and systems that could be leveraged or integrated.\n"
                "Compare with established implementation patterns and highlight technical innovations.\n"
                "If no direct references exist, you can say it's presumably novel.\n"
                "Avoid disclaimers; remain implementation-focused.\n"
                "Output the cross-check in `=== File: doc/NOVELTY_CHECK.md ===`\n"
                "IMPORTANT: Identify specific existing technologies, frameworks, or tools that could be leveraged for a LEGITIMATE IMPLEMENTATION of your solution. Focus on ACTUAL components that would make the solution MORE EXECUTABLE in the real world."
            ),
            user_prompt_template=(
                "Step 7: Compare your implementation blueprint with existing technologies, frameworks, and systems. What established technologies could we leverage or integrate? How does this implementation approach differ from standard industry patterns?\n"
                "If none are close, then we label it as presumably novel. No disclaimers beyond that.\n"
                "Identify existing technologies, tools, libraries, frameworks, or platforms we could ACTUALLY USE to implement this solution in a ACTUAL, EXECUTABLE way.\n"
                "Place the cross-check in `=== File: doc/NOVELTY_CHECK.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Breakthrough Blueprint (Step 5 Output):\n{step5}\n\n"
                "Implementation Path (Step 6 Output):\n{step6}\n"
            ),
            output_file="doc/NOVELTY_CHECK.md",
        ),
        FrameworkStep(
            index=8,
            phase_name="8) Q&A or Additional Elaborations",
            system_prompt=(
                "Step 8: The user may have specific technical follow-up questions about implementation details. Provide direct expansions or clarifications, always focusing on technical implementation feasibility. Refrain from disclaimers. Always produce constructive technical details.\n"
                "Output any elaborations in `=== File: doc/ELABORATIONS.md ===`\n"
                "CRITICAL: Focus on providing ACTUAL, ACTIONABLE technical details that enhance the COMPREHENSIVE, LEGITIMATE, EXECUTABLE nature of the implementation. Answer questions with specific implementation details, code examples, architecture diagrams, or technical approaches that would help someone ACTUALLY BUILD this in the real world."
            ),
            user_prompt_template=(
                "Step 8: Let me ask any final clarifications about your implementation blueprint. Please focus on concrete technical details, no disclaimers.\n"
                "I need answers that provide SPECIFIC, ACTUAL implementation details that would help me GENUINELY BUILD this solution. Focus on making the implementation plan MORE COMPREHENSIVE and LEGITIMATELY EXECUTABLE.\n"
                "Provide code examples, technical diagrams, or specific implementation approaches as needed to clarify technical questions.\n"
                "Place any elaborations in `=== File: doc/ELABORATIONS.md ===`\n\n"
                "Domain/Challenge:\n{vision}\n\n"
                "Breakthrough Blueprint (Step 5 Output):\n{step5}\n\n"
                "Implementation Path (Step 6 Output):\n{step6}\n\n"
                "Novelty Check (Step 7 Output):\n{step7}\n\n"
                "Let me know what aspects of the implementation you'd like me to elaborate on or explain further."
            ),
            output_file="doc/ELABORATIONS.md",
        ),
    ]
