# tests/test_reasoning_tree.py

"""Tests for the reasoning tree execution logic."""

import os
import sys
from typing import Dict
from unittest.mock import patch

import pytest

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.reasoning_tree import execute_reasoning_tree

STYLE_DIRECTIVES = "Unit test style directives"


@pytest.fixture(autouse=True)
def stub_call_with_retry(monkeypatch):
    """Provide deterministic responses for the provider interactions."""

    def _fake_call(prompt_template, context, config, is_structured=False):
        if "Based on the primary critique claim" in prompt_template:
            return (["Topic A", "Topic B"], "stub-model")
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
