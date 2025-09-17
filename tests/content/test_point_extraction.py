"""Tests for the content assessor's point extraction helpers."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.content_assessor import ContentAssessor

SUCCESSFUL_RESPONSE = {
    "points": [
        {"id": "point-1", "point": "First test point"},
        {"id": "point-2", "point": "Second test point"},
    ]
}

INCOMPLETE_JSON_RESPONSE = """
{
  "points": [
    {
      "id": "point-1",
      "point": "First point"
    },
    {
      "id": "point-2",
      "point": "Second point"
    }
"""

TEXT_RESPONSE = """
Here are some points:
1. First point from text
2. Second point from text
3. Third point from text
"""


@pytest.fixture
def assessor() -> ContentAssessor:
    """Return a content assessor with a test logger attached."""

    instance = ContentAssessor()
    instance.logger = logging.getLogger("tests.content_assessor")
    return instance


def test_extract_points_returns_provider_payload_without_references(assessor: ContentAssessor, monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured provider responses should flow straight through to callers."""

    captured: Dict[str, Any] = {}

    def fake_call(prompt_template: str, context: Dict[str, Any], config: Dict[str, Any], is_structured: bool) -> tuple[Dict[str, Any], str]:
        captured["prompt"] = prompt_template
        captured["context"] = context
        captured["config"] = config
        captured["structured"] = is_structured
        return SUCCESSFUL_RESPONSE, "o3-mini"

    monkeypatch.setattr("src.content_assessor.call_with_retry", fake_call)

    config: Dict[str, Any] = {"arxiv": {"enabled": False}}
    points = assessor.extract_points("Some source content", config)

    assert points == SUCCESSFUL_RESPONSE["points"]
    assert captured["structured"] is True
    assert "Some source content" in captured["prompt"]
    assert captured["config"] is config


def test_validate_and_format_points_repairs_truncated_json(assessor: ContentAssessor) -> None:
    """Malformed JSON returned from providers should be repaired when possible."""

    repaired = assessor._validate_and_format_points(INCOMPLETE_JSON_RESPONSE)

    assert len(repaired) == 2
    assert repaired[0]["id"] == "point-1"
    assert repaired[1]["point"].startswith("Second point")


def test_validate_and_format_points_provides_fallback_when_empty(assessor: ContentAssessor) -> None:
    """The assessor must offer a graceful fallback when no points are returned."""

    fallback = assessor._validate_and_format_points(result={})

    assert len(fallback) == 1
    assert fallback[0]["id"] == "point-fallback"
    assert "point extraction failed" in fallback[0]["point"].lower()


def test_extract_points_from_text_handles_numbered_lists(assessor: ContentAssessor) -> None:
    """Raw text containing numbered points should still yield structured output."""

    extracted = assessor._extract_points_from_text(TEXT_RESPONSE)

    assert len(extracted) >= 1
    assert extracted[0]["id"].startswith("point-")
    assert "First point" in extracted[0]["point"]


def test_attach_arxiv_references_enriches_points(tmp_path: Path, assessor: ContentAssessor, monkeypatch: pytest.MonkeyPatch) -> None:
    """ArXiv lookups should attach references and update bibliographies when enabled."""

    calls: Dict[str, Any] = {}

    class DummyArxivService:
        def __init__(self, cache_dir: str) -> None:
            calls["cache_dir"] = cache_dir
            calls["service"] = self
            self.registered: List[tuple[str, str, float]] = []
            self.updated_paths: List[str] = []

        def get_references_for_content(self, text: str, max_results: int, domains: Any | None = None) -> List[Dict[str, Any]]:
            calls.setdefault("lookups", []).append((text, max_results))
            return [
                {
                    "id": "arxiv:1234",
                    "title": "Evidence-based testing",
                    "authors": ["Test", "Researcher"],
                    "summary": "Detailed summary of the referenced paper.",
                    "arxiv_url": "https://arxiv.org/abs/1234",
                    "published": "2024-01-01",
                }
            ]

        def register_reference_for_agent(self, agent_name: str, paper_id: str, relevance_score: float) -> None:
            self.registered.append((agent_name, paper_id, relevance_score))

        def update_latex_bibliography(self, path: str) -> bool:
            self.updated_paths.append(path)
            return True

    monkeypatch.setattr("src.content_assessor.ArxivReferenceService", DummyArxivService)

    points = [
        {
            "id": "point-1",
            "point": "This is a sufficiently descriptive point to trigger reference lookup.",
        }
    ]

    cache_dir = tmp_path / "arxiv_cache"
    cache_dir.mkdir()
    latex_dir = tmp_path / "latex"
    latex_dir.mkdir()

    config = {
        "arxiv": {
            "enabled": True,
            "cache_dir": str(cache_dir),
            "max_references_per_point": 1,
            "update_bibliography": True,
        },
        "latex": {
            "output_dir": str(latex_dir),
            "output_filename": "report",
        },
    }

    assessor._attach_arxiv_references(points, "source content", config)

    assert "references" in points[0]
    assert points[0]["references"][0]["id"] == "arxiv:1234"
    assert calls["lookups"][0][0].startswith("This is a sufficiently descriptive point")
    dummy_service: DummyArxivService = calls["service"]
    assert dummy_service.registered[0][0] == "ContentAssessor"
    assert dummy_service.updated_paths[0].endswith("report_bibliography.bib")
