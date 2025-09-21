# tests/test_reasoning_tree.py

"""Tests for the reasoning tree execution logic."""

import os
import sys
from typing import Dict
from unittest.mock import patch

import pytest

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.providers.exceptions import JsonParsingError, JsonProcessingError
from src.reasoning_tree import execute_reasoning_tree, run_example

STYLE_DIRECTIVES = "Unit test style directives"


@pytest.fixture(autouse=True)
def stub_call_with_retry(monkeypatch):
    """Provide deterministic responses for the provider interactions."""

    def _fake_call(prompt_template, context, config, is_structured=False):
        if "Based on the primary critique claim" in prompt_template:
            return ({"topics": ["Topic A", "Topic B"]}, "stub-model")
        return (
            {
                "claim": "Stub claim",
                "evidence": "Stub evidence",
                "confidence": 0.8,
                "severity": "medium",
                "recommendation": "Stub recommendation",
                "concession": "None",
            },
            "stub-model",
        )

    monkeypatch.setattr("src.reasoning_tree.call_with_retry", _fake_call)


@pytest.fixture
def base_config() -> Dict[str, Dict[str, float]]:
    """Return a minimal configuration for the reasoning tree."""

    return {
        "goal": "Unit test goal",
        "reasoning_tree": {"max_depth": 2, "confidence_threshold": 0.1},
    }


def test_tree_returns_node_structure(base_config):
    """The reasoning tree should return a structured node with sub-critiques."""

    result = execute_reasoning_tree("Sufficient content for testing." * 5, STYLE_DIRECTIVES, "TestAgent", base_config)

    assert isinstance(result, dict)
    assert result["sub_critiques"], "Expected recursive sub-critiques to be generated"


def test_tree_respects_max_depth(base_config):
    """Recursion should terminate once the configured max depth is reached."""

    config = {**base_config, "reasoning_tree": {**base_config["reasoning_tree"], "max_depth": 1}}

    result = execute_reasoning_tree("Layered content." * 5, STYLE_DIRECTIVES, "TestAgent", config, depth=1)

    assert result is None


def test_tree_terminates_with_short_content(base_config):
    """Short content should stop the recursion immediately."""

    result = execute_reasoning_tree("Too short.", STYLE_DIRECTIVES, "TestAgent", base_config)

    assert result is None


def test_tree_respects_confidence_threshold(base_config):
    """Low confidence results should prune the branch."""

    config = {
        **base_config,
        "reasoning_tree": {**base_config["reasoning_tree"], "confidence_threshold": 0.9},
    }

    result = execute_reasoning_tree("Adequate content." * 5, STYLE_DIRECTIVES, "TestAgent", config)

    assert result is None


def test_node_contains_expected_fields(base_config):
    """Returned nodes should expose the primary critique fields."""

    result = execute_reasoning_tree("Rich content for testing." * 5, STYLE_DIRECTIVES, "TestAgent", base_config)

    assert result is not None
    expected_fields = {
        "id",
        "claim",
        "evidence",
        "confidence",
        "severity",
        "recommendation",
        "concession",
        "sub_critiques",
    }
    assert expected_fields <= result.keys()


def test_node_missing_expected_fields_logs_warning(base_config, caplog):
    """Gracefully handle provider responses that omit expected fields."""

    def _partial_response(prompt_template, context, config, is_structured=False):
        return ({"claim": "Incomplete"}, "stub-model")

    with caplog.at_level("WARNING", logger="src.reasoning_tree"):
        with patch("src.reasoning_tree.call_with_retry", _partial_response):
            result = execute_reasoning_tree(
                "Insufficient structured response." * 5,
                STYLE_DIRECTIVES,
                "TestAgent",
                base_config,
            )

    assert result is None
    assert any("Unexpected assessment structure" in message for message in caplog.messages)


def test_tree_distributes_assigned_points(base_config, monkeypatch):
    """Assigned points should guide the root and propagate to delegated subtopics."""

    import importlib

    reasoning_tree_module = importlib.import_module('src.reasoning_tree')
    original_execute = reasoning_tree_module.execute_reasoning_tree

    recursive_assigned_points = []

    def _tracking_execute(*args, **kwargs):
        recursive_assigned_points.append(kwargs.get('assigned_points'))
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(reasoning_tree_module, 'execute_reasoning_tree', _tracking_execute)

    assessment_contexts = []

    def _call_with_retry(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            _call_with_retry.decomposition_calls += 1
            if _call_with_retry.decomposition_calls == 1:
                return (['Topic 1', 'Topic 2'], 'stub-decomposition-model')
            return ([], 'stub-decomposition-model')

        assessment_contexts.append(context)
        return (
            {
                'claim': f"Claim {len(assessment_contexts)}",
                'evidence': 'Robust supporting evidence underpins the critique.' * 2,
                'confidence': 0.95,
                'severity': 'high',
                'recommendation': 'Follow-up action recommended.',
                'concession': 'None',
            },
            'stub-assessment-model',
        )

    _call_with_retry.decomposition_calls = 0
    monkeypatch.setattr(reasoning_tree_module, 'call_with_retry', _call_with_retry)

    assigned_points = [
        {'id': 'point-0', 'point': 'Root focus'},
        {'id': 'point-1', 'point': 'Delegate first child'},
        {'id': 'point-2', 'point': 'Delegate second child'},
    ]

    long_content = 'Comprehensive discussion segment. ' * 60

    result = reasoning_tree_module.execute_reasoning_tree(
        initial_content=long_content,
        style_directives=STYLE_DIRECTIVES,
        agent_style='TestAgent',
        config=base_config,
        assigned_points=assigned_points,
    )

    assert recursive_assigned_points[0] == assigned_points
    assert recursive_assigned_points[1] == [assigned_points[1]]
    assert recursive_assigned_points[2] == [assigned_points[2]]
    assert len(recursive_assigned_points) == 3

    assert assessment_contexts[0]['assigned_point_id'] == 'point-0'
    assert result['assigned_point_id'] == 'point-0'
    assert len(result['sub_critiques']) == 2


def test_tree_handles_assessment_provider_error(base_config, monkeypatch):
    """Provider-layer failures should yield a pruned branch."""

    def _failing_call(prompt_template, context, config, is_structured=False):
        raise JsonParsingError('bad json payload')

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _failing_call)

    result = execute_reasoning_tree('Sufficient content for analysis.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is None


def test_tree_handles_unexpected_assessment_error(base_config, monkeypatch):
    """Unexpected provider errors should also prune the branch."""

    def _unexpected_call(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            return [], 'stub-model'
        raise RuntimeError('unexpected failure')

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _unexpected_call)

    result = execute_reasoning_tree('Sufficient content for analysis.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is None


def test_tree_handles_decomposition_provider_error(base_config, monkeypatch):
    """Failures during decomposition should be logged and still return a node."""

    def _call_with_retry(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            raise JsonProcessingError('bad decomposition payload')
        return (
            {
                'claim': 'Primary finding',
                'evidence': 'Detailed evidence',
                'confidence': 0.9,
                'severity': 'high',
                'recommendation': 'Action',
                'concession': 'None',
            },
            'assessment-model',
        )

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _call_with_retry)

    result = execute_reasoning_tree('Substantial content for review.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is not None
    assert result['sub_critiques'] == []


def test_tree_handles_unexpected_decomposition_error(base_config, monkeypatch, caplog):
    """Unexpected decomposition exceptions should be logged and allow execution to continue."""

    def _call_with_retry(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            raise RuntimeError('decomposition failed')
        return (
            {
                'claim': 'Primary finding',
                'evidence': 'Detailed evidence',
                'confidence': 0.9,
                'severity': 'high',
                'recommendation': 'Action',
                'concession': 'None',
            },
            'assessment-model',
        )

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _call_with_retry)

    with caplog.at_level('ERROR', logger='src.reasoning_tree'):
        result = execute_reasoning_tree('Extensive content segment.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is not None
    assert result['sub_critiques'] == []
    assert any('Unexpected error during decomposition' in message for message in caplog.messages)


def test_tree_accepts_list_based_decomposition(base_config, monkeypatch, caplog):
    """Lists of strings from the decomposition provider should remain supported."""

    def _call_with_retry(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            return (["Topic 1", "Topic 2"], 'stub-model')
        return (
            {
                'claim': 'Primary finding',
                'evidence': 'Detailed evidence',
                'confidence': 0.9,
                'severity': 'high',
                'recommendation': 'Action',
                'concession': 'None',
            },
            'assessment-model',
        )

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _call_with_retry)

    with caplog.at_level('INFO', logger='src.reasoning_tree'):
        result = execute_reasoning_tree('Extensive content segment.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is not None
    assert any('Identified 2 sub-topics for recursion.' in message for message in caplog.messages)


def test_tree_accepts_alternative_topic_keys(base_config, monkeypatch, caplog):
    """Mappings with "items" or "subtopics" keys should normalise correctly."""

    def _call_with_retry(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            return ({'items': ['Topic 1']}, 'stub-model')
        return (
            {
                'claim': 'Primary finding',
                'evidence': 'Detailed evidence',
                'confidence': 0.9,
                'severity': 'high',
                'recommendation': 'Action',
                'concession': 'None',
            },
            'assessment-model',
        )

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _call_with_retry)

    with caplog.at_level('INFO', logger='src.reasoning_tree'):
        result = execute_reasoning_tree('Extensive content segment.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is not None
    assert any('Identified 1 sub-topics for recursion.' in message for message in caplog.messages)


def test_tree_warns_on_invalid_decomposition_structure(base_config, caplog, monkeypatch):
    """Unexpected decomposition results should trigger a warning."""

    def _call_with_retry(prompt_template, context, config, is_structured=False):
        if 'Based on the primary critique claim' in prompt_template:
            return {'invalid': 'structure'}, 'stub-model'
        return (
            {
                'claim': 'Primary finding',
                'evidence': 'Detailed evidence',
                'confidence': 0.9,
                'severity': 'high',
                'recommendation': 'Action',
                'concession': 'None',
            },
            'assessment-model',
        )

    monkeypatch.setattr('src.reasoning_tree.call_with_retry', _call_with_retry)

    with caplog.at_level('WARNING', logger='src.reasoning_tree'):
        result = execute_reasoning_tree('Extensive content segment.' * 5, STYLE_DIRECTIVES, 'TestAgent', base_config)

    assert result is not None
    warnings = [message for message in caplog.messages if 'Unexpected decomposition structure' in message]
    assert len(warnings) == 1
    assert 'provider=' in warnings[0]
    assert 'keys=invalid' in warnings[0]


def test_run_example_executes_without_error(caplog):
    """The module example should be a harmless no-op."""

    with caplog.at_level('INFO'):
        run_example()

