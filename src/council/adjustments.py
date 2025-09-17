"""Helpers for applying council arbitration adjustments."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional

Adjustment = Dict[str, Any]


def apply_adjustments_to_tree(
    node: Optional[Dict[str, Any]],
    adjustment_map: Mapping[str, Adjustment],
    logger: logging.Logger,
) -> None:
    """Recursively apply arbitration adjustments to a critique node."""
    if not node or not isinstance(node, dict):
        return

    node_id = node.get("id")
    if node_id and node_id in adjustment_map:
        adjustment = adjustment_map[node_id]
        original_confidence = node.get("confidence", 0.0)
        delta = adjustment.get("confidence_delta", 0.0)
        raw_confidence = original_confidence + delta
        adjusted_confidence = max(0.0, min(1.0, raw_confidence))
        if adjusted_confidence != raw_confidence:
            logger.warning(
                "Confidence for claim '%s' clamped from %.2f to %.2f (original=%.2f, delta=%+.2f).",
                node_id,
                raw_confidence,
                adjusted_confidence,
                original_confidence,
                delta,
            )
        node["confidence"] = adjusted_confidence
        node["arbitration"] = adjustment.get("arbitration_comment")
        logger.debug(
            "Applied arbitration to claim '%s': Delta=%+.2f, NewConf=%.2f.",
            node_id,
            delta,
            adjusted_confidence,
        )

    if isinstance(node.get("sub_critiques"), list):
        for sub_node in node["sub_critiques"]:
            apply_adjustments_to_tree(sub_node, adjustment_map, logger)


def _build_self_adjustment_map(feedback: Iterable[Mapping[str, Any]]) -> Dict[str, Adjustment]:
    adjustment_map: Dict[str, Adjustment] = {}
    for entry in feedback:
        for adjustment in entry.get("adjustments", []) or []:
            target_id = adjustment.get("target_claim_id")
            if not target_id:
                continue
            bucket = adjustment_map.setdefault(target_id, {"confidence_delta": 0.0})
            bucket["confidence_delta"] += adjustment.get("confidence_delta", 0.0)
            comment = adjustment.get("reasoning") or adjustment.get("comment")
            if comment:
                bucket["arbitration_comment"] = comment
    return adjustment_map


def apply_self_critique_feedback(
    critiques: List[Dict[str, Any]],
    feedback: Iterable[Mapping[str, Any]],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Apply self-critique feedback adjustments to agent critique trees."""
    adjustment_map = _build_self_adjustment_map(feedback)
    if not adjustment_map:
        return critiques

    for critique in critiques:
        tree = critique.get("critique_tree")
        if isinstance(tree, dict):
            apply_adjustments_to_tree(tree, adjustment_map, logger)
    return critiques


def _build_arbitration_adjustment_map(adjustments: Iterable[Mapping[str, Any]]) -> Dict[str, Adjustment]:
    return {
        adjustment["target_claim_id"]: dict(adjustment)
        for adjustment in adjustments or []
        if adjustment.get("target_claim_id")
    }


def apply_arbitration_adjustments(
    critiques: List[Dict[str, Any]],
    adjustments: Iterable[Mapping[str, Any]],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Apply expert arbitration adjustments to critique trees."""
    adjustment_map = _build_arbitration_adjustment_map(adjustments)
    if not adjustment_map:
        return list(critiques)

    adjusted_critiques: List[Dict[str, Any]] = []
    for critique in critiques:
        tree = critique.get("critique_tree")
        if isinstance(tree, dict):
            apply_adjustments_to_tree(tree, adjustment_map, logger)
        adjusted_critiques.append(critique)
    return adjusted_critiques
