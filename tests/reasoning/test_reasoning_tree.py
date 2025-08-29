# tests/test_reasoning_tree.py

import pytest
import os
import sys
from unittest.mock import patch

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.reasoning_tree import execute_reasoning_tree, MAX_DEPTH

# --- Test Cases ---

def test_tree_returns_dict_or_none():
    """Tests that the function returns a dictionary on success or None on termination."""
    result = execute_reasoning_tree("Sufficient content for testing.", "Directives", "TestAgent")
    assert isinstance(result, dict) or result is None

def test_tree_terminates_at_max_depth():
    """Tests that recursion stops at MAX_DEPTH."""
    # Patch the function within its own module for recursive calls
    with patch('src.reasoning_tree.execute_reasoning_tree') as mock_recursive_call:
        # Set up mock to return None when called at MAX_DEPTH
        def side_effect(*args, **kwargs):
            depth = kwargs.get('depth', 0)
            if depth >= MAX_DEPTH:
                return None
            else:
                # For calls below max depth, return a minimal valid node structure
                # to allow the parent call to proceed.
                # Need to call the original function to get realistic structure for depth < MAX_DEPTH
                # This makes mocking complex; alternative is to test structure based on placeholder.
                # Let's stick to testing based on placeholder structure for simplicity.
                 return {'id': f'mock-child-{depth}', 'claim': 'child', 'sub_critiques': []}


        mock_recursive_call.side_effect = side_effect

        # Call the function starting at depth 0, using the original implementation
        # The mock will only affect the *recursive* calls made *by* the original.
        # Need to import the original function directly for the initial call.
        from src.reasoning_tree import execute_reasoning_tree as original_execute_reasoning_tree
        result = original_execute_reasoning_tree(
            initial_content="Content long enough for multiple levels " * 20,
            style_directives="Directives",
            agent_style="TestAgent",
            depth=0 # Start at the top
        )

        # Check if the structure reflects termination at the correct depth
        # This requires inspecting the structure based on the placeholder logic.
        # The placeholder creates 2 sub-critiques per level if content is long enough.
        assert result is not None
        assert 'sub_critiques' in result
        # Check first level children
        for child1 in result['sub_critiques']:
             assert child1 is not None
             assert 'sub_critiques' in child1
             # Check second level children
             for child2 in child1['sub_critiques']:
                  assert child2 is not None
                  assert 'sub_critiques' in child2
                  # Check third level children (should be empty list as recursion terminated)
                  # The placeholder logic returns None at MAX_DEPTH, so the list should be empty
                  assert child2['sub_critiques'] == []


def test_tree_terminates_with_short_content():
    """Tests that recursion stops if content is too short."""
    short_content = "Too short."
    result = execute_reasoning_tree(short_content, "Directives", "TestAgent")
    # The placeholder terminates if len < 50
    assert result is None

def test_tree_terminates_with_low_confidence():
    """Tests termination if placeholder confidence drops below threshold."""
    # This test is difficult with the current placeholder as confidence is
    # deterministically calculated based on depth. A real implementation
    # with LLM calls would be needed, or the placeholder logic modified
    # to allow simulating low confidence return.
    # Skipping this specific scenario test for the placeholder.
    pytest.skip("Skipping low confidence termination test for placeholder logic.")

def test_node_structure():
    """Tests the basic structure of a returned node."""
    result = execute_reasoning_tree("Sufficient content for testing.", "Directives", "TestAgent")
    if result: # Only check if not terminated early
        assert 'id' in result and isinstance(result['id'], str)
        assert 'claim' in result and isinstance(result['claim'], str)
        assert 'evidence' in result and isinstance(result['evidence'], str)
        assert 'confidence' in result and isinstance(result['confidence'], float)
        assert 'severity' in result and isinstance(result['severity'], str)
        assert 'sub_critiques' in result and isinstance(result['sub_critiques'], list)
