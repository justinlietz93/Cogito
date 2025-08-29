# tests/test_main.py

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.main import critique_goal_document

# Use absolute paths for patching relative to the new src directory
PATCH_INPUT = 'src.main.read_file_content'
PATCH_COUNCIL = 'src.main.run_critique_council'
PATCH_FORMAT = 'src.main.format_critique_output'

@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_success_flow(mock_read, mock_council, mock_format):
    """Tests the successful execution flow of the main function."""
    # Configure mocks
    mock_read.return_value = "Sample file content."
    mock_council.return_value = {'final_assessment': 'Good', 'points': [], 'no_findings': True}
    mock_format.return_value = "Formatted: Good"

    test_path = "dummy/path/goal.txt"
    result = critique_goal_document(test_path)

    # Assertions
    mock_read.assert_called_once_with(test_path)
    mock_council.assert_called_once_with("Sample file content.")
    mock_format.assert_called_once_with({'final_assessment': 'Good', 'points': [], 'no_findings': True})
    assert result == "Formatted: Good"

@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_file_not_found(mock_read, mock_council, mock_format):
    """Tests that FileNotFoundError from input_reader is propagated."""
    # Configure mocks
    mock_read.side_effect = FileNotFoundError("File not found error")

    test_path = "dummy/path/nonexistent.txt"
    with pytest.raises(FileNotFoundError, match="File not found error"):
        critique_goal_document(test_path)

    # Ensure council and formatter were not called
    mock_council.assert_not_called()
    mock_format.assert_not_called()

@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_council_error(mock_read, mock_council, mock_format):
    """Tests that an exception from the council is propagated."""
    # Configure mocks
    mock_read.return_value = "Some content."
    mock_council.side_effect = Exception("Council processing failed")

    test_path = "dummy/path/goal.txt"
    with pytest.raises(Exception, match="Critique module failed unexpectedly: Council processing failed"):
        critique_goal_document(test_path)

    # Ensure formatter was not called
    mock_format.assert_not_called()

@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_formatter_error(mock_read, mock_council, mock_format):
    """Tests that an exception from the formatter is propagated."""
    # Configure mocks
    mock_read.return_value = "Some content."
    mock_council.return_value = {'final_assessment': 'Okay', 'points': [], 'no_findings': True}
    mock_format.side_effect = Exception("Formatting failed")

    test_path = "dummy/path/goal.txt"
    with pytest.raises(Exception, match="Critique module failed unexpectedly: Formatting failed"):
        critique_goal_document(test_path)
