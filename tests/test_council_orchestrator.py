# tests/test_council_orchestrator.py

import pytest
import os
import sys
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.council_orchestrator import run_critique_council
# Import agent classes to allow mocking their methods if needed
from src.reasoning_agent import AristotleAgent, DescartesAgent, KantAgent, LeibnizAgent, PopperAgent, RussellAgent

# --- Mock Data ---

# Mock return value for execute_reasoning_tree
# Make it slightly different per agent style for testing synthesis
def mock_tree_side_effect(*args, **kwargs):
    agent_style = kwargs.get('agent_style', 'Unknown')
    depth = kwargs.get('depth', 0)
    if depth >= 1: # Terminate sub-critiques quickly for integration test
        return None
    return {
        'id': f'mock-root-{agent_style}',
        'claim': f'Claim from {agent_style}',
        'evidence': 'Mock evidence',
        'confidence': 0.8 if agent_style != 'Skeptic' else 0.6, # Skeptic is less confident
        'severity': 'Medium',
        'sub_critiques': []
    }

# Mock return value for agent's self_critique (placeholder adjustments)
def mock_self_critique_side_effect(self, own_critique: Dict[str, Any], other_critiques: list[Dict[str, Any]]):
     # Simulate adjustment based on own critique ID
     own_tree_id = own_critique.get('critique_tree', {}).get('id', 'N/A')
     adj_reason = f'Self-critique adjustment by {self.style}'
     delta = -0.1 if self.style == 'Skeptic' else -0.05 # Skeptic adjusts more
     adjustments = []
     if own_tree_id != 'root-terminated':
         adjustments.append({'target_claim_id': own_tree_id, 'confidence_delta': delta, 'reasoning': adj_reason})
     return {'agent_style': self.style, 'adjustments': adjustments}


# --- Tests ---

# Patch the tree execution within the reasoning_agent module where it's called
@patch('src.reasoning_agent.execute_reasoning_tree', side_effect=mock_tree_side_effect)
# Patch the self_critique method directly on the base class (or specific classes if needed)
@patch('src.reasoning_agent.ReasoningAgent.self_critique', side_effect=mock_self_critique_side_effect, autospec=True)
def test_orchestrator_full_cycle(mock_self_critique, mock_tree):
    """Tests the full critique -> self-critique -> synthesis cycle."""
    result = run_critique_council("Content for council integration test.")

    agent_names = [
        cls.__name__.replace("Agent", "")
        for cls in [AristotleAgent, DescartesAgent, KantAgent, LeibnizAgent, PopperAgent, RussellAgent]
    ]

    assert mock_tree.call_count == len(agent_names)
    agent_styles = {kwargs.get('agent_style') for _, kwargs in mock_tree.call_args_list}
    assert agent_styles == set(agent_names)
    assert all(
        kwargs.get('style_directives') and "ERROR:" not in kwargs.get('style_directives', '')
        for _, kwargs in mock_tree.call_args_list
        if kwargs.get('agent_style') in agent_names
    )

    assert mock_self_critique.call_count == len(agent_names)
    own_styles = {call_args[1]['agent_style'] for call_args, _ in mock_self_critique.call_args_list}
    assert own_styles == set(agent_names)
    other_counts = {len(call_args[2]) for call_args, _ in mock_self_critique.call_args_list}
    assert other_counts == {len(agent_names) - 1}

    assert not result['no_findings']
    assert f"Council identified {len(agent_names)} primary point(s)" in result['final_assessment']
    assert len(result['points']) == len(agent_names)

    critiques = [point['critique'] for point in result['points']]
    assert all('Claim from' in critique for critique in critiques)
    areas = [point['area'] for point in result['points']]
    assert all(area.partition(':')[0].strip() == 'Philosopher' for area in areas)
    confidences = {point['confidence'] for point in result['points']}
    assert confidences == {0.75}
    severities = {point['severity'] for point in result['points']}
    assert severities == {'Medium'}


# Patch the tree execution within the reasoning_agent module where it's called
@patch('src.reasoning_agent.execute_reasoning_tree', return_value=None) # Simulate all critiques failing/terminating
@patch('src.reasoning_agent.ReasoningAgent.self_critique', side_effect=mock_self_critique_side_effect, autospec=True)
def test_orchestrator_no_significant_findings(mock_self_critique, mock_tree, capsys):
    """Tests the case where no critiques meet the synthesis threshold."""
    test_content = "Content resulting in no findings."
    result = run_critique_council(test_content)

    assert mock_tree.call_count == 6 # Critique called for all agents
    # Self-critique might not be called if initial critique returns terminated tree
    assert mock_self_critique.call_count == 6 # Should still be called even if tree terminated

    # Check the output based on synthesis logic
    assert result['no_findings'] is True
    assert "No points met the significance threshold" in result['final_assessment']
    assert len(result['points']) == 0

    # captured = capsys.readouterr()
    # Ensure synthesis logic correctly identifies no points to include
    # assert "Included point:" not in captured.out
    assert "No points met the significance threshold" in result['final_assessment']


# Patch the tree execution within the reasoning_agent module where it's called
@patch('src.reasoning_agent.execute_reasoning_tree', side_effect=mock_tree_side_effect)
@patch('src.reasoning_agent.ReasoningAgent.self_critique', side_effect=mock_self_critique_side_effect, autospec=True)
def test_orchestrator_scientific_mode_uses_scientific_label(mock_self_critique, mock_tree):
    """Ensure scientific mode reports scientific analyst areas instead of philosophers."""
    result = run_critique_council("Scientific content", scientific_mode=True)

    assert mock_tree.call_count == 6
    assert not result['no_findings']
    assert result['points'], "Scientific runs should surface significant points in this scenario"

    areas = [point['area'] for point in result['points']]

    def _is_scientific(area: str) -> bool:
        cohort_label, separator, _ = area.partition(':')
        return (
            (separator and cohort_label.strip() == 'Scientific Analyst')
            or (not separator and area == 'Scientific Analyst')
        )

    assert all(_is_scientific(area) for area in areas)


# Patch the tree execution within the reasoning_agent module where it's called
@patch('src.reasoning_agent.execute_reasoning_tree', side_effect=mock_tree_side_effect)
@patch('src.reasoning_agent.ReasoningAgent.self_critique', side_effect=mock_self_critique_side_effect, autospec=True)
def test_orchestrator_respects_agent_area_overrides(mock_self_critique, mock_tree):
    """Agent-specific area overrides should replace the cohort label when configured."""
    config = {
        'council_orchestrator': {
            'cohort_labels': {'scientific': 'Scientific Analyst'},
            'agent_area_labels': {
                'SystemsAnalyst': 'Systems Specialist',
                'default': 'Council Member {style}',
            },
        }
    }

    result = run_critique_council("Scientific content", config=config, scientific_mode=True)

    areas = {point['area'] for point in result['points']}
    assert any(area.startswith('Systems Specialist') for area in areas)
    assert any(area.startswith('Council Member') for area in areas)
    # Ensure the default cohort label is no longer present in the synthesized areas
    assert not any(area.startswith('Scientific Analyst:') for area in areas)
