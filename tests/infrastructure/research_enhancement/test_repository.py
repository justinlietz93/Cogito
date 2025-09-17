"""Tests for the filesystem research enhancement repository."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.syncretic_catalyst.domain import (
    EnhancedProposal,
    KeyConcept,
    ResearchGapAnalysis,
    ResearchPaper,
)
from src.syncretic_catalyst.infrastructure.research_enhancement import (
    FileSystemResearchEnhancementRepository,
)


def test_repository_round_trips_documents_and_outputs(tmp_path) -> None:
    doc_dir = tmp_path / "doc"
    doc_dir.mkdir(parents=True)
    (doc_dir / "CONTEXT_CONSTRAINTS.md").write_text("Context body", encoding="utf-8")
    (doc_dir / "BREAKTHROUGH_BLUEPRINT.md").write_text(
        "# Title\nDetails", encoding="utf-8"
    )

    repository = FileSystemResearchEnhancementRepository(tmp_path)
    documents = repository.load_documents()

    assert [doc.name for doc in documents] == [
        "CONTEXT_CONSTRAINTS.md",
        "BREAKTHROUGH_BLUEPRINT.md",
    ]
    assert documents[0].content == "Context body"

    repository.persist_key_concepts([KeyConcept("Concept A"), KeyConcept("Concept B")])
    concepts_path = tmp_path / "key_concepts.json"
    assert json.loads(concepts_path.read_text(encoding="utf-8")) == [
        "Concept A",
        "Concept B",
    ]

    papers = [
        ResearchPaper(
            identifier="id1",
            title="Paper One",
            authors=("Alice", "Bob"),
            published="2024-01-01T00:00:00",
            summary="Summary text",
            raw_payload={"id": "id1"},
        ),
        ResearchPaper(
            identifier="id2",
            title="Paper Two",
            authors=(),
            published=None,
            summary=None,
            raw_payload={"id": "id2"},
        ),
    ]
    repository.persist_papers(papers)
    papers_json = json.loads((tmp_path / "relevant_papers.json").read_text(encoding="utf-8"))
    assert papers_json[0]["id"] == "id1"
    papers_md = (tmp_path / "relevant_papers.md").read_text(encoding="utf-8")
    assert "# Relevant Research Papers" in papers_md
    assert "Paper One" in papers_md

    repository.persist_gap_analysis(ResearchGapAnalysis("Gap content"))
    assert (tmp_path / "research_gaps_analysis.md").read_text(encoding="utf-8") == "Gap content"

    repository.persist_enhanced_proposal(EnhancedProposal("Proposal body"))
    assert (tmp_path / "enhanced_research_proposal.md").read_text(encoding="utf-8") == "Proposal body"

