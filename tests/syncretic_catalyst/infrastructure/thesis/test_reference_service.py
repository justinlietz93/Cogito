from pathlib import Path

import pytest

from syncretic_catalyst.domain import ResearchPaper
from syncretic_catalyst.infrastructure.thesis.reference_service import ArxivReferenceService


class StubVectorService:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads
        self.calls: list[tuple[str, int]] = []

    def get_references_for_content(self, query: str, *, max_results: int) -> list[dict]:
        self.calls.append((query, max_results))
        return self._payloads


def test_search_returns_domain_objects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [
        {
            "id": "1234.1",
            "title": "Quantum Networks",
            "authors": [{"name": "Ada"}, {"name": "Grace"}],
            "published": "2024-01-01",
            "summary": "Summary",
        }
    ]
    stub_service = StubVectorService(payloads)
    monkeypatch.setattr(
        "syncretic_catalyst.infrastructure.thesis.reference_service.ArxivVectorReferenceService",
        lambda config: stub_service,
    )

    service = ArxivReferenceService(cache_root=tmp_path)
    results = service.search("query", max_results=3)

    assert isinstance(results[0], ResearchPaper)
    assert results[0].identifier == "1234.1"
    assert results[0].authors == ["Ada", "Grace"]
    assert stub_service.calls == [("query", 3)]


def test_to_paper_handles_various_author_formats() -> None:
    payload_variants = [
        {"title": "Solo", "authors": "Single Author"},
        {"title": "Multiple", "authors": ["Alice", "Bob"]},
        {"title": "Dict", "authors": [{"name": "Carol"}, {"name": None}]},
    ]

    for payload in payload_variants:
        paper = ArxivReferenceService._to_paper(payload)
        assert isinstance(paper, ResearchPaper)
        assert paper.title
        assert paper.authors
