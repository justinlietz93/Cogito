"""Filesystem-backed repository for the research enhancement workflow."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from ...domain import (
    DEFAULT_DOCUMENT_ORDER,
    EnhancedProposal,
    KeyConcept,
    ProjectDocument,
    ResearchGapAnalysis,
    ResearchPaper,
)


class FileSystemResearchEnhancementRepository:
    """Persists research enhancement artefacts to disk."""

    def __init__(
        self,
        base_dir: Path,
        *,
        document_order: Sequence[str] | None = None,
        documents_subdir: str = "doc",
    ) -> None:
        self._base_dir = base_dir
        self._documents_dir = base_dir / documents_subdir
        self._document_order = tuple(document_order or DEFAULT_DOCUMENT_ORDER)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._documents_dir.mkdir(parents=True, exist_ok=True)

    def load_documents(self) -> Sequence[ProjectDocument]:
        documents: list[ProjectDocument] = []
        for name in self._document_order:
            path = self._documents_dir / name
            if not path.exists():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                content = f"[Error decoding {name}: {exc}]"
            except OSError as exc:
                content = f"[Error reading {name}: {exc}]"
            documents.append(ProjectDocument(name=name, content=content))
        return documents

    def persist_key_concepts(self, concepts: Sequence[KeyConcept]) -> None:
        payload = [concept.value for concept in concepts]
        path = self._base_dir / "key_concepts.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def persist_papers(self, papers: Sequence[ResearchPaper]) -> None:
        json_path = self._base_dir / "relevant_papers.json"
        json_payload = [self._serialise_paper(paper) for paper in papers]
        json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

        markdown_path = self._base_dir / "relevant_papers.md"
        markdown_path.write_text(self._format_papers_markdown(papers), encoding="utf-8")

    def persist_gap_analysis(self, analysis: ResearchGapAnalysis) -> None:
        path = self._base_dir / "research_gaps_analysis.md"
        path.write_text(analysis.content, encoding="utf-8")

    def persist_enhanced_proposal(self, proposal: EnhancedProposal) -> None:
        path = self._base_dir / "enhanced_research_proposal.md"
        path.write_text(proposal.content, encoding="utf-8")

    @staticmethod
    def _serialise_paper(paper: ResearchPaper) -> dict:
        return {
            "id": paper.identifier,
            "title": paper.title,
            "authors": list(paper.authors),
            "published": paper.published,
            "summary": paper.summary,
            "raw_payload": paper.raw_payload,
        }

    @staticmethod
    def _format_papers_markdown(papers: Sequence[ResearchPaper]) -> str:
        lines = ["# Relevant Research Papers", ""]
        for index, paper in enumerate(papers, start=1):
            authors = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
            published = paper.published.split("T")[0] if paper.published else "n.d."
            identifier = (paper.identifier or "unknown").split("v")[0]
            entry = [
                f"{index}. **{paper.title or 'Unknown Title'}**",
                f"   Authors: {authors}",
                f"   Published: {published}",
                f"   ArXiv ID: {identifier}",
            ]
            if paper.summary:
                entry.append(f"   Summary: {paper.summary[:300]}...")
            lines.extend(entry)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

