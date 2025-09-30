# src/critique_module/reasoning_agent.py

"""
Defines the base class and specific implementations for reasoning agents
within the critique council. Supports both philosophical and scientific methodology agents.
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union

# Import reasoning tree logic
from .reasoning_tree import execute_reasoning_tree # Now synchronous
# Import provider factory for LLM clients
from .providers import call_with_retry
from .reasoning_agent_self_critique import build_self_critique_adjustments
from .prompt_texts import (
    CRITIQUE_ARISTOTLE_PROMPT,
    CRITIQUE_DESCARTES_PROMPT,
    CRITIQUE_KANT_PROMPT,
    CRITIQUE_LEIBNIZ_PROMPT,
    CRITIQUE_POPPER_PROMPT,
    CRITIQUE_RUSSELL_PROMPT,
    EXPERT_ARBITER_PROMPT,
    PEER_REVIEW_ENHANCEMENT,
    SCIENTIFIC_BOUNDARY_CONDITION_ANALYST_PROMPT,
    SCIENTIFIC_EMPIRICAL_VALIDATION_ANALYST_PROMPT,
    SCIENTIFIC_EXPERT_ARBITER_PROMPT,
    SCIENTIFIC_FIRST_PRINCIPLES_ANALYST_PROMPT,
    SCIENTIFIC_LOGICAL_STRUCTURE_ANALYST_PROMPT,
    SCIENTIFIC_OPTIMIZATION_ANALYST_PROMPT,
    SCIENTIFIC_PEER_REVIEW_ENHANCEMENT,
    SCIENTIFIC_SYSTEMS_ANALYST_PROMPT,
)

module_logger = logging.getLogger(__name__)

class ReasoningAgent(ABC):
    """
    Abstract base class for a reasoning agent in the critique council.
    """
    def __init__(self, style_name: str):
        self.style = style_name
        self.logger = module_logger

    def set_logger(self, logger: logging.Logger):
         self.logger = logger
         self.logger.info(f"Agent logger initialized for {self.style}")

    @abstractmethod
    def get_style_directives(self) -> str:
        pass

    # Synchronous
    def critique(self, content: str, config: Dict[str, Any], agent_logger: Optional[logging.Logger] = None, 
                peer_review: bool = False, assigned_points: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generates an initial critique synchronously. Applies peer review enhancement if flag is set.
        
        Args:
            content: The content to critique
            config: Configuration settings
            agent_logger: Optional logger to use
            peer_review: Whether to apply peer review enhancement
            assigned_points: Optional list of points assigned to this agent to address
        """
        current_logger = agent_logger or self.logger
        current_logger.info(f"Starting initial critique... (Peer Review: {peer_review}, Assigned Points: {len(assigned_points) if assigned_points else 0})")

        # Get base directives
        base_style_directives = self.get_style_directives()
        if "ERROR:" in base_style_directives:
             current_logger.error(f"Cannot perform critique due to prompt loading error: {base_style_directives}")
             return {
                 'agent_style': self.style,
                 'critique_tree': {},
                 'error': f"Failed to load style directives: {base_style_directives}"
             }

        # Apply enhancements if needed
        final_style_directives = base_style_directives
        
        # Apply peer review enhancement if needed
        if peer_review:
            final_style_directives += PEER_REVIEW_ENHANCEMENT
            current_logger.info("Peer Review enhancement applied to style directives.")
        
        # Apply assigned points enhancement if available
        if assigned_points and len(assigned_points) > 0:
            points_text = "\n\n--- ASSIGNED POINTS ENHANCEMENT ---\n"
            points_text += "You have been assigned to specifically address the following points from the content. "
            points_text += "While you are free to critique any aspects you find relevant, please PRIORITIZE addressing "
            points_text += "these assigned points through the lens of your philosophical framework:\n\n"
            
            for i, point in enumerate(assigned_points):
                point_id = point.get('id', f'point-{i+1}')
                point_text = point.get('point', 'No point text available')
                points_text += f"{i+1}. [{point_id}] {point_text}\n"
            
            points_text += "\n--- END ASSIGNED POINTS ENHANCEMENT ---\n"
            final_style_directives += points_text
            current_logger.info(f"Assigned Points enhancement applied with {len(assigned_points)} points.")

        critique_tree_result = execute_reasoning_tree(
            initial_content=content,
            style_directives=final_style_directives, # Use potentially enhanced directives
            agent_style=self.style,
            config=config,
            agent_logger=current_logger,
            assigned_points=assigned_points  # Pass assigned points to reasoning tree
        )

        if critique_tree_result is None:
             current_logger.warning("Critique generation terminated early (e.g., max depth or low confidence).")
             critique_tree_result = {
                 'id': 'root-terminated',
                 'claim': f'Critique generation terminated early for {self.style}.',
                 'evidence': '', 'confidence': 0.0, 'severity': 'N/A', 'sub_critiques': []
             }

        current_logger.info(f"Finished initial critique.")
        return {
            'agent_style': self.style,
            'critique_tree': critique_tree_result
        }

    # Synchronous
    def self_critique(
        self,
        own_critique: Dict[str, Any],
        other_critiques: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        agent_logger: Optional[logging.Logger] = None,
    ) -> Dict[str, Any]:
        """Compare this agent's critique with its peers and propose confidence adjustments."""

        current_logger = agent_logger or self.logger
        current_logger.info("Starting self-critique analysis...")

        adjustments = build_self_critique_adjustments(own_critique, other_critiques, config, current_logger)
        current_logger.info("Finished self-critique with %d adjustment(s).", len(adjustments))
        return {
            'agent_style': self.style,
            'adjustments': adjustments,
        }

# --- Concrete Agent Base Classes ---

class PromptAgent(ReasoningAgent):
    """Base class for agents with static prompt directives."""

    def __init__(self, name: str, prompt_text: str):
        super().__init__(name)
        self._prompt_text = prompt_text

    def get_style_directives(self) -> str:
        return self._prompt_text


class PhilosopherAgent(PromptAgent):
    """Base class for philosophical approach agents."""

    def __init__(self, name: str, prompt_text: str):
        super().__init__(name, prompt_text)


class ScientificAgent(PromptAgent):
    """Base class for scientific methodology agents."""

    def __init__(self, name: str, prompt_text: str):
        super().__init__(name, prompt_text)

# --- Specific Philosopher Agents ---

class AristotleAgent(PhilosopherAgent):
    """Critiques based on Aristotelian principles."""

    def __init__(self):
        super().__init__('Aristotle', CRITIQUE_ARISTOTLE_PROMPT)

class DescartesAgent(PhilosopherAgent):
    """Critiques based on Cartesian principles."""

    def __init__(self):
        super().__init__('Descartes', CRITIQUE_DESCARTES_PROMPT)

class KantAgent(PhilosopherAgent):
    """Critiques based on Kantian principles."""

    def __init__(self):
        super().__init__('Kant', CRITIQUE_KANT_PROMPT)

class LeibnizAgent(PhilosopherAgent):
    """Critiques based on Leibnizian principles."""

    def __init__(self):
        super().__init__('Leibniz', CRITIQUE_LEIBNIZ_PROMPT)

class PopperAgent(PhilosopherAgent):
    """Critiques based on Popperian principles."""

    def __init__(self):
        super().__init__('Popper', CRITIQUE_POPPER_PROMPT)

class RussellAgent(PhilosopherAgent):
    """Critiques based on Russellian principles."""

    def __init__(self):
        super().__init__('Russell', CRITIQUE_RUSSELL_PROMPT)

# --- Specific Scientific Methodology Agents ---

class SystemsAnalystAgent(ScientificAgent):
    """Critiques based on systems analysis methodology."""

    def __init__(self):
        super().__init__('SystemsAnalyst', SCIENTIFIC_SYSTEMS_ANALYST_PROMPT)

class FirstPrinciplesAnalystAgent(ScientificAgent):
    """Critiques based on first principles analysis methodology."""

    def __init__(self):
        super().__init__('FirstPrinciplesAnalyst', SCIENTIFIC_FIRST_PRINCIPLES_ANALYST_PROMPT)

class BoundaryConditionAnalystAgent(ScientificAgent):
    """Critiques based on boundary condition analysis methodology."""

    def __init__(self):
        super().__init__('BoundaryConditionAnalyst', SCIENTIFIC_BOUNDARY_CONDITION_ANALYST_PROMPT)

class OptimizationAnalystAgent(ScientificAgent):
    """Critiques based on optimization analysis methodology."""

    def __init__(self):
        super().__init__('OptimizationAnalyst', SCIENTIFIC_OPTIMIZATION_ANALYST_PROMPT)

class EmpiricalValidationAnalystAgent(ScientificAgent):
    """Critiques based on empirical validation analysis methodology."""

    def __init__(self):
        super().__init__('EmpiricalValidationAnalyst', SCIENTIFIC_EMPIRICAL_VALIDATION_ANALYST_PROMPT)

class LogicalStructureAnalystAgent(ScientificAgent):
    """Critiques based on logical structure analysis methodology."""

    def __init__(self):
        super().__init__('LogicalStructureAnalyst', SCIENTIFIC_LOGICAL_STRUCTURE_ANALYST_PROMPT)

# --- Expert Arbiter Agents ---

class ExpertArbiterBaseAgent(ReasoningAgent):
    """Base class for arbiter agents that evaluate critiques."""

    def __init__(self, name: str, prompt_text: str):
        super().__init__(name)
        self._prompt_text = prompt_text

    def get_style_directives(self) -> str:
        return self._prompt_text
    
    def critique(self, content: str, config: Dict[str, Any], agent_logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
        raise NotImplementedError("Arbiter agents do not perform initial critique.")

    def self_critique(self, own_critique: Dict[str, Any], other_critiques: List[Dict[str, Any]], config: Dict[str, Any], agent_logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
         raise NotImplementedError("Arbiter agents do not perform self-critique.")

class ExpertArbiterAgent(ExpertArbiterBaseAgent):
    """Arbiter for philosophical critiques."""

    def __init__(self):
        super().__init__('ExpertArbiter', EXPERT_ARBITER_PROMPT)

class ScientificExpertArbiterAgent(ExpertArbiterBaseAgent):
    """Arbiter for scientific methodology critiques."""

    def __init__(self):
        super().__init__('ScientificExpertArbiter', SCIENTIFIC_EXPERT_ARBITER_PROMPT)

# Define the common arbitration method that works for both philosophical and scientific approaches
def common_arbitrate(self, original_content: str, initial_critiques: List[Dict[str, Any]], config: Dict[str, Any], 
                    agent_logger: Optional[logging.Logger] = None, peer_review: bool = False, 
                    is_scientific: bool = False) -> Dict[str, Any]:
    """
    Evaluates critiques, provides adjustments, and calculates an arbiter score.
    Applies peer review enhancement if flag is set.
    Returns a dictionary including 'adjustments', 'arbiter_overall_score',
    'arbiter_score_justification', and potentially 'error'.
    
    Args:
        original_content: The original content to be analyzed
        initial_critiques: List of critiques from agents
        config: Configuration dictionary
        agent_logger: Optional logger
        peer_review: Whether to apply peer review enhancement
        is_scientific: Whether this is a scientific (vs philosophical) arbitration
    """
    current_logger = agent_logger or self.logger
    current_logger.info(f"Starting {'scientific' if is_scientific else 'philosophical'} arbitration... (Peer Review: {peer_review})")

    # Get base directives
    base_style_directives = self.get_style_directives()
    if "ERROR:" in base_style_directives:
         current_logger.error(f"Cannot perform arbitration due to prompt loading error: {base_style_directives}")
         # Return structure indicating error but including expected keys if possible
         return {'agent_style': self.style, 'adjustments': [], 'arbiter_overall_score': None, 'arbiter_score_justification': None, 'error': base_style_directives}

    # Apply enhancement if needed
    final_style_directives = base_style_directives
    if peer_review:
        if is_scientific:
            final_style_directives += SCIENTIFIC_PEER_REVIEW_ENHANCEMENT
            current_logger.info("Scientific Peer Review enhancement applied to arbiter directives.")
        else:
            final_style_directives += PEER_REVIEW_ENHANCEMENT
            current_logger.info("Peer Review enhancement applied to arbiter directives.")

    try:
        critiques_json_str = json.dumps(initial_critiques, indent=2)
    except TypeError as e:
        error_msg = f"Failed to serialize critiques to JSON: {e}"
        current_logger.error(error_msg, exc_info=True)
        return {'agent_style': self.style, 'adjustments': [], 'arbiter_overall_score': None, 'arbiter_score_justification': None, 'error': error_msg}

    # Use the appropriate context key based on whether this is scientific or philosophical
    critique_key = "scientific_critiques_json" if is_scientific else "philosophical_critiques_json"
    arbitration_context = {
        "original_content": original_content,
        critique_key: critiques_json_str
    }

    try:
        # Expecting structured JSON with adjustments, score, and justification
        arbitration_result, model_used = call_with_retry(
            prompt_template=final_style_directives, # Use potentially enhanced directives
            context=arbitration_context,
            config=config,
            is_structured=True
        )

        # Validate the richer structure
        if (isinstance(arbitration_result, dict) and
                'adjustments' in arbitration_result and
                isinstance(arbitration_result['adjustments'], list) and
                'arbiter_overall_score' in arbitration_result and
                'arbiter_score_justification' in arbitration_result):

             adj_count = len(arbitration_result['adjustments'])
             score = arbitration_result['arbiter_overall_score']
             justification = arbitration_result['arbiter_score_justification']
             current_logger.info(f"Arbitration completed using {model_used}. Score={score}. Found {adj_count} adjustments.")
             current_logger.debug(f"Arbiter Score Justification: {justification}")
             # Return the full result including score and justification
             return {
                 'agent_style': self.style,
                 'adjustments': arbitration_result['adjustments'],
                 'arbiter_overall_score': score,
                 'arbiter_score_justification': justification
             }
        else:
             current_logger.warning(f"Unexpected arbitration result structure received from {model_used}: {arbitration_result}")
             return {'agent_style': self.style, 'adjustments': [], 'arbiter_overall_score': None, 'arbiter_score_justification': None, 'error': 'Invalid arbitration result structure'}

    except Exception as e:
        error_msg = f"Arbitration failed: {e}"
        current_logger.error(error_msg, exc_info=True)
        return {'agent_style': self.style, 'adjustments': [], 'arbiter_overall_score': None, 'arbiter_score_justification': None, 'error': error_msg}

# Assign the common method to both arbiter classes
ExpertArbiterAgent.arbitrate = lambda self, original_content, initial_critiques, config, agent_logger=None, peer_review=False: common_arbitrate(
    self, original_content, initial_critiques, config, agent_logger, peer_review, is_scientific=False
)

ScientificExpertArbiterAgent.arbitrate = lambda self, original_content, initial_critiques, config, agent_logger=None, peer_review=False: common_arbitrate(
    self, original_content, initial_critiques, config, agent_logger, peer_review, is_scientific=True
)
