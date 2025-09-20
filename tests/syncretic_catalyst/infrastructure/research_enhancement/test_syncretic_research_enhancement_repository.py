import json
from pathlib import Path
from typing import Iterable

import pytest

from syncretic_catalyst.domain import (
    EnhancedProposal,
    KeyConcept,
    ResearchGapAnalysis,
    ResearchPaper,
)
from syncretic_catalyst.infrastructure.research_enhancement.repository import (
    FileSystemResearchEnhancementRepository,
)


def build_paper(identifier: str, title: str, *, summary: str | None = None) -> ResearchPaper:
    return ResearchPaper(
        identifier=identifier,
        title=title,
        authors=("Alice", "Bob"),
        published="2024-01-01T00:00:00",
        summary=summary,
        raw_payload={"id": identifier},
    )


def test_load_documents_orders_files_and_handles_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FileSystemResearchEnhancementRepository(tmp_path)
    doc_dir = tmp_path / "doc"

    (doc_dir / "CONTEXT_CONSTRAINTS.md").write_text("Context", encoding="utf-8")
    (doc_dir / "DEEP_DIVE_MECHANISMS.md").write_bytes(b"\xff\xfebinary")
    (doc_dir / "BREAKTHROUGH_BLUEPRINT.md").write_text("# Title\nDetails", encoding="utf-8")
    error_path = doc_dir / "SELF_CRITIQUE_SYNERGY.md"
    error_path.write_text("content", encoding="utf-8")

    original_read_text = Path.read_text

    def failing_read_text(self: Path, *args: object, **kwargs: object) -> str:  # type: ignore[override]
        if self == error_path:
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read_text)

    documents = repository.load_documents()

    contents = {doc.name: doc.content for doc in documents}
    assert contents["CONTEXT_CONSTRAINTS.md"] == "Context"
    assert "Error decoding" in contents["DEEP_DIVE_MECHANISMS.md"]
    assert contents["BREAKTHROUGH_BLUEPRINT.md"] == "# Title\nDetails"
    assert "Error reading" in contents["SELF_CRITIQUE_SYNERGY.md"]


def test_persist_key_concepts_and_gap_analysis(tmp_path: Path) -> None:
    repository = FileSystemResearchEnhancementRepository(tmp_path)

    repository.persist_key_concepts([KeyConcept("LLM"), KeyConcept("Vector Search")])
    concepts_path = tmp_path / "key_concepts.json"
    assert json.loads(concepts_path.read_text(encoding="utf-8")) == ["LLM", "Vector Search"]

    gap = ResearchGapAnalysis("Gaps identified")
    repository.persist_gap_analysis(gap)
    assert (tmp_path / "research_gaps_analysis.md").read_text(encoding="utf-8") == "Gaps identified"


def test_persist_papers_creates_json_and_markdown(tmp_path: Path) -> None:
    repository = FileSystemResearchEnhancementRepository(tmp_path)
    papers = [
        build_paper("1234.5678v1", "Advances in Syncretic AI", summary="A" * 350),
        build_paper("9876.5432v2", "Composable Systems"),
    ]

    repository.persist_papers(papers)

    payload = json.loads((tmp_path / "relevant_papers.json").read_text(encoding="utf-8"))
    assert payload[0]["id"] == "1234.5678v1"
    assert payload[0]["raw_payload"] == {"id": "1234.5678v1"}

    markdown = (tmp_path / "relevant_papers.md").read_text(encoding="utf-8")
    assert "# Relevant Research Papers" in markdown
    assert "Advances in Syncretic AI" in markdown
    assert "Syncretic AI" in markdown
    assert "Composable Systems" in markdown


def test_persist_enhanced_proposal(tmp_path: Path) -> None:
    repository = FileSystemResearchEnhancementRepository(tmp_path)
    proposal = EnhancedProposal("Expanded proposal")

    repository.persist_enhanced_proposal(proposal)

    path = tmp_path / "enhanced_research_proposal.md"
    assert path.read_text(encoding="utf-8") == "Expanded proposal"
