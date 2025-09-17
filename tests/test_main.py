# tests/test_main.py

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.main import critique_goal_document
from src.pipeline_input import PipelineInput

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
    assert mock_council.call_count == 1
    council_args, council_kwargs = mock_council.call_args
    assert isinstance(council_args[0], PipelineInput)
    assert council_args[0].content == "Sample file content."
    assert council_args[0].source == test_path
    assert council_kwargs["config"] == {}
    assert council_kwargs["peer_review"] is False
    assert council_kwargs["scientific_mode"] is False

    assert mock_format.call_count == 1
    format_args, format_kwargs = mock_format.call_args
    assert format_args[0] == {'final_assessment': 'Good', 'points': [], 'no_findings': True}
    assert format_args[1] == "Sample file content."
    assert format_args[2] == {}
    assert format_kwargs["peer_review"] is False
    assert result == "Formatted: Good"

@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_missing_file_falls_back_to_text(mock_read, mock_council, mock_format):
    """Tests that missing files are treated as literal text content."""
    mock_read.side_effect = FileNotFoundError("File not found error")
    mock_council.return_value = {'final_assessment': 'Okay', 'points': [], 'no_findings': True}
    mock_format.return_value = "Formatted: fallback"

    test_path = "dummy/path/nonexistent.txt"
    result = critique_goal_document(test_path)

    mock_read.assert_called_once_with(test_path)
    pipeline_input = mock_council.call_args[0][0]
    assert isinstance(pipeline_input, PipelineInput)
    assert pipeline_input.content == test_path
    assert pipeline_input.source is None
    assert pipeline_input.metadata.get("fallback_reason") == "file_not_found"

    mock_format.assert_called_once()
    assert result == "Formatted: fallback"

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


@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_accepts_direct_text(mock_read, mock_council, mock_format):
    """Tests that direct text inputs bypass file loading."""
    mock_read.side_effect = FileNotFoundError("No file")
    mock_council.return_value = {'final_assessment': 'Great', 'points': [], 'no_findings': True}
    mock_format.return_value = "Formatted: direct"

    text_input = "Direct critique content"
    result = critique_goal_document(text_input)

    mock_read.assert_called_once_with(text_input)
    pipeline_input = mock_council.call_args[0][0]
    assert isinstance(pipeline_input, PipelineInput)
    assert pipeline_input.content == text_input
    assert pipeline_input.source is None
    assert pipeline_input.metadata.get("input_type") == "text"
    assert pipeline_input.metadata.get("fallback_reason") == "file_not_found"

    mock_format.assert_called_once()
    assert result == "Formatted: direct"


@patch(PATCH_FORMAT)
@patch(PATCH_COUNCIL)
@patch(PATCH_INPUT)
def test_main_empty_direct_text_raises(mock_read, mock_council, mock_format):
    """Empty direct text inputs should raise a validation error."""

    mock_read.side_effect = FileNotFoundError("No file")
    mock_council.return_value = {'final_assessment': 'Great', 'points': [], 'no_findings': True}
    mock_format.return_value = "Formatted: direct"

    with pytest.raises(ValueError, match="Critique input contains no content."):
        critique_goal_document("")
