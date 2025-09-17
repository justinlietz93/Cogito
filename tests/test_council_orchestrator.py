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
def test_orchestrator_full_cycle(mock_self_critique, mock_tree, capsys):
    """Tests the full critique -> self-critique -> synthesis cycle."""
    test_content = "Content for council integration test."
    result = run_critique_council(test_content)

    # 1. Check Agent Instantiation & Critique Calls
    agent_names = [cls.__name__.replace("Agent", "") for cls in [AristotleAgent, DescartesAgent, KantAgent, LeibnizAgent, PopperAgent, RussellAgent]]
    # Check that critique (which calls the mocked tree) was called for each agent
    assert mock_tree.call_count == len(agent_names)
    # Verify style directives were passed (indirectly checks agent init and get_style_directives)
    loaded_directives_count = 0
    for agent_name in agent_names:
         found_call = False
         for args_call in mock_tree.call_args_list:
              _, kwargs_call = args_call
              if kwargs_call.get('agent_style') == agent_name:
                   # Check if directives were loaded (not an error string)
                   directives = kwargs_call.get('style_directives', '')
                   assert "ERROR:" not in directives
                   if len(directives) > 0: # Count successful loads
                        loaded_directives_count +=1
                   found_call = True
                   break
         assert found_call, f"execute_reasoning_tree not called for agent {agent_name}"
    # Ensure directives were actually loaded (requires prompt files to exist)
    # This might fail if prompt files are missing, adjust assertion if needed
    assert loaded_directives_count == len(agent_names), "Not all agent directives were loaded successfully"


    # 2. Check Self-Critique Calls
    assert mock_self_critique.call_count == len(agent_names)
    # Check that each agent received its own critique and others' critiques
    for i, agent_name in enumerate(agent_names):
         call_args, _ = mock_self_critique.call_args_list[i]
         # call_args[0] is 'self' (the agent instance)
         assert call_args[1]['agent_style'] == agent_name # own_critique
         assert len(call_args[2]) == len(agent_names) - 1 # other_critiques

    # 3. Check Synthesis Logic (based on mock data and synthesis placeholder)
    assert not result['no_findings']
    assert f"Council identified {len(agent_names)} primary point(s)" in result['final_assessment']
    assert len(result['points']) == len(agent_names) # Placeholder adds one point per agent

    # Check details of synthesized points (using knowledge of mock data)
    for point in result['points']:
        assert 'Claim from' in point['critique']
        area = point['area']
        cohort_label, separator, remainder = area.partition(':')
        if separator:
            assert cohort_label.strip() == 'Philosopher'
            agent_style = remainder.strip()
        else:
            assert area == 'Philosopher'
            agent_style = 'Philosopher'
        expected_confidence = (0.8 if agent_style != 'Skeptic' else 0.6) + (-0.1 if agent_style == 'Skeptic' else -0.05)
        assert point['confidence'] == round(expected_confidence, 2)
        assert point['severity'] == 'Medium'

    # Check console output for flow (optional, depends if prints are kept)
    # captured = capsys.readouterr()
    # assert "Instantiating 6 agents" in captured.out
    # assert "Starting initial critique round" in captured.out
    # ... etc


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

    for point in result['points']:
        area = point['area']
        cohort_label, separator, _ = area.partition(':')
        if separator:
            assert cohort_label.strip() == 'Scientific Analyst'
        else:
            assert area == 'Scientific Analyst'


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
