"""Helper utilities for evaluating self-critique adjustments."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_SELF_CRITIQUE_CONFIG = {
    'consensus_weight': 0.6,
    'severity_weight': 0.3,
    'max_delta': 0.35,
    'depth_decay': 0.2,
    'minimum_delta': 0.01,
}

SEVERITY_SCORES = {
    'critical': 1.0,
    'severe': 0.9,
    'major': 0.85,
    'high': 0.8,
    'significant': 0.7,
    'medium': 0.6,
    'moderate': 0.55,
    'balanced': 0.5,
    'low': 0.4,
    'minor': 0.35,
    'info': 0.2,
    'informational': 0.2,
    'none': 0.0,
    'n/a': 0.0,
}

SEVERITY_LABELS = {
    'critical': 'Critical',
    'severe': 'Severe',
    'major': 'Major',
    'high': 'High',
    'significant': 'Significant',
    'medium': 'Medium',
    'moderate': 'Moderate',
    'balanced': 'Balanced',
    'low': 'Low',
    'minor': 'Minor',
    'info': 'Info',
    'informational': 'Informational',
    'none': 'None',
    'n/a': 'N/A',
}

CONCESSION_NEGATIONS = {'', 'none', 'n/a', 'na', 'no concession', 'not applicable'}


def build_self_critique_adjustments(
    own_critique: Dict[str, Any],
    other_critiques: Iterable[Dict[str, Any]],
    config: Optional[Dict[str, Any]],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """Return structured confidence adjustments based on peer consensus heuristics."""

    current_logger = logger or logging.getLogger(__name__)
    own_tree = own_critique.get('critique_tree') if isinstance(own_critique, dict) else None
    if not isinstance(own_tree, dict) or not own_tree:
        current_logger.info("Self-critique skipped: no critique tree available.")
        return []

    peer_nodes: List[Dict[str, Any]] = []
    for peer in other_critiques or []:
        peer_tree = peer.get('critique_tree') if isinstance(peer, dict) else None
        peer_nodes.extend(node for node, _ in _collect_nodes(peer_tree))

    critique_config = dict(config.get('self_critique', {})) if isinstance(config, dict) else {}
    consensus_weight = float(critique_config.get('consensus_weight', DEFAULT_SELF_CRITIQUE_CONFIG['consensus_weight']))
    severity_weight = float(critique_config.get('severity_weight', DEFAULT_SELF_CRITIQUE_CONFIG['severity_weight']))
    max_delta = float(critique_config.get('max_delta', DEFAULT_SELF_CRITIQUE_CONFIG['max_delta']))
    depth_decay = float(critique_config.get('depth_decay', DEFAULT_SELF_CRITIQUE_CONFIG['depth_decay']))
    minimum_delta = float(critique_config.get('minimum_delta', DEFAULT_SELF_CRITIQUE_CONFIG['minimum_delta']))

    adjustments: List[Dict[str, Any]] = []
    for node, depth in _collect_nodes(own_tree):
        node_id = node.get('id')
        if not node_id:
            continue

        node_confidence = _normalise_confidence(node.get('confidence'))
        if node_confidence is None:
            continue

        node_severity_score = _severity_score(node.get('severity'))
        consensus = _summarise_peers(peer_nodes, node.get('assigned_point_id'))

        total_delta = 0.0
        reason_lines: List[str] = []

        peer_average = consensus.get('confidence_avg')
        if peer_average is not None:
            diff = peer_average - node_confidence
            if abs(diff) >= 0.05:
                consensus_delta = _clamp(diff * consensus_weight, -max_delta, max_delta)
                if abs(consensus_delta) >= minimum_delta:
                    total_delta += consensus_delta
                    direction = 'up' if consensus_delta > 0 else 'down'
                    reason_lines.append(
                        f"Adjusted {direction} toward peer confidence average {peer_average:.2f}."
                    )

        peer_severity_avg = consensus.get('severity_avg')
        if peer_severity_avg is not None:
            severity_diff = peer_severity_avg - node_severity_score
            if abs(severity_diff) >= 0.15:
                severity_delta = _clamp(severity_diff * severity_weight, -max_delta, max_delta)
                if abs(severity_delta) >= minimum_delta:
                    total_delta += severity_delta
                    label = consensus.get('severity_label') or 'peer consensus severity'
                    if severity_diff > 0:
                        reason_lines.append(f"Peers reported higher severity ({label}).")
                    else:
                        reason_lines.append(f"Peers reported lower severity ({label}).")

        concession_text = _normalise_text(node.get('concession')).lower()
        if concession_text and concession_text not in CONCESSION_NEGATIONS:
            concession_penalty = -min(0.1, 0.04 + len(concession_text) * 0.0005)
            total_delta += concession_penalty
            reason_lines.append("Agent conceded limitations in the critique, reducing confidence.")

        evidence_text = _normalise_text(node.get('evidence'))
        if node_severity_score >= 0.6 and evidence_text and len(evidence_text) < 40:
            total_delta += -0.05
            reason_lines.append("High severity finding has limited supporting evidence.")
        elif node_severity_score <= 0.45 and len(evidence_text) > 120 and node_confidence < 0.6:
            evidence_boost = min(0.08, 0.02 + len(evidence_text) / 2000)
            total_delta += evidence_boost
            reason_lines.append("Rich supporting evidence justifies a modest confidence increase.")

        depth_factor = max(0.45, 1.0 - depth_decay * depth)
        total_delta *= depth_factor

        total_delta = _clamp(total_delta, -max_delta, max_delta)

        if abs(total_delta) < minimum_delta or not reason_lines:
            continue

        reasoning = " ".join(reason_lines)
        adjustments.append({
            'target_claim_id': node_id,
            'confidence_delta': round(total_delta, 4),
            'reasoning': reasoning,
        })
        current_logger.debug(
            "Self-critique adjustment prepared for %s: delta=%+.4f (%s)",
            node_id,
            total_delta,
            reasoning,
        )

    return adjustments


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normalise_confidence(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def _severity_score(severity: Any) -> float:
    if severity is None:
        return 0.5
    normalized = str(severity).strip().lower()
    return SEVERITY_SCORES.get(normalized, 0.5)


def _canonical_severity(severity: Any) -> Optional[str]:
    if severity is None:
        return None
    normalized = str(severity).strip().lower()
    if not normalized:
        return None
    if normalized in SEVERITY_LABELS:
        return SEVERITY_LABELS[normalized]
    return str(severity).strip().title()


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _collect_nodes(tree: Optional[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], int]]:
    if not isinstance(tree, dict):
        return []
    stack: List[Tuple[Dict[str, Any], int]] = [(tree, 0)]
    collected: List[Tuple[Dict[str, Any], int]] = []
    while stack:
        node, depth = stack.pop()
        if not isinstance(node, dict):
            continue
        collected.append((node, depth))
        children = node.get('sub_critiques')
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    stack.append((child, depth + 1))
    return collected


def _filter_peer_nodes(peer_nodes: List[Dict[str, Any]], assigned_point: Optional[str]) -> List[Dict[str, Any]]:
    if not peer_nodes:
        return []
    if not assigned_point:
        return peer_nodes
    scoped = [node for node in peer_nodes if node.get('assigned_point_id') in (None, assigned_point)]
    return scoped or peer_nodes


def _summarise_peers(peer_nodes: List[Dict[str, Any]], assigned_point: Optional[str]) -> Dict[str, Optional[float]]:
    scoped = _filter_peer_nodes(peer_nodes, assigned_point)
    confidence_values = [_normalise_confidence(node.get('confidence')) for node in scoped]
    severity_values = [_severity_score(node.get('severity')) for node in scoped if node.get('severity') is not None]
    severity_labels = [_canonical_severity(node.get('severity')) for node in scoped if _canonical_severity(node.get('severity'))]
    consensus_label = None
    if severity_labels:
        consensus_label = Counter(severity_labels).most_common(1)[0][0]
    return {
        'confidence_avg': _mean(confidence_values),
        'severity_avg': _mean(severity_values),
        'severity_label': consensus_label,
    }


def _normalise_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()
