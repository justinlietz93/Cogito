"""Unit tests for :mod:`src.council_orchestrator`."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src import council_orchestrator
from src.pipeline_input import PipelineInput


def test_run_critique_council_returns_placeholder_when_content_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank content should short-circuit with an empty assessment."""

    recorded_context: Dict[str, Any] = {}

    class SentinelAssessor:
        style = "SentinelAssessor"

        def __init__(self) -> None:  # pragma: no cover - not expected to run
            raise AssertionError("Content assessor should not be instantiated for blank input")

    monkeypatch.setattr(council_orchestrator, "ContentAssessor", SentinelAssessor)
    monkeypatch.setattr(council_orchestrator, "setup_agent_logger", lambda *_, **__: logging.getLogger("test"))

    config: Dict[str, Any] = {"pipeline_input": recorded_context}
    pipeline_input = PipelineInput(content="   ", metadata={"topic": "philosophy"})

    result = council_orchestrator.run_critique_council(pipeline_input, config=config)

    assert result["no_findings"] is True
    assert result["points"] == []
    assert result["final_assessment"].startswith("No content provided")
    assert recorded_context == {
        "source": None,
        "metadata": {"topic": "philosophy"},
        "character_count": 3,
    }


def test_run_critique_council_raises_when_agent_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no agent classes are registered the orchestrator should bail out."""

    monkeypatch.setattr(council_orchestrator, "PHILOSOPHER_AGENT_CLASSES", [])

    with pytest.raises(ValueError):
        council_orchestrator.run_critique_council("content")


class _CooperativeAgent:
    """Test double that records interactions for later inspection."""

    instances: List["_CooperativeAgent"] = []

    def __init__(self) -> None:
        self.style = "CooperativeAgent"
        self.logger = None
        self.received: Dict[str, Any] = {}
        self.__class__.instances.append(self)

    def set_logger(self, logger: logging.Logger) -> None:
        self.logger = logger

    def critique(
        self,
        content: str,
        config: Dict[str, Any],
        agent_logger: logging.Logger,
        *,
        peer_review: bool,
        assigned_points: List[Dict[str, Any]] | None,
    ) -> Dict[str, Any]:
        self.received["critique"] = {
            "content": content,
            "peer_review": peer_review,
            "config": config,
            "assigned_points": list(assigned_points or []),
        }
        return {
            "agent_style": self.style,
            "critique_tree": {"id": "root-1", "confidence": 0.6, "sub_critiques": []},
        }

    def self_critique(
        self,
        own_result: Dict[str, Any],
        peer_critiques: List[Dict[str, Any]],
        config: Dict[str, Any],
        agent_logger: logging.Logger,
    ) -> Dict[str, Any]:
        self.received["self_critique"] = {
            "own": own_result,
            "peer": list(peer_critiques),
        }
        return {
            "agent_style": self.style,
            "adjustments": [
                {"target_claim_id": "root-1", "confidence_delta": -0.15, "reasoning": "peer consensus"}
            ],
        }


class _FailingAgent:
    """Test double that simulates failure paths."""

    instances: List["_FailingAgent"] = []

    def __init__(self) -> None:
        self.style = "FailingAgent"
        self.logger = None
        self.assigned_points: List[Dict[str, Any]] | None = None
        self.__class__.instances.append(self)

    def set_logger(self, logger: logging.Logger) -> None:
        self.logger = logger

    def critique(
        self,
        content: str,
        config: Dict[str, Any],
        agent_logger: logging.Logger,
        *,
        peer_review: bool,
        assigned_points: List[Dict[str, Any]] | None,
    ) -> Dict[str, Any]:
        self.assigned_points = list(assigned_points or [])
        raise RuntimeError("initial failure")

    def self_critique(
        self,
        own_result: Dict[str, Any],
        peer_critiques: List[Dict[str, Any]],
        config: Dict[str, Any],
        agent_logger: logging.Logger,
    ) -> Dict[str, Any]:
        raise ValueError("secondary failure")


def test_run_critique_council_coordinates_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the full orchestration flow including error branches."""

    _CooperativeAgent.instances.clear()
    _FailingAgent.instances.clear()

    monkeypatch.setattr(council_orchestrator.random, "shuffle", lambda seq: None)
    monkeypatch.setattr(council_orchestrator, "setup_agent_logger", lambda *_, **__: logging.getLogger("test"))

    class StubContentAssessor:
        style = "StubAssessor"

        def __init__(self) -> None:
            self.logger = None
            self.call_args: Dict[str, Any] = {}

        def set_logger(self, logger: logging.Logger) -> None:
            self.logger = logger

        def extract_points(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
            self.call_args = {"content": content, "config": config}
            return [
                {"id": "p1", "point": "First"},
                {"id": "p2", "point": "Second"},
                {"id": "p3", "point": "Third"},
            ]

    assessor_instances: List[StubContentAssessor] = []

    def _assessor_factory() -> StubContentAssessor:
        instance = StubContentAssessor()
        assessor_instances.append(instance)
        return instance

    monkeypatch.setattr(council_orchestrator, "ContentAssessor", _assessor_factory)

    monkeypatch.setattr(
        council_orchestrator,
        "PHILOSOPHER_AGENT_CLASSES",
        [_CooperativeAgent, _FailingAgent],
    )
    monkeypatch.setattr(
        council_orchestrator,
        "SCIENTIFIC_AGENT_CLASSES",
        [_CooperativeAgent, _FailingAgent],
    )

    applied_self_feedback: Dict[str, Any] = {}

    def _fake_apply_self_feedback(critiques: List[Dict[str, Any]], feedback: List[Dict[str, Any]], logger: logging.Logger) -> List[Dict[str, Any]]:
        applied_self_feedback["critiques"] = list(critiques)
        applied_self_feedback["feedback"] = list(feedback)
        return critiques

    monkeypatch.setattr(
        council_orchestrator,
        "apply_self_critique_feedback",
        _fake_apply_self_feedback,
    )

    captured_arbitration: Dict[str, Any] = {}

    def _fake_apply_arbitration(
        critiques: List[Dict[str, Any]],
        adjustments: List[Dict[str, Any]],
        logger: logging.Logger,
    ) -> List[Dict[str, Any]]:
        captured_arbitration["critiques"] = list(critiques)
        captured_arbitration["adjustments"] = list(adjustments)
        return [dict(critique) for critique in critiques]

    monkeypatch.setattr(
        council_orchestrator,
        "apply_arbitration_adjustments",
        _fake_apply_arbitration,
    )

    captured_collect: Dict[str, Any] = {}

    def _fake_collect_points(
        critiques: List[Dict[str, Any]],
        orchestrator_config: Dict[str, Any],
        scientific_mode: bool,
        logger: logging.Logger,
    ) -> Dict[str, Any]:
        captured_collect["critiques"] = list(critiques)
        captured_collect["config"] = dict(orchestrator_config)
        captured_collect["scientific_mode"] = scientific_mode
        return {
            "points": [{"critique": "Important", "severity": "high", "confidence": 0.7}],
            "score_metrics": {
                "high_severity_points": 1,
                "medium_severity_points": 0,
                "low_severity_points": 0,
            },
            "no_findings": False,
            "final_assessment": "Assessment",
            "final_assessment_summary": "Summary",
        }

    monkeypatch.setattr(
        council_orchestrator,
        "collect_significant_points",
        _fake_collect_points,
    )

    arbiter_calls: Dict[str, Any] = {}

    class StubScientificArbiter:
        style = "ScientificArbiter"

        def __init__(self) -> None:
            self.logger = None

        def set_logger(self, logger: logging.Logger) -> None:
            self.logger = logger

        def arbitrate(
            self,
            content: str,
            critiques: List[Dict[str, Any]],
            config: Dict[str, Any],
            logger: logging.Logger,
            *,
            peer_review: bool,
        ) -> Dict[str, Any]:
            arbiter_calls["content"] = content
            arbiter_calls["critiques"] = list(critiques)
            arbiter_calls["peer_review"] = peer_review
            arbiter_calls["config"] = config
            return {
                "adjustments": [
                    {"target_claim_id": "root-1", "confidence_delta": 0.2, "arbitration_comment": "override"}
                ],
                "arbiter_overall_score": 0.85,
                "arbiter_score_justification": "weighted consensus",
            }

    class _ShouldNotUse:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - defensive
            raise AssertionError("Expected scientific arbiter to be used")

    monkeypatch.setattr(council_orchestrator, "ScientificExpertArbiterAgent", StubScientificArbiter)
    monkeypatch.setattr(council_orchestrator, "ExpertArbiterAgent", _ShouldNotUse)

    config: Dict[str, Any] = {
        "pipeline_input": {"existing": "value"},
        "council_orchestrator": {"synthesis_confidence_threshold": 0.5},
    }
    pipeline_input = PipelineInput(
        content="Important text",
        source="unit-test",
        metadata={"topic": "ai"},
    )

    result = council_orchestrator.run_critique_council(
        pipeline_input,
        config=config,
        peer_review=True,
        scientific_mode=True,
    )

    assert assessor_instances and assessor_instances[0].call_args["content"] == "Important text"
    assert assessor_instances[0].call_args["config"] == config

    assert len(_CooperativeAgent.instances) == 1
    assert _CooperativeAgent.instances[0].received["critique"]["peer_review"] is True
    assert _CooperativeAgent.instances[0].received["critique"]["assigned_points"] == [{"id": "p1", "point": "First"}]

    assert len(_FailingAgent.instances) == 1
    assert _FailingAgent.instances[0].assigned_points == [
        {"id": "p2", "point": "Second"},
        {"id": "p3", "point": "Third"},
    ]

    assert arbiter_calls["critiques"] == [
        {
            "agent_style": "CooperativeAgent",
            "critique_tree": {"id": "root-1", "confidence": 0.6, "sub_critiques": []},
        }
    ]
    assert arbiter_calls["peer_review"] is True

    assert applied_self_feedback["feedback"] == [
        {
            "agent_style": "CooperativeAgent",
            "adjustments": [
                {"target_claim_id": "root-1", "confidence_delta": -0.15, "reasoning": "peer consensus"}
            ],
        },
        {"agent_style": "FailingAgent", "error": "secondary failure"},
    ]

    assert captured_arbitration["adjustments"] == [
        {"target_claim_id": "root-1", "confidence_delta": 0.2, "arbitration_comment": "override"}
    ]
    assert captured_collect["critiques"] == [
        {
            "agent_style": "CooperativeAgent",
            "critique_tree": {"confidence": 0.6, "id": "root-1", "sub_critiques": []},
        },
        {
            "agent_style": "FailingAgent",
            "critique_tree": {},
            "error": "initial failure",
        },
    ]
    assert captured_collect["scientific_mode"] is True

    assert result == {
        "final_assessment_summary": "Summary",
        "final_assessment": "Assessment",
        "adjusted_critique_trees": [
            {
                "agent_style": "CooperativeAgent",
                "critique_tree": {"confidence": 0.6, "id": "root-1", "sub_critiques": []},
            },
            {
                "agent_style": "FailingAgent",
                "critique_tree": {},
                "error": "initial failure",
            },
        ],
        "self_critique_feedback": [
            {
                "agent_style": "CooperativeAgent",
                "adjustments": [
                    {"target_claim_id": "root-1", "confidence_delta": -0.15, "reasoning": "peer consensus"}
                ],
            },
            {"agent_style": "FailingAgent", "error": "secondary failure"},
        ],
        "arbitration_adjustments": [
            {"target_claim_id": "root-1", "confidence_delta": 0.2, "arbitration_comment": "override"}
        ],
        "arbiter_overall_score": 0.85,
        "arbiter_score_justification": "weighted consensus",
        "no_findings": False,
        "points": [{"critique": "Important", "severity": "high", "confidence": 0.7}],
        "score_metrics": {
            "high_severity_points": 1,
            "medium_severity_points": 0,
            "low_severity_points": 0,
        },
    }

    assert config["pipeline_input"] == {
        "existing": "value",
        "source": "unit-test",
        "metadata": {"topic": "ai"},
        "character_count": len("Important text"),
    }


def test_pipeline_context_skips_enrichment_for_non_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(council_orchestrator, "PHILOSOPHER_AGENT_CLASSES", [_CooperativeAgent])
    monkeypatch.setattr(council_orchestrator, "SCIENTIFIC_AGENT_CLASSES", [_CooperativeAgent])
    monkeypatch.setattr(council_orchestrator, "ContentAssessor", lambda: _CooperativeAgent())
    monkeypatch.setattr(council_orchestrator, "setup_agent_logger", lambda *_, **__: logging.getLogger("test"))
    monkeypatch.setattr(council_orchestrator, "apply_self_critique_feedback", lambda critiques, *_: critiques)
    monkeypatch.setattr(council_orchestrator, "apply_arbitration_adjustments", lambda critiques, *_: critiques)
    monkeypatch.setattr(council_orchestrator, "collect_significant_points", lambda *_: {
        "points": [],
        "score_metrics": {"high_severity_points": 0, "medium_severity_points": 0, "low_severity_points": 0},
        "no_findings": True,
        "final_assessment": "none",
        "final_assessment_summary": "none",
    })

    config = {"pipeline_input": "unexpected"}
    pipeline_input = PipelineInput(content="body", metadata={})

    result = council_orchestrator.run_critique_council(pipeline_input, config=config)
    assert "input_metadata" not in result
    assert config["pipeline_input"] == "unexpected"


def test_arbitration_skips_when_no_valid_critiques(monkeypatch: pytest.MonkeyPatch) -> None:
    class NullAssessor:
        style = "StubAssessor"

        def __init__(self) -> None:
            self.logger = None

        def set_logger(self, logger: logging.Logger) -> None:
            self.logger = logger

        def extract_points(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
            return [{"id": "p1", "point": "First"}]

    def _mark_all_critiques_as_errors(
        critiques: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]],
        logger: logging.Logger,
    ) -> List[Dict[str, Any]]:
        critiques[:] = [{"agent_style": "Test", "critique_tree": {}, "error": "invalid"}]
        return critiques

    monkeypatch.setattr(council_orchestrator, "PHILOSOPHER_AGENT_CLASSES", [_CooperativeAgent])
    monkeypatch.setattr(council_orchestrator, "ContentAssessor", lambda: NullAssessor())
    monkeypatch.setattr(council_orchestrator, "setup_agent_logger", lambda *_, **__: logging.getLogger("test"))

    monkeypatch.setattr(council_orchestrator, "apply_self_critique_feedback", _mark_all_critiques_as_errors)
    monkeypatch.setattr(council_orchestrator, "apply_arbitration_adjustments", lambda critiques, *_: critiques)
    monkeypatch.setattr(council_orchestrator, "collect_significant_points", lambda *_: {
        "points": [],
        "score_metrics": {"high_severity_points": 0, "medium_severity_points": 0, "low_severity_points": 0},
        "no_findings": True,
        "final_assessment": "none",
        "final_assessment_summary": "none",
    })

    class TrackingArbiter:
        style = "Tracker"

        def __init__(self) -> None:
            self.called = False

        def set_logger(self, logger: logging.Logger) -> None:
            pass

        def arbitrate(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            self.called = True
            return {}

    arbiter_instance = TrackingArbiter()
    monkeypatch.setattr(council_orchestrator, "ScientificExpertArbiterAgent", lambda: arbiter_instance)

    result = council_orchestrator.run_critique_council("content", peer_review=False, scientific_mode=True)
    assert arbiter_instance.called is False
    assert result["arbitration_adjustments"] == []


def test_arbitration_errors_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(council_orchestrator, "PHILOSOPHER_AGENT_CLASSES", [_CooperativeAgent])
    monkeypatch.setattr(council_orchestrator, "ContentAssessor", lambda: _CooperativeAgent())
    monkeypatch.setattr(council_orchestrator, "setup_agent_logger", lambda *_, **__: logging.getLogger("test"))
    monkeypatch.setattr(council_orchestrator, "apply_self_critique_feedback", lambda critiques, *_: [
        {"agent_style": "CooperativeAgent", "critique_tree": {}}
    ])
    monkeypatch.setattr(council_orchestrator, "apply_arbitration_adjustments", lambda critiques, *_: critiques)
    monkeypatch.setattr(council_orchestrator, "collect_significant_points", lambda *_: {
        "points": [],
        "score_metrics": {"high_severity_points": 0, "medium_severity_points": 0, "low_severity_points": 0},
        "no_findings": True,
        "final_assessment": "none",
        "final_assessment_summary": "none",
    })

    class ErroringArbiter:
        style = "Erroring"

        def __init__(self) -> None:
            pass

        def set_logger(self, logger: logging.Logger) -> None:
            pass

        def arbitrate(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            raise RuntimeError("arbitration failed")

    monkeypatch.setattr(council_orchestrator, "ScientificExpertArbiterAgent", ErroringArbiter)

    result = council_orchestrator.run_critique_council("content", peer_review=True, scientific_mode=True)
    assert result["arbitration_adjustments"] == []
    assert result["arbiter_overall_score"] is None
