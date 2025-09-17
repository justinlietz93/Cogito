# src/critique_module/council_orchestrator.py

"""
Manages the Reasoning Council workflow. Includes initial content assessment,
critiques by either philosophical agents or scientific methodology agents,
followed by arbitration from a subject-matter expert agent.
Runs agents sequentially and distributes content points among critics.
"""
import logging
import random
from typing import Dict, List, Any, Type, Optional, Union, Mapping

# Import agent implementations
from .reasoning_agent import (
    ReasoningAgent,
    # Philosophical agents
    AristotleAgent, DescartesAgent, KantAgent, LeibnizAgent, PopperAgent, RussellAgent,
    # Scientific methodology agents
    SystemsAnalystAgent, FirstPrinciplesAnalystAgent, BoundaryConditionAnalystAgent,
    OptimizationAnalystAgent, EmpiricalValidationAnalystAgent, LogicalStructureAnalystAgent,
    # Arbiters
    ExpertArbiterAgent, ScientificExpertArbiterAgent
)
from .content_assessor import ContentAssessor
from .pipeline_input import PipelineInput, ensure_pipeline_input
from .council.logging import setup_agent_logger
from .council.adjustments import apply_self_critique_feedback, apply_arbitration_adjustments
from .council.synthesis import collect_significant_points

# Define agent types
PHILOSOPHER_AGENT_CLASSES: List[Type[ReasoningAgent]] = [
    AristotleAgent, DescartesAgent, KantAgent, LeibnizAgent, PopperAgent, RussellAgent
]

SCIENTIFIC_AGENT_CLASSES: List[Type[ReasoningAgent]] = [
    SystemsAnalystAgent, FirstPrinciplesAnalystAgent, BoundaryConditionAnalystAgent,
    OptimizationAnalystAgent, EmpiricalValidationAnalystAgent, LogicalStructureAnalystAgent
]

# Synchronous version
def run_critique_council(
    input_data: Union[PipelineInput, str, Mapping[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    peer_review: bool = False,
    scientific_mode: bool = False,
) -> Dict[str, Any]:
    """Execute the full critique workflow for the provided input."""

    root_logger = logging.getLogger(__name__)
    config = dict(config or {})

    pipeline_input = ensure_pipeline_input(input_data, allow_empty=True)
    content = pipeline_input.content

    pipeline_context = config.setdefault("pipeline_input", {})
    if isinstance(pipeline_context, dict):
        pipeline_context.update(
            {
                "source": pipeline_input.source,
                "metadata": dict(pipeline_input.metadata),
                "character_count": len(content),
            }
        )
    else:
        root_logger.debug("pipeline_input config entry is not a dict; skipping context enrichment.")

    if not content.strip():
        root_logger.warning("No content provided for critique; returning empty assessment.")
        return {
            "final_assessment": "No content provided for critique.",
            "points": [],
            "no_findings": True,
            "adjusted_critique_trees": [],
            "arbitration_adjustments": [],
            "arbiter_overall_score": None,
            "arbiter_score_justification": None,
            "score_metrics": {
                "high_severity_points": 0,
                "medium_severity_points": 0,
                "low_severity_points": 0,
            },
            "input_metadata": pipeline_input.metadata,
        }

    # Determine which agent classes to use based on mode
    agent_classes = SCIENTIFIC_AGENT_CLASSES if scientific_mode else PHILOSOPHER_AGENT_CLASSES
    agent_type_name = "scientific methodology" if scientific_mode else "philosopher"
    
    if not agent_classes:
        root_logger.error(
            "event=agent_selection status=error detail=%s",
            f"{agent_type_name.capitalize()} agent classes list is empty.",
        )
        raise ValueError(f"{agent_type_name.capitalize()} agent classes list is empty.")

    mode_label = "scientific" if scientific_mode else "philosophical"
    
    # 1. Initialize and Run Content Assessor to extract objective points
    root_logger.info("event=content_assessment phase=start mode=%s", mode_label)
    content_assessor = ContentAssessor()
    assessor_logger = setup_agent_logger(content_assessor.style, scientific_mode)
    if hasattr(content_assessor, 'set_logger'): content_assessor.set_logger(assessor_logger)
    
    try:
        extracted_points = content_assessor.extract_points(content, config)
        root_logger.info(
            "event=content_assessment phase=complete mode=%s extracted_points=%d",
            mode_label,
            len(extracted_points),
        )
    except Exception as e:
        root_logger.error(
            "event=content_assessment phase=failed mode=%s error=%s",
            mode_label,
            e,
            exc_info=True,
        )
        assessor_logger.error(f"Content assessment failed: {e}", exc_info=True)
        # If assessment fails, proceed without points
        extracted_points = []
        root_logger.warning("event=content_assessment phase=failed mode=%s action=continue", mode_label)
    
    # Distribute points among agents if points were extracted
    points_per_agent = {}
    if extracted_points:
        # Create a roughly equal distribution of points for each agent
        total_agents = len(agent_classes)
        points_per_agent_count = max(1, len(extracted_points) // total_agents)
        
        # Shuffle points for random distribution
        shuffled_points = extracted_points.copy()
        random.shuffle(shuffled_points)
        
        # Distribute points to agents
        for i, agent_cls in enumerate(agent_classes):
            start_idx = i * points_per_agent_count
            end_idx = start_idx + points_per_agent_count if i < total_agents - 1 else len(shuffled_points)
            points_per_agent[agent_cls.__name__] = shuffled_points[start_idx:end_idx]
            
        root_logger.info(
            "event=point_distribution status=complete mode=%s agents=%d",
            mode_label,
            total_agents,
        )

    # 1. Instantiate Agents and Setup Loggers
    reasoning_agents: List[ReasoningAgent] = []
    agent_loggers: Dict[str, logging.Logger] = {}
    for agent_cls in agent_classes:
        agent = agent_cls()
        agent_logger = setup_agent_logger(agent.style, scientific_mode)
        agent_loggers[agent.style] = agent_logger
        if hasattr(agent, 'set_logger'): agent.set_logger(agent_logger)
        reasoning_agents.append(agent)
    total_agents = len(reasoning_agents)

    # 2. Initial Critique Round (Agents run sequentially with their assigned points)
    root_logger.info(
        "event=critique_round phase=start round=initial mode=%s agents=%d",
        mode_label,
        total_agents,
    )
    initial_critiques: List[Dict[str, Any]] = []
    initial_errors = 0
    for i, agent in enumerate(reasoning_agents):
        agent_style = agent.style
        agent_logger = agent_loggers[agent_style]
        status = "OK"
        root_logger.info(
            "event=critique phase=run round=initial agent=%s peer_review=%s",
            agent_style,
            peer_review,
        )
        try:
            # Pass peer_review flag and assigned points to agent's critique method
            agent_points = points_per_agent.get(type(agent).__name__, [])
            result = agent.critique(content, config, agent_logger, peer_review=peer_review, assigned_points=agent_points)
            initial_critiques.append(result)
        except Exception as e:
            root_logger.error(
                "event=critique phase=run round=initial agent=%s peer_review=%s error=%s",
                agent_style,
                peer_review,
                e,
                exc_info=True,
            )
            agent_logger.error(f"Initial critique failed: {e}", exc_info=True)
            initial_critiques.append({'agent_style': agent_style, 'critique_tree': {}, 'error': str(e)})
            initial_errors += 1
            status = f"ERROR ({type(e).__name__})"
        root_logger.info(
            "event=critique phase=complete round=initial agent=%s status=%s",
            agent_style,
            status,
        )
    root_logger.info(
        "event=critique_round phase=complete round=initial mode=%s errors=%d",
        mode_label,
        initial_errors,
    )

    # 3. Self-Critique Round (Agents reflect on collective results)
    root_logger.info("event=critique_round phase=start round=self mode=%s", mode_label)
    self_critique_feedback: List[Dict[str, Any]] = []
    for agent, own_result in zip(reasoning_agents, initial_critiques):
        agent_style = agent.style
        agent_logger = agent_loggers[agent_style]
        try:
            peer_critiques = [crit for crit in initial_critiques if crit is not own_result]
            if hasattr(agent.self_critique, 'mock'):
                feedback = agent.self_critique.mock(agent, own_result, peer_critiques)
            else:
                feedback = agent.self_critique(own_result, peer_critiques, config, agent_logger)
            if feedback:
                self_critique_feedback.append(feedback)
        except Exception as exc:
            root_logger.error(
                "event=critique phase=self round=self agent=%s error=%s",
                agent_style,
                exc,
                exc_info=True,
            )
            agent_logger.error("Self-critique failed: %s", exc, exc_info=True)
            self_critique_feedback.append({
                'agent_style': agent_style,
                'error': str(exc),
            })
    root_logger.info("event=critique_round phase=complete round=self mode=%s", mode_label)

    if self_critique_feedback:
        root_logger.info("event=critique_round phase=adjustments source=self")
        apply_self_critique_feedback(initial_critiques, self_critique_feedback, root_logger)

    # 4. Arbitration Round (Expert Arbiter runs once)
    root_logger.info("event=arbitration phase=start mode=%s", mode_label)
    # Use the appropriate arbiter based on mode
    arbiter_agent = ScientificExpertArbiterAgent() if scientific_mode else ExpertArbiterAgent()
    arbiter_logger = setup_agent_logger(arbiter_agent.style, scientific_mode)
    if hasattr(arbiter_agent, 'set_logger'): arbiter_agent.set_logger(arbiter_logger)

    # Initialize arbiter result structure
    arbitration_result_data = {'adjustments': [], 'arbiter_overall_score': None, 'arbiter_score_justification': None, 'error': None}
    status = "OK"
    try:
        valid_critiques_for_arbiter = [c for c in initial_critiques if 'error' not in c]
        if valid_critiques_for_arbiter:
            root_logger.info(
                "event=arbitration phase=run agent=%s peer_review=%s",
                arbiter_agent.style,
                peer_review,
            )
            # Capture the full result dictionary from arbitrate, passing peer_review flag
            arbitration_result = arbiter_agent.arbitrate(
                content,
                valid_critiques_for_arbiter,
                config,
                arbiter_logger,
                peer_review=peer_review,
            )
            # Update the result data structure
            arbitration_result_data['adjustments'] = arbitration_result.get('adjustments', [])
            arbitration_result_data['arbiter_overall_score'] = arbitration_result.get('arbiter_overall_score')
            arbitration_result_data['arbiter_score_justification'] = arbitration_result.get('arbiter_score_justification')
            arbitration_result_data['error'] = arbitration_result.get('error')  # Capture potential error string

            if arbitration_result_data['error']:
                status = f"ERROR ({arbitration_result_data['error']})"
                root_logger.error(
                    "event=arbitration phase=run agent=%s status=error detail=%s",
                    arbiter_agent.style,
                    arbitration_result_data['error'],
                )
        else:
            status = "SKIPPED (No valid initial critiques)"
            root_logger.info("event=arbitration phase=skip reason=no_valid_critiques")

    except Exception as e:
        root_logger.error(
            "event=arbitration phase=run agent=%s error=%s",
            arbiter_agent.style,
            e,
            exc_info=True,
        )
        arbiter_logger.error(f"Arbitration call failed: {e}", exc_info=True)
        status = f"ERROR ({type(e).__name__})"
        arbitration_result_data['error'] = str(e) # Store exception string

    root_logger.info(
        "event=arbitration phase=complete status=%s adjustments=%d score=%s",
        status,
        len(arbitration_result_data['adjustments']),
        arbitration_result_data['arbiter_overall_score'],
    )


    # 5. Apply Arbitration Adjustments to Trees
    root_logger.info("event=arbitration phase=adjustments status=apply")
    adjusted_critique_trees = apply_arbitration_adjustments(
        initial_critiques,
        arbitration_result_data['adjustments'],
        root_logger,
    )

    # 6. Synthesize Final Data (Calculate severity counts based on adjusted trees)
    root_logger.info("event=synthesis phase=start mode=%s", mode_label)
    orchestrator_config = config.get('council_orchestrator', {})
    synthesis_payload = collect_significant_points(
        adjusted_critique_trees,
        orchestrator_config,
        scientific_mode,
        root_logger,
    )

    synthesized_data = {
        'final_assessment_summary': synthesis_payload['final_assessment_summary'],
        'final_assessment': synthesis_payload['final_assessment'],
        'adjusted_critique_trees': adjusted_critique_trees,
        'self_critique_feedback': self_critique_feedback,
        'arbitration_adjustments': arbitration_result_data['adjustments'],
        'arbiter_overall_score': arbitration_result_data['arbiter_overall_score'],
        'arbiter_score_justification': arbitration_result_data['arbiter_score_justification'],
        'no_findings': synthesis_payload['no_findings'],
        'points': synthesis_payload['points'],
        'score_metrics': synthesis_payload['score_metrics'],
    }
    root_logger.info("event=synthesis phase=complete mode=%s", mode_label)
    return synthesized_data
