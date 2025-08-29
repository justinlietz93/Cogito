# tests/test_reasoning_agent.py

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.reasoning_agent import (
    AristotleAgent, DescartesAgent, KantAgent, LeibnizAgent, PopperAgent, RussellAgent,
    PROMPT_DIR # Import base path for verification
)

# List of agent classes and their expected prompt filenames
AGENT_TEST_PARAMS = [
    (AristotleAgent, 'critique_aristotle.txt'),
    (DescartesAgent, 'critique_descartes.txt'),
    (KantAgent, 'critique_kant.txt'),
    (LeibnizAgent, 'critique_leibniz.txt'),
    (PopperAgent, 'critique_popper.txt'),
    (RussellAgent, 'critique_russell.txt'),
]

# --- Fixtures ---

@pytest.fixture(params=AGENT_TEST_PARAMS)
def agent_instance(request):
    """Fixture to create an instance of each philosopher agent."""
    agent_class, _ = request.param
    return agent_class()

@pytest.fixture
def mock_tree_execution():
    """Fixture to mock the execute_reasoning_tree function."""
    # Define a consistent mock return value for the tree
    mock_tree_result = {
        'id': 'mock-root-id',
        'claim': 'Mock critique claim',
        'evidence': 'Mock evidence',
        'confidence': 0.8,
        'severity': 'Medium',
        'sub_critiques': []
    }
    # Patch the function in the reasoning_agent module where it's imported
    with patch('src.reasoning_agent.execute_reasoning_tree', return_value=mock_tree_result) as mock_tree:
        yield mock_tree

# --- Test Cases ---

def test_agent_initialization(agent_instance):
    """Tests that agents are initialized with the correct style name."""
    agent_class, _ = next(p for p in AGENT_TEST_PARAMS if isinstance(agent_instance, p[0]))
    assert agent_instance.style == agent_class.__name__.replace("Agent", "")

def test_get_style_directives_loads_file(agent_instance):
    """Tests that get_style_directives attempts to load the correct file and caches it."""
    agent_class, filename = next(p for p in AGENT_TEST_PARAMS if isinstance(agent_instance, p[0]))
    # Adjust expected path based on new structure
    expected_prompt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'prompts'))
    expected_filepath = os.path.join(expected_prompt_dir, filename)

    # Check if prompt file actually exists before trying to read
    if not os.path.exists(expected_filepath):
        pytest.skip(f"Prompt file not found, skipping directive content check: {expected_filepath}")

    # First call - should load from file
    directives1 = agent_instance.get_style_directives()
    assert isinstance(directives1, str)
    assert len(directives1) > 0 # Basic check that content was loaded
    assert "ERROR:" not in directives1 # Ensure no load error occurred

    # Second call - should use cache (mock open to verify)
    with patch('builtins.open', MagicMock()) as mock_open:
        directives2 = agent_instance.get_style_directives()
        mock_open.assert_not_called() # Assert file wasn't opened again
        assert directives1 == directives2 # Ensure cached value is returned

def test_get_style_directives_file_not_found(agent_instance):
    """Tests error handling when prompt file is missing."""
    # Temporarily force a non-existent path relative to the new PROMPT_DIR
    original_path = agent_instance.prompt_filepath
    new_prompt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'prompts'))
    agent_instance.prompt_filepath = os.path.join(new_prompt_dir, "non_existent_prompt.txt")
    agent_instance._directives_cache = None # Clear cache

    directives = agent_instance.get_style_directives()
    assert "ERROR: Prompt file not found" in directives

    # Restore original path for other tests
    agent_instance.prompt_filepath = original_path
    agent_instance._directives_cache = None # Clear cache again

def test_critique_method_calls_tree(agent_instance, mock_tree_execution):
    """Tests that the critique method calls execute_reasoning_tree."""
    dummy_content = "Some text to critique."
    result = agent_instance.critique(dummy_content)

    # Check that the tree function was called
    mock_tree_execution.assert_called_once()
    call_args, call_kwargs = mock_tree_execution.call_args
    assert call_kwargs['initial_content'] == dummy_content
    assert call_kwargs['style_directives'] == agent_instance.get_style_directives()
    assert call_kwargs['agent_style'] == agent_instance.style

    # Check the structure of the returned dictionary
    assert result['agent_style'] == agent_instance.style
    assert 'critique_tree' in result
    assert result['critique_tree']['id'] == 'mock-root-id' # Check mock data is returned

def test_critique_method_handles_tree_termination(agent_instance):
    """Tests that critique handles None return from execute_reasoning_tree."""
    # Patch the function in the reasoning_agent module where it's imported
    with patch('src.reasoning_agent.execute_reasoning_tree', return_value=None) as mock_tree:
        result = agent_instance.critique("Some content")
        mock_tree.assert_called_once()
        assert result['agent_style'] == agent_instance.style
        assert result['critique_tree']['id'] == 'root-terminated'
        assert result['critique_tree']['confidence'] == 0.0

def test_self_critique_method_placeholder(agent_instance):
    """Tests the placeholder implementation of the self_critique method."""
    own_critique = {'agent_style': agent_instance.style, 'critique_tree': {'id': 'test-id'}}
    other_critiques = [{'agent_style': 'Other', 'critique_tree': {'id': 'other-id'}}]

    result = agent_instance.self_critique(own_critique, other_critiques)

    assert result['agent_style'] == agent_instance.style
    assert 'adjustments' in result
    assert isinstance(result['adjustments'], list)
    # Check placeholder adjustment details (may change if placeholder changes)
    if own_critique['critique_tree']['id'] != 'root-terminated':
        assert len(result['adjustments']) == 1
        assert result['adjustments'][0]['target_claim_id'] == 'test-id'
        assert result['adjustments'][0]['confidence_delta'] == -0.05
    else:
         assert len(result['adjustments']) == 0
