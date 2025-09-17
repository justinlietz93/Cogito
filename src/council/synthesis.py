"""Synthesis helpers for council critique results."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set

Point = Dict[str, Any]


def resolve_cohort_label(orchestrator_config: Mapping[str, Any], scientific_mode: bool) -> str:
    """Return a human-readable label for the active agent cohort."""
    default_label = "Scientific Analyst" if scientific_mode else "Philosopher"
    if isinstance(orchestrator_config, Mapping):
        labels_config = orchestrator_config.get("cohort_labels")
        if isinstance(labels_config, Mapping):
            key = "scientific" if scientific_mode else "philosophical"
            label_candidate = labels_config.get(key)
            if isinstance(label_candidate, str) and label_candidate.strip():
                return label_candidate.strip()
            default_candidate = labels_config.get("default")
            if isinstance(default_candidate, str) and default_candidate.strip():
                return default_candidate.strip()
    return default_label


def _prepare_area_label_resolver(
    orchestrator_config: Mapping[str, Any],
    scientific_mode: bool,
    logger: logging.Logger,
) -> Callable[[str], str]:
    cohort_label = resolve_cohort_label(orchestrator_config, scientific_mode)
    area_label_config = orchestrator_config.get("agent_area_labels", {})
    agent_area_overrides: Dict[str, str] = {}
    default_area_override: Optional[str] = None

    if isinstance(area_label_config, Mapping):
        for key, value in area_label_config.items():
            if not isinstance(value, str):
                continue
            if key == "default":
                stripped_value = value.strip()
                if stripped_value:
                    default_area_override = stripped_value
                continue
            agent_area_overrides[str(key)] = value.strip()

    def resolve_area_label(agent_style: str) -> str:
        override = agent_area_overrides.get(agent_style)
        candidate = override or default_area_override
        if candidate:
            candidate = candidate.strip()
            if candidate:
                if "{style" in candidate:
                    try:
                        return candidate.format(style=agent_style)
                    except (KeyError, IndexError, ValueError):
                        logger.debug(
                            "Failed to format area label override '%s' for agent '%s'. Falling back to cohort label.",
                            candidate,
                            agent_style,
                        )
                if agent_style in candidate:
                    return candidate
                return f"{candidate}: {agent_style}"
        return f"{cohort_label}: {agent_style}"

    return resolve_area_label


def extract_significant_points(
    node: Optional[Dict[str, Any]],
    agent_style: str,
    threshold: float,
    resolve_area_label: Callable[[str], str],
) -> List[Point]:
    points: List[Point] = []
    if not node or not isinstance(node, dict):
        return points

    confidence = node.get("confidence", 0.0)
    claim_text = node.get("claim", "N/A")
    if isinstance(confidence, (int, float)) and confidence >= threshold:
        point_data: Point = {
            "area": resolve_area_label(agent_style),
            "critique": claim_text,
            "severity": node.get("severity", "N/A"),
            "confidence": round(confidence, 2),
        }
        if node.get("arbitration"):
            point_data["arbitration"] = node["arbitration"]
        points.append(point_data)

    if isinstance(node.get("sub_critiques"), list):
        for sub_node in node["sub_critiques"]:
            points.extend(extract_significant_points(sub_node, agent_style, threshold, resolve_area_label))
    return points


def _summarize_points(points: Sequence[Point]) -> Dict[str, int]:
    metrics = {
        "high_severity_points": 0,
        "medium_severity_points": 0,
        "low_severity_points": 0,
    }
    for point in points:
        severity = str(point.get("severity", "")).lower()
        if severity in ("critical", "high"):
            metrics["high_severity_points"] += 1
        elif severity == "medium":
            metrics["medium_severity_points"] += 1
        elif severity == "low":
            metrics["low_severity_points"] += 1
    return metrics


def _build_assessments(points: Sequence[Point]) -> Dict[str, Any]:
    point_total = len(points)
    if not points:
        return {
            "no_findings": True,
            "final_assessment": "No points met the significance threshold for reporting.",
            "final_assessment_summary": (
                "Council synthesis complete. No points met the significance threshold for reporting after expert arbitration."
            ),
        }

    return {
        "no_findings": False,
        "final_assessment": f"Council identified {point_total} primary point(s) requiring attention.",
        "final_assessment_summary": (
            "Council synthesis complete. Identified "
            f"{point_total} significant point(s) across all critique levels after expert arbitration."
        ),
    }


def collect_significant_points(
    critiques: Iterable[Mapping[str, Any]],
    orchestrator_config: Mapping[str, Any],
    scientific_mode: bool,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Extract significant points and summarise the collective council findings."""
    threshold = orchestrator_config.get("synthesis_confidence_threshold", 0.4)
    resolve_area_label = _prepare_area_label_resolver(orchestrator_config, scientific_mode, logger)

    processed_claims: Set[str] = set()
    significant_points: List[Point] = []
    for critique in critiques:
        if "error" in critique:
            continue
        tree = critique.get("critique_tree")
        if not isinstance(tree, dict):
            continue
        agent_style = critique.get("agent_style", "Unknown")
        extracted_points = extract_significant_points(tree, agent_style, threshold, resolve_area_label)
        for point in extracted_points:
            claim = point.get("critique")
            if claim and claim not in processed_claims:
                processed_claims.add(claim)
                significant_points.append(point)

    assessments = _build_assessments(significant_points)
    metrics = _summarize_points(significant_points)

    return {
        "points": significant_points,
        "score_metrics": metrics,
        **assessments,
    }
