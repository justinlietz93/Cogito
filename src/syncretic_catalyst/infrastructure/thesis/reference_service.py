"""Reference service implementations for thesis building."""
from __future__ import annotations

from typing import Sequence

from pathlib import Path

from ...domain import ResearchPaper
from src.arxiv.arxiv_vector_reference_service import ArxivVectorReferenceService


class ArxivReferenceService:
    """Wraps :class:`ArxivVectorReferenceService` to return domain objects."""

    def __init__(self, *, cache_root: Path, force_fallback: bool = False) -> None:
        config = {
            "arxiv": {
                "cache_dir": str(cache_root / "arxiv_cache"),
                "vector_cache_dir": str(cache_root / "arxiv_vector_cache"),
                "cache_ttl_days": 30,
                "force_vector_fallback": force_fallback,
            }
        }
        self._service = ArxivVectorReferenceService(config=config)

    def search(self, query: str, *, max_results: int) -> Sequence[ResearchPaper]:
        raw_results = self._service.get_references_for_content(
            query, max_results=max_results
        )
        return [self._to_paper(payload) for payload in raw_results]

    @staticmethod
    def _to_paper(payload: dict) -> ResearchPaper:
        identifier = payload.get("id") or payload.get("identifier")
        title = payload.get("title") or "Unknown Title"
        authors_field = payload.get("authors")
        authors: list[str] = []
        if isinstance(authors_field, list):
            if authors_field and isinstance(authors_field[0], dict):
                authors = [
                    str(author.get("name"))
                    for author in authors_field
                    if isinstance(author, dict) and author.get("name")
                ]
            else:
                authors = [str(author) for author in authors_field if author]
        elif isinstance(authors_field, str) and authors_field.strip():
            authors = [authors_field.strip()]
        published = payload.get("published")
        summary = payload.get("summary")
        return ResearchPaper(
            identifier=identifier,
            title=title,
            authors=authors,
            published=published,
            summary=summary,
            raw_payload=payload,
        )
