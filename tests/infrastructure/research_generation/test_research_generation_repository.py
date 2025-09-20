from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(ROOT))

from src.syncretic_catalyst.domain import (
    GeneratedProposal,
    ProjectDocument,
    ProposalPrompt,
    ResearchProposalResult,
)
from src.syncretic_catalyst.infrastructure.research_generation import (
    FileSystemResearchGenerationRepository,
)


def test_load_documents_returns_known_order(tmp_path: Path):
    project_dir = tmp_path / "project"
    repository = FileSystemResearchGenerationRepository(project_dir)

    doc_dir = project_dir / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "CONTEXT_CONSTRAINTS.md").write_text("alpha", encoding="utf-8")
    (doc_dir / "BREAKTHROUGH_BLUEPRINT.md").write_text("# Title\nbody", encoding="utf-8")

    documents = repository.load_documents()

    assert [doc.name for doc in documents] == [
        "CONTEXT_CONSTRAINTS.md",
        "BREAKTHROUGH_BLUEPRINT.md",
    ]
    assert all(isinstance(doc, ProjectDocument) for doc in documents)


def test_persist_generation_writes_prompt_and_proposal(tmp_path: Path):
    repository = FileSystemResearchGenerationRepository(tmp_path)

    result = ResearchProposalResult(
        project_title="Example",
        prompt=ProposalPrompt("prompt text"),
        proposal=GeneratedProposal("proposal body"),
    )

    repository.persist_generation(result)

    assert repository.prompt_path.read_text(encoding="utf-8") == "prompt text"
    assert repository.proposal_path.read_text(encoding="utf-8") == "proposal body"
