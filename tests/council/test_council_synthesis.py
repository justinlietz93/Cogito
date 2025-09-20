import logging
from typing import Callable

import pytest

from src.council.synthesis import (
    collect_significant_points,
    extract_significant_points,
    resolve_cohort_label,
    _prepare_area_label_resolver,
)


def test_resolve_cohort_label_prefers_configured_labels() -> None:
    config = {
        "cohort_labels": {
            "scientific": "Scientific Council",
            "philosophical": "Philosophy Council",
            "default": "Fallback Label",
        }
    }

    assert resolve_cohort_label(config, True) == "Scientific Council"
    assert resolve_cohort_label(config, False) == "Philosophy Council"


def test_resolve_cohort_label_returns_defaults_for_missing_or_blank() -> None:
    config = {"cohort_labels": {"scientific": "  ", "default": ""}}

    assert resolve_cohort_label(config, True) == "Scientific Analyst"
    assert resolve_cohort_label(config, False) == "Philosopher"


def test_resolve_cohort_label_uses_default_fallback() -> None:
    config = {"cohort_labels": {"scientific": "", "default": "Interdisciplinary Council"}}

    assert resolve_cohort_label(config, True) == "Interdisciplinary Council"
    assert resolve_cohort_label(config, False) == "Interdisciplinary Council"


def test_prepare_area_label_resolver_handles_overrides_and_formatting(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.council.synthesis")
    config = {
        "cohort_labels": {"philosophical": "Philosophy Council"},
        "agent_area_labels": {
            "default": "Focus {style}",
            "Stoic": "Stoic Mentor",
            "Skeptic": "{style",
            "Mystic": 123,
        },
    }

    resolver = _prepare_area_label_resolver(config, False, logger)

    with caplog.at_level(logging.DEBUG):
        stoic_area = resolver("Stoic")
        rationalist_area = resolver("Rationalist")
        skeptic_area = resolver("Skeptic")
        mystic_area = resolver("Mystic")

    assert stoic_area == "Stoic Mentor"
    assert rationalist_area == "Focus Rationalist"
    assert skeptic_area == "{style: Skeptic"
    assert mystic_area == "Focus Mystic"
    debug_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]
    assert any("Failed to format area label override" in message for message in debug_messages)


def test_extract_significant_points_collects_nested_points() -> None:
    resolver: Callable[[str], str] = lambda style: f"Area {style}"
    tree = {
        "id": "root",
        "claim": "Root claim",
        "confidence": 0.752,
        "severity": "Critical",
        "arbitration": "Panel note",
        "sub_critiques": [
            {
                "id": "child",
                "claim": "Child claim",
                "confidence": 0.645,
                "severity": "Medium",
                "sub_critiques": [
                    {
                        "id": "grandchild",
                        "claim": "Grandchild claim",
                        "confidence": 0.601,
                        "severity": "Low",
                        "sub_critiques": [],
                    }
                ],
            }
        ],
    }

    points = extract_significant_points(tree, "Stoic", 0.6, resolver)

    assert points == [
        {
            "area": "Area Stoic",
            "critique": "Root claim",
            "severity": "Critical",
            "confidence": pytest.approx(0.75),
            "arbitration": "Panel note",
        },
        {
            "area": "Area Stoic",
            "critique": "Child claim",
            "severity": "Medium",
            "confidence": pytest.approx(0.65),
        },
        {
            "area": "Area Stoic",
            "critique": "Grandchild claim",
            "severity": "Low",
            "confidence": pytest.approx(0.6),
        },
    ]


def test_extract_significant_points_handles_invalid_nodes() -> None:
    resolver: Callable[[str], str] = lambda style: style

    assert extract_significant_points(None, "Stoic", 0.5, resolver) == []
    assert extract_significant_points({}, "Stoic", 0.5, resolver) == []
    assert extract_significant_points(
        {"id": "low", "claim": "Low confidence", "confidence": 0.2},
        "Stoic",
        0.5,
        resolver,
    ) == []


def test_collect_significant_points_compiles_summary_and_metrics() -> None:
    logger = logging.getLogger("tests.council.synthesis")
    orchestrator_config = {
        "synthesis_confidence_threshold": 0.6,
        "cohort_labels": {"philosophical": "Philosophy Council"},
        "agent_area_labels": {
            "default": "Focus {style}",
            "Empiricist": "Empiricist Analyst",
        },
    }
    critiques = [
        {
            "agent_style": "Empiricist",
            "critique_tree": {
                "id": "root",
                "claim": "High priority issue",
                "confidence": 0.72,
                "severity": "High",
                "arbitration": "Panel boost",
                "sub_critiques": [
                    {
                        "id": "sub-1",
                        "claim": "Follow-up medium",
                        "confidence": 0.68,
                        "severity": "Medium",
                        "sub_critiques": [],
                    },
                    {
                        "id": "sub-2",
                        "claim": "Follow-up low",
                        "confidence": 0.6,
                        "severity": "Low",
                        "sub_critiques": [],
                    },
                ],
            },
        },
        {
            "agent_style": "Empiricist",
            "critique_tree": {
                "id": "duplicate",
                "claim": "High priority issue",
                "confidence": 0.9,
                "severity": "Critical",
                "sub_critiques": [],
            },
        },
        {
            "agent_style": "Rationalist",
            "critique_tree": {
                "id": "other",
                "claim": "Different perspective",
                "confidence": 0.65,
                "severity": "Medium",
                "sub_critiques": [],
            },
        },
        {"agent_style": "Mystic", "critique_tree": {"id": "low", "claim": "Too low", "confidence": 0.4}},
        {"error": "Agent failure"},
        {"agent_style": "Invalid", "critique_tree": ["not", "a", "dict"]},
    ]

    result = collect_significant_points(critiques, orchestrator_config, False, logger)

    assert result["no_findings"] is False
    assert result["final_assessment"] == "Council identified 4 primary point(s) requiring attention."
    assert "Identified 4 significant point(s)" in result["final_assessment_summary"]
    assert len(result["points"]) == 4

    first_point = result["points"][0]
    assert first_point["area"] == "Empiricist Analyst"
    assert first_point["critique"] == "High priority issue"
    assert first_point["confidence"] == pytest.approx(0.72)
    assert first_point["arbitration"] == "Panel boost"

    assert result["points"][1]["area"] == "Empiricist Analyst"
    assert result["points"][2]["area"] == "Empiricist Analyst"
    assert result["points"][3]["area"] == "Focus Rationalist"

    assert result["score_metrics"] == {
        "high_severity_points": 1,
        "medium_severity_points": 2,
        "low_severity_points": 1,
    }


def test_collect_significant_points_reports_no_findings_when_below_threshold() -> None:
    logger = logging.getLogger("tests.council.synthesis")
    orchestrator_config = {"synthesis_confidence_threshold": 0.95}
    critiques = [
        {
            "agent_style": "Empiricist",
            "critique_tree": {
                "id": "root",
                "claim": "Insufficient confidence",
                "confidence": 0.5,
                "severity": "Medium",
                "sub_critiques": [],
            },
        }
    ]

    result = collect_significant_points(critiques, orchestrator_config, True, logger)

    assert result["no_findings"] is True
    assert result["points"] == []
    assert "No points met the significance threshold" in result["final_assessment"]
    assert result["score_metrics"] == {
        "high_severity_points": 0,
        "medium_severity_points": 0,
        "low_severity_points": 0,
    }
