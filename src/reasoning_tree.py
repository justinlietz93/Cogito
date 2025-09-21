# src/critique_module/reasoning_tree.py

"""Recursive reasoning tree orchestration for critique generation.

Purpose:
    Drive the critique workflow by recursively delegating analysis tasks to
    language-model providers while capturing structured assessments and
    decomposition topics for follow-up passes.
External Dependencies:
    Depends on :mod:`src.providers` for model execution via ``call_with_retry``.
    No direct HTTP clients are instantiated here.
Fallback Semantics:
    Provider exceptions are logged and terminate the current branch without
    raising to callers; downstream logic continues operating on remaining
    branches.
Timeout Strategy:
    Timeout management is delegated to the provider adapters referenced through
    ``call_with_retry``. The module itself does not implement additional
    timeout logic.
"""

import logging
from typing import Dict, List, Any, Optional, Sequence, Mapping
import uuid
import json

# Import the provider factory
from .providers import call_with_retry, ProviderError, ApiCallError, ApiResponseError, JsonParsingError, JsonProcessingError

# Default configuration values
DEFAULT_MAX_DEPTH = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.3

module_logger = logging.getLogger(__name__)

_DECOMPOSITION_TOPIC_KEYS: Sequence[str] = ("topics", "items", "subtopics")


def _should_request_topic_array_schema(config: Mapping[str, Any]) -> bool:
    """Determine whether decomposition should request an array-only schema.

    Parameters
    ----------
    config:
        Application configuration containing provider and model selections.

    Returns
    -------
    bool
        ``True`` when the configured primary provider is OpenAI and the
        selected model identifier corresponds to an o-series Responses API
        model, otherwise ``False``.

    Raises
    ------
    None.

    Side Effects
    ------------
    None. The helper performs pure dictionary inspection.
    """

    api_section = config.get("api", {}) if isinstance(config, Mapping) else {}
    if not isinstance(api_section, Mapping):
        return False

    provider = str(api_section.get("primary_provider", "")).strip().lower()
    if provider != "openai":
        return False

    provider_config: Mapping[str, Any] | None = None
    providers_section = api_section.get("providers")
    if isinstance(providers_section, Mapping):
        candidate = providers_section.get("openai")
        if isinstance(candidate, Mapping):
            provider_config = candidate

    if provider_config is None:
        candidate = api_section.get("openai")
        if isinstance(candidate, Mapping):
            provider_config = candidate

    model_name = ""
    if provider_config is not None:
        raw_model = provider_config.get("model") or provider_config.get("model_name")
        if isinstance(raw_model, str):
            model_name = raw_model.strip().lower()

    if not model_name:
        return False

    if len(model_name) > 1 and model_name[0] == "o" and model_name[1].isdigit():
        return True

    return model_name in {"o1", "o1-mini", "o1-preview", "o3", "o3-mini"}


def _normalise_decomposition_topics(result: Any) -> tuple[List[str], Optional[Sequence[str]], Optional[str]]:
    """Normalise decomposition payloads into a list of topic strings.

    Args:
        result: Raw object returned by the decomposition provider call.

    Returns:
        Tuple containing three values:
            ``topics``: List of topic strings (may be empty when recursion should
            stop).
            ``observed_keys``: Sequence of keys seen when ``result`` is a mapping
            that does not expose expected topic fields. ``None`` when not
            applicable.
            ``structure``: String describing the unexpected structure (for
            example ``"list"``) when parsing fails. ``None`` when topics are
            returned successfully.
    """

    if isinstance(result, list):
        if all(isinstance(item, str) for item in result):
            return list(result), None, None
        return [], None, "list"

    if isinstance(result, dict):
        for key in _DECOMPOSITION_TOPIC_KEYS:
            value = result.get(key)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return list(value), None, None
        keys = tuple(sorted(str(item) for item in result.keys()))
        return [], keys, "mapping"

    return [], None, type(result).__name__

# Synchronous version
def execute_reasoning_tree(
    initial_content: str,
    style_directives: str,
    agent_style: str,
    config: Dict[str, Any],
    agent_logger: Optional[logging.Logger] = None,
    depth: int = 0,
    assigned_points: Optional[List[Dict[str, Any]]] = None,
    *,
    _warning_state: Optional[Dict[str, bool]] = None,
) -> Optional[Dict[str, Any]]:
    """Recursively generate a reasoning tree for critique generation.

    Args:
        initial_content: Content to critique.
        style_directives: Directives for the critique style.
        agent_style: Style identifier for the agent.
        config: Configuration settings and provider metadata.
        agent_logger: Optional logger to use.
        depth: Current depth in the reasoning tree.
        assigned_points: Optional list of points assigned to this agent.
        _warning_state: Internal mutable flag used to ensure decomposition
            warnings emit at most once per run.

    Returns:
        Structured node describing the critique branch or ``None`` when the
        branch terminates early.

    Raises:
        None. Provider exceptions are caught, logged, and result in branch
        termination.
    """

    current_logger = agent_logger or module_logger
    current_logger.info(f"Depth {depth}: Starting analysis...")

    warning_state = _warning_state if _warning_state is not None else {"emitted": False}

    tree_config = config.get('reasoning_tree', {})
    max_depth = tree_config.get('max_depth', DEFAULT_MAX_DEPTH)
    confidence_threshold = tree_config.get('confidence_threshold', DEFAULT_CONFIDENCE_THRESHOLD)

    # 1. Base Case Check
    if depth >= max_depth:
        current_logger.info(f"Depth {depth}: Terminating branch (Reason: Max Depth Reached [{max_depth}])")
        return None
    if len(initial_content) < 50:
         current_logger.info(f"Depth {depth}: Terminating branch (Reason: Content too small)")
         return None

    # --- LLM Integration ---
    node_id = str(uuid.uuid4())
    claim = f"Error generating claim at depth {depth}."
    evidence = "N/A"
    confidence = 0.0
    severity = "N/A"
    recommendation = "N/A"
    concession = "N/A" # Initialize concession field
    assigned_point_id = None # Initialize assigned point ID
    sub_topics_for_recursion = []
    model_used_for_assessment = "N/A"
    model_used_for_decomposition = "N/A"
    
    # Handle assigned points at the top level only
    current_assigned_point = None
    if depth == 0 and assigned_points and len(assigned_points) > 0:
        # For the top level analysis, select one of the assigned points
        # We'll rotate through assigned points as we generate sub-topics
        current_assigned_point = assigned_points[0]
        current_logger.info(f"Depth {depth}: Using assigned point: {current_assigned_point.get('id')}")
        assigned_point_id = current_assigned_point.get('id')

    # 2. Generate Assessment (Synchronous Call)
    # Use the prompt loaded by the agent, which now includes concession request
    assessment_prompt_template = style_directives # Use the full prompt content directly
    
    # Enhance context with assigned point information if available
    assessment_context = {
        # Context needed by the prompt template placeholders
        "context": "Critiquing provided steps.", # Generic context if not passed separately
        "goal": config.get("goal", "N/A"), # Pass goal if available in config
        "steps": initial_content, # Pass the current content segment as 'steps'
        "assigned_point_id": assigned_point_id, # Add assigned point ID if available
        "assigned_point": current_assigned_point.get('point', '') if current_assigned_point else None # Add assigned point text if available
    }
    try:
        assessment_result, model_used_for_assessment = call_with_retry(
            prompt_template=assessment_prompt_template,
            context=assessment_context,
            config=config,
            is_structured=True # Expecting JSON output
        )
        # Expect recommendation and concession fields now
        if isinstance(assessment_result, dict) and all(k in assessment_result for k in ["claim", "confidence", "severity", "recommendation", "concession"]):
            claim = assessment_result.get("claim", claim)
            evidence = assessment_result.get("evidence", evidence)
            confidence = float(assessment_result.get("confidence", 0.0))
            severity = assessment_result.get("severity", severity)
            recommendation = assessment_result.get("recommendation", recommendation)
            concession = assessment_result.get("concession", concession) # Extract concession
        else:
             current_logger.warning(f"Depth {depth}: Unexpected assessment structure received from {model_used_for_assessment}: {assessment_result}")
             pass

    except (ApiCallError, ApiResponseError, JsonParsingError, JsonProcessingError) as e:
        current_logger.error(f"Depth {depth}: Failed to generate assessment: {e}")
        confidence = 0.0
    except Exception as e:
        current_logger.error(f"Depth {depth}: Unexpected error during assessment: {e}", exc_info=True)
        confidence = 0.0

    current_logger.info(f"Depth {depth}: [Model: {model_used_for_assessment}] Claim='{claim}', Confidence={confidence:.2f}, Severity='{severity}'")
    if evidence != "N/A" and evidence: current_logger.debug(f"Depth {depth}: Evidence='{evidence}'")
    if recommendation != "N/A" and recommendation: current_logger.debug(f"Depth {depth}: Recommendation='{recommendation}'")
    if concession != "N/A" and concession and concession.lower() != "none": current_logger.debug(f"Depth {depth}: Concession='{concession}'") # Log concession if not "None"

    if confidence < confidence_threshold:
        current_logger.info(f"Depth {depth}: Terminating branch (Reason: Confidence {confidence:.2f} < Threshold {confidence_threshold})")
        return None

    # 3. Decomposition Identification (Synchronous Call)
    # (Decomposition logic remains the same, uses a separate prompt)
    decomposition_prompt_template = """
Based on the primary critique claim "{claim}", identify specific sub-topics, sub-arguments, or distinct sections within the following content segment that warrant deeper, more focused critique in the next level of analysis.

Style Directives (for context):
{style_directives}

Content Segment:
```
{content}
```

Return a JSON object with a "topics" field containing an array of concise strings that describe each sub-topic to explore next. If "topics" is unavailable for your model, you may instead use "items" or "subtopics" with the same array-of-strings structure. When no additional decomposition is required, return an empty array for the selected field. Example:
{{"topics": ["The definition of 'synergy' in paragraph 2", "The causality argument in section 3.1", "The empirical evidence cited for claim X"]}}
"""
    decomposition_context = {
        "claim": claim,
        "style_directives": style_directives, # Pass original style directives for context
        "content": initial_content
    }
    try:
        structured_schema: Optional[Dict[str, Any]] = None
        if _should_request_topic_array_schema(config):
            structured_schema = {
                "name": "decomposition_topics",
                "schema": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of sub-topic strings describing where to recurse in the "
                        "next critique depth."
                    ),
                },
            }
        decomposition_result, model_used_for_decomposition = call_with_retry(
            prompt_template=decomposition_prompt_template,
            context=decomposition_context,
            config=config,
            is_structured=True,
            structured_output_schema=structured_schema,
        )
        provider_name = (
            config.get("api", {}).get("primary_provider")
            if isinstance(config.get("api"), dict)
            else None
        ) or "unknown"
        topics, observed_keys, structure_type = _normalise_decomposition_topics(decomposition_result)
        if topics:
            sub_topics_for_recursion = topics
            current_logger.info(
                f"Depth {depth}: [Model: {model_used_for_decomposition}] Identified {len(sub_topics_for_recursion)} sub-topics for recursion."
            )
        else:
            if not warning_state["emitted"]:
                keys_fragment = (
                    ",".join(observed_keys) if observed_keys is not None else f"<{structure_type}>"
                )
                current_logger.warning(
                    "Depth %d: Unexpected decomposition structure provider=%s model=%s keys=%s expected_keys=%s",
                    depth,
                    provider_name,
                    model_used_for_decomposition,
                    keys_fragment,
                    "|".join(_DECOMPOSITION_TOPIC_KEYS),
                )
                warning_state["emitted"] = True

    except (ApiCallError, ApiResponseError, JsonParsingError, JsonProcessingError) as e:
        current_logger.error(f"Depth {depth}: Failed to identify decomposition points: {e}")
    except Exception as e:
        current_logger.error(f"Depth {depth}: Unexpected error during decomposition: {e}")


    # 4. Recursive Calls (Synchronous)
    sub_critiques = []
    if sub_topics_for_recursion:
        current_logger.debug(f"Depth {depth}: Using placeholder content division for recursion based on {len(sub_topics_for_recursion)} identified topics.")
        num_sub_points = len(sub_topics_for_recursion)
        segment_len = len(initial_content) // num_sub_points if num_sub_points > 0 else len(initial_content)
        
        # Distribute any remaining assigned points to sub-topics
        remaining_points = assigned_points[1:] if assigned_points and depth == 0 else None

        for i, sub_topic in enumerate(sub_topics_for_recursion):
            sub_content = initial_content[i * segment_len : (i + 1) * segment_len]
            current_logger.info(f"Depth {depth}: Recursing on sub-topic {i+1} ('{sub_topic}')...")
            
            # Pass points to sub-topics if available
            sub_assigned_points = None
            if remaining_points and i < len(remaining_points):
                sub_assigned_points = [remaining_points[i]]
                current_logger.info(f"Depth {depth}: Assigning point {remaining_points[i].get('id')} to sub-topic {i+1}")
            
            child_node = execute_reasoning_tree(
                initial_content=sub_content,
                style_directives=style_directives,
                agent_style=agent_style,
                config=config,
                agent_logger=current_logger,
                depth=depth + 1,
                assigned_points=sub_assigned_points,
                _warning_state=warning_state
            )
            if child_node:
                sub_critiques.append(child_node)

    # 5. Node Construction
    current_node = {
        'id': node_id,
        'claim': claim,
        'evidence': evidence,
        'confidence': confidence,
        'severity': severity,
        'recommendation': recommendation,
        'concession': concession, # Add concession to node
        'sub_critiques': sub_critiques
    }
    
    # Add assigned point information if available
    if assigned_point_id:
        current_node['assigned_point_id'] = assigned_point_id

    current_logger.info(f"Depth {depth}: Analysis complete for this level.")
    return current_node

# --- Example Usage ---
def run_example():
    print("NOTE: Reasoning tree example usage needs update for new recommendation/concession fields.")
    pass

if __name__ == '__main__':  # pragma: no cover - exercised via example invocation tests
    logging.basicConfig(level=logging.INFO)
    run_example()
