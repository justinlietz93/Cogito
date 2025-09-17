# tests/test_end_to_end.py

import pytest
import os
import sys

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.main import critique_goal_document

# Define path relative to the 'critique_council' directory (where pytest should be run)
# This assumes pytest is run from the 'critique_council' directory.
GOAL_FILE_PATH = 'goal.txt'

@pytest.mark.skipif(not os.path.exists(GOAL_FILE_PATH), reason=f"{GOAL_FILE_PATH} not found in critique_council/ for E2E test")
def test_e2e_critique_execution():
    """
    Performs an end-to-end test by running the main critique function
    on the goal.txt file within the critique_council directory.
    Focuses on successful execution and basic output format validation,
    as the critique content itself depends on placeholder logic.
    """
    print(f"\nRunning E2E test with input file: {GOAL_FILE_PATH}")
    try:
        # Ensure the path passed to the function is correct relative to execution context
        # If running pytest from critique_council/, GOAL_FILE_PATH should work directly.
        result = critique_goal_document(GOAL_FILE_PATH)

        # Basic Assertions for format and execution
        assert isinstance(result, str)
        assert len(result) > 0
        assert "# Critique Assessment Report" in result
        assert "## Overall Judge Summary" in result
        assert "## Detailed Agent Critiques" in result or "No critique data available." in result
        # Cannot reliably assert specific critique content due to placeholder logic

        print("E2E test completed successfully (basic format check).")

    except Exception as e:
        pytest.fail(f"End-to-end test failed with exception: {e}")
