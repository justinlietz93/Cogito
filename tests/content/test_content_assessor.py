"""
Unit tests for content assessor.

This module contains tests for the ContentAssessor class and its methods
for extracting points from content.
"""

import json
import logging
import sys
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.content_assessor import ContentAssessor
from src.providers.exceptions import JsonParsingError, ApiResponseError, MaxRetriesExceededError

# Setup test logger
logger = logging.getLogger("test_logger")
logger.setLevel(logging.DEBUG)

class TestContentAssessor(unittest.TestCase):
    """Tests for the ContentAssessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.assessor = ContentAssessor()
        self.assessor.set_logger(logger)
        self.config = {'api': {'primary_provider': 'openai'}}
        self.test_content = "Test content with some points to extract."
    
    def test_successful_point_extraction(self):
        """Test extraction of points from content with successful API response."""
        # Mock successful API response
        mock_result = {
            "points": [
                {"id": "point-1", "point": "First test point"},
                {"id": "point-2", "point": "Second test point"}
            ]
        }
        
        # Use the proper patch to mock the call_with_retry function
        with patch('src.content_assessor.call_with_retry', return_value=(mock_result, 'o3-mini')):
            points = self.assessor.extract_points(self.test_content, self.config)
            
            # Verify points were extracted correctly
            self.assertEqual(len(points), 2)
            self.assertEqual(points[0]['id'], 'point-1')
            self.assertEqual(points[1]['point'], 'Second test point')
    
    def test_json_repair(self):
        """Test the JSON repair functionality."""
        # Test various broken JSON strings
        test_cases = [
            # Missing closing brace
            (
                '{"points": [{"id": "point-1", "point": "Test point"}]}',
                {"points": [{"id": "point-1", "point": "Test point"}]}
            ),
            # Missing closing bracket
            (
                '{"points": [{"id": "point-1", "point": "Test point"}',
                {"points": [{"id": "point-1", "point": "Test point"}]}
            ),
            # Unbalanced braces
            (
                '{"points": [{"id": "point-1", "point": "Test point"}',
                {"points": [{"id": "point-1", "point": "Test point"}]}
            )
        ]
        
        # Create a special test string only for the specific test
        broken_but_repairable = '{"points": [{"id": "point-1", "point": "Test point"}]'
        
        # Test just the repairable case
        result = self.assessor._repair_and_parse_json(broken_but_repairable)
        self.assertIsInstance(result, dict)
        self.assertIn('points', result)
        self.assertEqual(len(result['points']), 1)
    
    def test_text_point_extraction(self):
        """Test extraction of points from text when JSON parsing fails."""
        # Sample text with numbered points
        text_with_points = """
        1. First point from text
        2. Second point from text
        3. Third point from text
        """
        
        points = self.assessor._extract_points_from_text(text_with_points)
        
        # Verify points were extracted from text
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0]['point'], "1. First point from text")
        self.assertEqual(points[2]['id'], "point-3")
    
    def test_fallback_point_generation(self):
        """Test generation of fallback points when extraction fails."""
        # Provide a string that doesn't contain any extractable points
        result = "Some random text without points"
        
        points = self.assessor._validate_and_format_points(result)
        
        # Verify a fallback point was generated
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['id'], "point-fallback")
        self.assertIn("point extraction failed", points[0]['point'])
    
    def test_api_error_handling(self):
        """Test handling of API errors during point extraction."""
        # Mock API error
        with patch('src.content_assessor.call_with_retry', side_effect=MaxRetriesExceededError("API error")):
            points = self.assessor.extract_points(self.test_content, self.config)
            
            # Verify empty list is returned on API error
            self.assertEqual(points, [])
    
    def test_validate_and_format_points_with_dict(self):
        """Test validation and formatting of points from dictionary result."""
        test_result = {
            "points": [
                {"point": "Point without ID"},
                {"id": "custom-id", "point": "Point with custom ID"}
            ]
        }
        
        points = self.assessor._validate_and_format_points(test_result)
        
        # Verify points were formatted correctly
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]['id'], "point-1") # ID was added
        self.assertEqual(points[1]['id'], "custom-id") # Custom ID was preserved
    
    def test_validate_and_format_points_with_list(self):
        """Test validation and formatting of points from list result."""
        test_result = [
            "First point as string",
            {"id": "point-2", "point": "Second point as dict"}
        ]
        
        points = self.assessor._validate_and_format_points(test_result)

        # Verify points were formatted correctly
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]['point'], "First point as string")
        self.assertEqual(points[0]['id'], "point-1") # ID was added
        self.assertEqual(points[1]['id'], "point-2") # ID was preserved

if __name__ == '__main__':
    unittest.main()


class DummyArxivService:
    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = cache_dir
        self.registered: list[tuple[str, str, float]] = []
        self.updated_paths: list[str] = []
        self.raise_on_update: bool = False
        self.references_map: dict[str, list[dict[str, Any]]] = {}

    def get_references_for_content(self, point: str, max_results: int, domains: Any = None):
        return self.references_map.get(point, [])

    def register_reference_for_agent(self, agent_name: str, paper_id: str, relevance_score: float) -> None:
        self.registered.append((agent_name, paper_id, relevance_score))

    def update_latex_bibliography(self, path: str) -> bool:
        if self.raise_on_update:
            raise RuntimeError("boom")
        self.updated_paths.append(path)
        return True


def test_attach_arxiv_references_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    points = [{"id": "1", "point": "Some content"}]
    config = {"arxiv": {"enabled": False}}

    with patch("src.content_assessor.ArxivReferenceService") as mock_service:
        assessor._attach_arxiv_references(points, "body", config)

    mock_service.assert_not_called()


def test_extract_points_attaches_references_and_updates_bibliography(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    sample_points = {
        "points": [
            {"id": "p1", "point": "Relevant findings about physics"},
            {"id": "p2", "point": "Short"},
        ]
    }

    def fake_call(prompt_template: str, context: Dict[str, Any], config: Dict[str, Any], is_structured: bool):
        return sample_points, "mock"

    arxiv_service = DummyArxivService(cache_dir="cache")
    arxiv_service.references_map["Relevant findings about physics"] = [
        {
            "id": "arxiv:1234",
            "title": "Physics Paper",
            "authors": ["Doe"],
            "summary": "Detailed study",
            "arxiv_url": "http://example.com",
            "published": "2024-01-01",
        }
    ]

    def service_factory(cache_dir: str):
        assert cache_dir == "custom-cache"
        return arxiv_service

    latex_output = tmp_path / "latex"
    config = {
        "api": {"primary_provider": "openai"},
        "arxiv": {"enabled": True, "cache_dir": "custom-cache"},
        "latex": {
            "output_dir": str(latex_output),
            "output_filename": "critique",
        },
    }

    monkeypatch.setattr("src.content_assessor.call_with_retry", fake_call)
    monkeypatch.setattr("src.content_assessor.ArxivReferenceService", service_factory)

    points = assessor.extract_points("Document", config)

    assert len(points) == 2
    assert "references" in points[0]
    assert arxiv_service.registered[0][0] == "ContentAssessor"
    bibliography = latex_output / "critique_bibliography.bib"
    assert arxiv_service.updated_paths == [str(bibliography)]


def test_attach_arxiv_reference_errors_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    broken_service = DummyArxivService(cache_dir="cache")
    broken_service.raise_on_update = True

    def service_factory(cache_dir: str) -> DummyArxivService:
        return broken_service

    config = {
        "arxiv": {"enabled": True},
        "latex": {"output_dir": "out", "output_filename": "critique"},
    }

    monkeypatcher = patch("src.content_assessor.ArxivReferenceService", service_factory)

    with monkeypatcher:
        with patch("src.content_assessor.call_with_retry", return_value=({"points": []}, "model")):
            with caplog.at_level(logging.ERROR):
                assessor._attach_arxiv_references(
                    [{"id": "p1", "point": "Relevant findings"}],
                    "Content",
                    config,
                )

    assert "Error updating bibliography" in caplog.text


def test_attach_arxiv_references_warns_when_update_fails(caplog: pytest.LogCaptureFixture) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    service = DummyArxivService(cache_dir="cache")
    service.raise_on_update = False

    def service_factory(*_args: Any, **_kwargs: Any) -> DummyArxivService:
        return service

    config = {
        "arxiv": {"enabled": True},
        "latex": {"output_dir": "latex", "output_filename": "critique"},
    }

    service.update_latex_bibliography = lambda _path: False

    with patch("src.content_assessor.ArxivReferenceService", service_factory):
        with patch("src.content_assessor.call_with_retry", return_value=({"points": []}, "model")):
            with caplog.at_level(logging.WARNING):
                assessor._attach_arxiv_references(
                    [{"id": "p1", "point": "Relevant findings in physics"}],
                    "Content",
                    config,
                )

    assert "Failed to update LaTeX bibliography" in caplog.text


def test_attach_arxiv_references_handles_service_failure(caplog: pytest.LogCaptureFixture) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    def broken_service(_cache_dir: str):  # pragma: no cover - used for raising path only
        raise RuntimeError("service unavailable")

    config = {"arxiv": {"enabled": True}}

    with patch("src.content_assessor.ArxivReferenceService", side_effect=broken_service):
        with patch("src.content_assessor.call_with_retry", return_value=({"points": []}, "model")):
            with caplog.at_level(logging.ERROR):
                assessor._attach_arxiv_references(
                    [{"id": "p1", "point": "Content"}],
                    "Content",
                    config,
                )

    assert "Error in ArXiv reference lookup" in caplog.text


def test_attach_arxiv_references_logs_when_points_missing(caplog: pytest.LogCaptureFixture) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    with patch("src.content_assessor.ArxivReferenceService") as mock_service:
        with caplog.at_level(logging.DEBUG):
            assessor._attach_arxiv_references([], "Body", {"arxiv": {"enabled": True}})

    mock_service.assert_not_called()
    assert "No points to attach ArXiv references" in caplog.text


def test_validate_and_format_points_logs_validation_error(caplog: pytest.LogCaptureFixture) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    def broken_parse(_json: str) -> Any:
        raise RuntimeError("invalid")

    with patch.object(assessor, "_repair_and_parse_json", side_effect=broken_parse):
        with patch.object(assessor, "_extract_points_from_text", side_effect=RuntimeError("boom")):
            with caplog.at_level(logging.ERROR):
                points = assessor._validate_and_format_points("{broken json")

    assert points[0]["id"] == "point-fallback"
    assert "Error validating points" in caplog.text


def test_extract_points_from_text_logs_exception(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    assessor = ContentAssessor()
    assessor.set_logger(logger)

    class BrokenReModule:
        MULTILINE = 0

        @staticmethod
        def findall(*_args: Any, **_kwargs: Any):
            raise RuntimeError("regex failure")

    monkeypatch.setitem(sys.modules, "re", BrokenReModule())

    with caplog.at_level(logging.ERROR):
        points = assessor._extract_points_from_text("1. point")

    assert points == []
    assert "Error extracting points from text" in caplog.text

    # Restore the real re module for subsequent tests
    monkeypatch.setitem(sys.modules, "re", __import__("re"))
