import logging
from copy import deepcopy

import pytest

from src.council.adjustments import (
    apply_adjustments_to_tree,
    apply_arbitration_adjustments,
    apply_self_critique_feedback,
)


@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("tests.council.adjustments")
    # Ensure deterministic logging during tests
    logger.propagate = True
    return logger


def test_apply_adjustments_to_tree_clamps_and_logs(logger: logging.Logger, caplog: pytest.LogCaptureFixture) -> None:
    tree = {
        "id": "root-claim",
        "confidence": 0.95,
        "sub_critiques": [
            {"id": "child-1", "confidence": 0.2, "sub_critiques": []},
            {"id": "child-2", "confidence": 0.4, "sub_critiques": []},
        ],
    }
    adjustments = {
        "root-claim": {"confidence_delta": 0.2, "arbitration_comment": "Panel boost"},
        "child-1": {"confidence_delta": 0.4},
        "child-2": {"confidence_delta": -0.9, "arbitration_comment": "Outlier"},
    }

    with caplog.at_level(logging.DEBUG):
        apply_adjustments_to_tree(tree, adjustments, logger)

    assert tree["confidence"] == 1.0
    assert tree["arbitration"] == "Panel boost"
    assert tree["sub_critiques"][0]["confidence"] == pytest.approx(0.6)
    assert tree["sub_critiques"][0].get("arbitration") is None
    assert tree["sub_critiques"][1]["confidence"] == 0.0
    assert tree["sub_critiques"][1]["arbitration"] == "Outlier"

    warning_messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any("clamped" in message for message in warning_messages)
    debug_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]
    assert any("Applied arbitration" in message for message in debug_messages)


def test_apply_adjustments_to_tree_returns_for_invalid_nodes(logger: logging.Logger) -> None:
    apply_adjustments_to_tree(None, {}, logger)
    apply_adjustments_to_tree("not-a-dict", {}, logger)  # type: ignore[arg-type]


def test_apply_self_critique_feedback_combines_adjustments(logger: logging.Logger, caplog: pytest.LogCaptureFixture) -> None:
    critiques = [
        {
            "agent_style": "Stoic",
            "critique_tree": {
                "id": "root-1",
                "confidence": 0.5,
                "sub_critiques": [
                    {"id": "child-1", "confidence": 0.2, "sub_critiques": []},
                    {"id": "child-2", "confidence": 0.9, "sub_critiques": []},
                ],
            },
        }
    ]
    feedback = [
        {
            "adjustments": [
                {"target_claim_id": "root-1", "confidence_delta": 0.25, "reasoning": "Initial boost"},
                {"target_claim_id": "child-1", "confidence_delta": 0.4},
            ]
        },
        {
            "adjustments": [
                {"target_claim_id": "root-1", "confidence_delta": -0.1, "comment": "Tie breaker"},
                {"target_claim_id": "child-2", "confidence_delta": -0.95, "comment": "Too strong"},
            ]
        },
    ]

    with caplog.at_level(logging.WARNING):
        result = apply_self_critique_feedback(deepcopy(critiques), feedback, logger)

    critique_tree = result[0]["critique_tree"]
    assert critique_tree["confidence"] == pytest.approx(0.65)
    assert critique_tree["arbitration"] == "Tie breaker"
    assert critique_tree["sub_critiques"][0]["confidence"] == pytest.approx(0.6)
    assert critique_tree["sub_critiques"][0].get("arbitration") is None
    assert critique_tree["sub_critiques"][1]["confidence"] == 0.0
    assert critique_tree["sub_critiques"][1]["arbitration"] == "Too strong"

    warning_messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert any("clamped" in message for message in warning_messages)


def test_apply_self_critique_feedback_returns_original_when_no_adjustments(logger: logging.Logger) -> None:
    critiques = [
        {
            "agent_style": "Skeptic",
            "critique_tree": {"id": "root", "confidence": 0.3, "sub_critiques": []},
        }
    ]
    feedback = [
        {"adjustments": [{"target_claim_id": None, "confidence_delta": 0.5}]},
        {"adjustments": []},
    ]

    result = apply_self_critique_feedback(critiques, feedback, logger)
    assert result is critiques
    assert critiques[0]["critique_tree"]["confidence"] == 0.3
    assert "arbitration" not in critiques[0]["critique_tree"]


def test_apply_arbitration_adjustments_filters_and_applies(logger: logging.Logger, caplog: pytest.LogCaptureFixture) -> None:
    critiques = [
        {
            "agent_style": "Stoic",
            "critique_tree": {
                "id": "root-claim",
                "confidence": 0.4,
                "sub_critiques": [],
            },
        }
    ]
    adjustments = [
        {"target_claim_id": "root-claim", "confidence_delta": 0.3, "arbitration_comment": "Expert override"},
        {"target_claim_id": "", "confidence_delta": 1.0},
        {"confidence_delta": 0.2},
    ]

    with caplog.at_level(logging.DEBUG):
        result = apply_arbitration_adjustments(deepcopy(critiques), adjustments, logger)

    assert result[0]["critique_tree"]["confidence"] == pytest.approx(0.7)
    assert result[0]["critique_tree"]["arbitration"] == "Expert override"
    debug_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]
    assert any("Applied arbitration" in message for message in debug_messages)


def test_apply_arbitration_adjustments_returns_copy_when_no_adjustments(logger: logging.Logger) -> None:
    critiques = [
        {
            "agent_style": "Stoic",
            "critique_tree": {"id": "root", "confidence": 0.4, "sub_critiques": []},
        }
    ]

    result = apply_arbitration_adjustments(critiques, [], logger)

    assert result is not critiques
    assert result[0] is critiques[0]
    assert result[0]["critique_tree"]["confidence"] == 0.4
    assert "arbitration" not in result[0]["critique_tree"]
