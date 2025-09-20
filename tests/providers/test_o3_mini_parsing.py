"""
Unit tests for o3-mini JSON response parsing.

This module contains specific tests for parsing and repairing o3-mini model JSON responses.
"""

import os
import sys
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))

from src.providers import openai_client
from src.providers.exceptions import JsonParsingError, ApiResponseError
from tests.providers.fixtures.o3_mini_responses import *


def _wrap_response(payload):
    """Recursively convert payload dictionaries into SimpleNamespace objects."""

    if isinstance(payload, list):
        return [_wrap_response(item) for item in payload]
    if isinstance(payload, dict):
        return SimpleNamespace(**{key: _wrap_response(value) for key, value in payload.items()})
    return payload

class TestO3MiniJsonParsing(unittest.TestCase):
    """Tests for parsing JSON responses from o3-mini model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = MagicMock()
        self.config = {
            'api': {
                'openai': {
                    'model': 'o3-mini',
                    'retries': 1,
                    'resolved_key': 'test-key'
                }
            }
        }
    
    def test_successful_json_parsing(self):
        """Test parsing a successful JSON response from o3-mini."""
        # Mock the response
        mock_response = _wrap_response(O3_MINI_SUCCESS)
        
        # Setup the mock client
        with patch('src.providers.openai_client.OpenAI', return_value=self.client):
            self.client.responses.create.return_value = mock_response
            
            # Call the function with structured flag
            result, model = openai_client.call_openai_with_retry(
                prompt_template="Test prompt",
                context={},
                config=self.config,
                is_structured=True
            )
            
            # Assert we got a properly parsed JSON object
            self.assertIsInstance(result, dict)
            self.assertIn('points', result)
            self.assertEqual(len(result['points']), 2)
            self.assertEqual(result['points'][0]['id'], 'point-1')
    
    def test_truncated_json_repair(self):
        """Test repairing a truncated JSON response from o3-mini."""
        # Mock the response with truncated JSON
        mock_response = _wrap_response(O3_MINI_TRUNCATED)
        
        # Setup the mock client
        with patch('src.providers.openai_client.OpenAI', return_value=self.client):
            self.client.responses.create.return_value = mock_response
            
            # Call the function with structured flag
            result, model = openai_client.call_openai_with_retry(
                prompt_template="Test prompt",
                context={},
                config=self.config,
                is_structured=True
            )
            
            # When repair fails we should still return the truncated text
            self.assertIsInstance(result, str)
            self.assertIn('point-1', result)
    
    def test_non_json_response_handling(self):
        """Test handling a non-JSON response from o3-mini."""
        # Mock the response with non-JSON text
        mock_response = _wrap_response(O3_MINI_NON_JSON)
        
        # Setup the mock client
        with patch('src.providers.openai_client.OpenAI', return_value=self.client):
            self.client.responses.create.return_value = mock_response
            
            # Call the function - should return text as is
            result, model = openai_client.call_openai_with_retry(
                prompt_template="Test prompt",
                context={},
                config=self.config,
                is_structured=True
            )
            
            # For structured requests that return plain text, 
            # we should get the original text
            self.assertIsInstance(result, str)
            self.assertIn("I've analyzed the content", result)
    
    def test_unexpected_empty_response(self):
        """Test handling an unexpected empty response."""
        # Mock an empty response structure
        mock_response = SimpleNamespace(output=[])
        
        # Setup the mock client
        with patch('src.providers.openai_client.OpenAI', return_value=self.client):
            self.client.responses.create.return_value = mock_response
            
            # Call should gracefully handle the unexpected structure
            result, model = openai_client.call_openai_with_retry(
                prompt_template="Test prompt",
                context={},
                config=self.config,
                is_structured=True
            )

        self.assertIsInstance(result, str)
        self.assertEqual(model, 'o3-mini')

if __name__ == '__main__':
    unittest.main()
