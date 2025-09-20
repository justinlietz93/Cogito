"""Tests for the Markdown critique output formatter."""

from __future__ import annotations

import datetime
import runpy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))

from src import output_formatter
from src.reasoning_agent import PEER_REVIEW_ENHANCEMENT


def _stub_call_with_retry(result: Dict[str, Any]) -> Tuple[List[Tuple[tuple, dict]], Any]:
    """Return a stub ``call_with_retry`` implementation and capture list."""

    calls: List[Tuple[tuple, dict]] = []

    def _call_with_retry(*args: Any, **kwargs: Any) -> Tuple[Dict[str, Any], str]:
        calls.append((args, kwargs))
        return result, "mock-model"

    return calls, _call_with_retry


def test_format_critique_output_with_structured_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end smoke test covering successful formatting."""

    judge_payload = {
        "judge_summary_text": "Comprehensive review summarised.",
        "judge_overall_score": 95,
        "judge_score_justification": "Thorough justification."
    }
    captured_calls, fake_call = _stub_call_with_retry(judge_payload)
    monkeypatch.setattr(output_formatter, "call_with_retry", fake_call)

    fixed_now = datetime.datetime(2024, 1, 2, 15, 30, 0)

    class _FixedDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:  # type: ignore[override]
            return fixed_now

    monkeypatch.setattr(output_formatter.datetime, "datetime", _FixedDatetime)

    critique_tree = {
        "agent_style": "AgentA",
        "critique_tree": {
            "claim": "Primary issue",
            "severity": "high",
            "confidence": 0.82,
            "evidence": "Supporting evidence",  # ensure evidence logging path
            "recommendation": "Take action",
            "concession": "None",
            "sub_critiques": [
                {
                    "claim": "Secondary issue",
                    "severity": "low",
                    "confidence": 0.55,
                    "arbitration": "Resolved",
                    "sub_critiques": []
                }
            ],
        },
    }

    critique_data = {
        "adjusted_critique_trees": [critique_tree],
        "arbitration_adjustments": [
            {"target_claim_id": "claim-1", "arbitration_comment": "Clarified", "confidence_delta": 0.1}
        ],
        "arbiter_overall_score": 82,
        "arbiter_score_justification": "Balanced view.",
        "score_metrics": {
            "high_severity_points": 2,
            "medium_severity_points": 1,
            "low_severity_points": 0,
        },
    }

    report = output_formatter.format_critique_output(
        critique_data,
        original_content="Original manuscript text",
        config={"api": {"openai": {"model": "test-model"}}},
        peer_review=True,
    )

    assert "# Critique Assessment Report" in report
    assert "**Generated:** 2024-01-02 15:30:00" in report
    assert "## Overall Judge Summary" in report
    assert "Comprehensive review summarised." in report
    assert "- **Final Judge Score:** 95/100" in report
    assert "- **Expert Arbiter Score:** 82/100" in report
    assert "**Confidence Delta:** +0.10" in report
    assert "* **Claim:** Primary issue" in report
    assert "- **Severity:** high" in report
    assert "Resolved" in report
    assert "--- End of Report ---" in report

    assert captured_calls, "Expected judge API invocation"
    kwargs = captured_calls[0][1]
    assert kwargs["is_structured"] is True
    prompt = kwargs["prompt_template"]
    assert PEER_REVIEW_ENHANCEMENT.strip() in prompt
    context = kwargs["context"]
    trees = json.loads(context["adjusted_critique_trees_json"])
    assert trees[0]["agent_style"] == "AgentA"


def test_format_output_handles_agent_error_and_incomplete_trees(monkeypatch: pytest.MonkeyPatch) -> None:
    """Error annotations and malformed trees should still render informative output."""

    judge_payload = {
        "judge_summary_text": "Summary.",
        "judge_overall_score": 75,
        "judge_score_justification": "Adequate.",
    }
    _, fake_call = _stub_call_with_retry(judge_payload)
    monkeypatch.setattr(output_formatter, "call_with_retry", fake_call)

    critique_data = {
        "adjusted_critique_trees": [
            {"agent_style": "ErrorAgent", "error": "timeout"},
            {"agent_style": "EmptyTreeAgent", "critique_tree": "  "},
            {"agent_style": "MissingTreeAgent", "critique_tree": None},
        ],
        "arbitration_adjustments": [],
        "score_metrics": {},
    }

    report = output_formatter.format_critique_output(
        critique_data,
        original_content="Original",
        config={},
        peer_review=False,
    )

    assert "Error during critique" in report
    assert "Critique terminated early" in report
    assert "No valid critique tree" in report


def test_format_critique_output_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors from the provider should degrade gracefully."""

    def _raise(*_: Any, **__: Any) -> Tuple[dict, str]:
        raise RuntimeError("network down")

    monkeypatch.setattr(output_formatter, "call_with_retry", _raise)

    critique_data = {
        "adjusted_critique_trees": [],
        "arbitration_adjustments": [],
        "score_metrics": {},
    }

    result = output_formatter.format_critique_output(
        critique_data,
        original_content="Original",
        config={},
        peer_review=False,
    )

    assert "Error generating Judge summary" in result
    assert "No critique data available" in result


def test_format_critique_node_nested_structure() -> None:
    """The recursive formatter should produce nested bullet lists."""

    node = {
        "claim": "Top level",
        "severity": "medium",
        "confidence": 0.75,
        "sub_critiques": [
            {
                "claim": "Child",
                "severity": "low",
                "confidence": 0.6,
                "sub_critiques": [],
                "concession": "Improved",
            }
        ],
        "concession": "None",
    }

    lines = output_formatter.format_critique_node(node)

    assert lines[0].startswith("* **Claim:** Top level")
    assert any("- **Claim:** Child" in line for line in lines)
    assert any("Concession" in line for line in lines)


def test_format_output_without_adjustments(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no adjustments are present the summary should state this explicitly."""

    payload = {
        "judge_summary_text": "All good.",
        "judge_overall_score": 88,
        "judge_score_justification": "Sound reasoning.",
    }
    _, fake_call = _stub_call_with_retry(payload)
    monkeypatch.setattr(output_formatter, "call_with_retry", fake_call)

    critique_data = {
        "adjusted_critique_trees": [],
        "arbitration_adjustments": [],
        "score_metrics": {},
    }

    report = output_formatter.format_critique_output(
        critique_data,
        original_content="Original",
        config={},
        peer_review=False,
    )

    assert "provided no specific adjustments" in report


def test_generate_judge_summary_handles_missing_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing prompt file should surface a helpful error message."""

    def _failing_open(*args: Any, **kwargs: Any):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("builtins.open", _failing_open)

    summary, score, justification = output_formatter.generate_judge_summary_and_score(
        "Original text",
        [],
        {},
        {},
        peer_review=False,
    )

    assert "prompt file not found" in summary
    assert score is None
    assert justification == "N/A"


def test_generate_judge_summary_invalid_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected payloads should return a structured error message."""

    def _fake_call(**_: Any) -> Tuple[Dict[str, Any], str]:
        return {"unexpected": "payload"}, "mock"

    monkeypatch.setattr(output_formatter, "call_with_retry", _fake_call)

    summary, score, justification = output_formatter.generate_judge_summary_and_score(
        "Original",
        [],
        {},
        {},
        peer_review=False,
    )

    assert summary == "Error: Invalid Judge result structure."
    assert score is None
    assert justification == "N/A"


def test_output_formatter_main_entrypoint(capsys: pytest.CaptureFixture[str]) -> None:
    """Executing the module as a script should emit its informational message."""

    sys.modules.pop("src.output_formatter", None)
    runpy.run_module("src.output_formatter", run_name="__main__")

    captured = capsys.readouterr()
    assert "Direct execution of output_formatter.py example is limited." in captured.out

