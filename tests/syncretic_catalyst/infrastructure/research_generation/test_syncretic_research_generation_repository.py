from pathlib import Path

import pytest

from syncretic_catalyst.domain import (
    GeneratedProposal,
    ProjectDocument,
    ProposalPrompt,
    ResearchProposalResult,
)
from syncretic_catalyst.infrastructure.research_generation.repository import (
    FileSystemResearchGenerationRepository,
)


def make_document(name: str, content: str) -> ProjectDocument:
    return ProjectDocument(name=name, content=content)


def test_load_documents_orders_results_and_skips_invalid(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    repository = FileSystemResearchGenerationRepository(tmp_path)
    doc_dir = tmp_path / "doc"

    (doc_dir / "CONTEXT_CONSTRAINTS.md").write_text("alpha", encoding="utf-8")
    bad_file = doc_dir / "DEEP_DIVE_MECHANISMS.md"
    bad_file.write_bytes(b"\xff\x00\xfe")
    (doc_dir / "BREAKTHROUGH_BLUEPRINT.md").write_text("# Blueprint\nBody", encoding="utf-8")

    caplog.set_level("WARNING")
    documents = repository.load_documents()

    assert [doc.name for doc in documents] == [
        "CONTEXT_CONSTRAINTS.md",
        "BREAKTHROUGH_BLUEPRINT.md",
    ]
    assert all(isinstance(doc, ProjectDocument) for doc in documents)

    assert "decode error" in caplog.text


def test_load_documents_skips_files_on_os_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FileSystemResearchGenerationRepository(tmp_path)
    doc_dir = tmp_path / "doc"
    target = doc_dir / "DEEP_DIVE_MECHANISMS.md"
    target.write_text("content", encoding="utf-8")

    original_read_text = Path.read_text

    def failing_read_text(self: Path, *args, **kwargs):  # type: ignore[override]
        if self == target:
            raise OSError("boom")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read_text)

    documents = repository.load_documents()

    assert documents == []


def test_persist_generation_writes_prompt_and_proposal(tmp_path: Path) -> None:
    repository = FileSystemResearchGenerationRepository(tmp_path)
    result = ResearchProposalResult(
        project_title="Project",
        prompt=ProposalPrompt("prompt text"),
        proposal=GeneratedProposal("proposal body"),
    )

    repository.persist_generation(result)

    assert repository.prompt_path.read_text(encoding="utf-8") == "prompt text"
    assert repository.proposal_path.read_text(encoding="utf-8") == "proposal body"


def test_prompt_and_proposal_paths_expose_locations(tmp_path: Path) -> None:
    repository = FileSystemResearchGenerationRepository(
        tmp_path,
        prompt_filename="custom_prompt.txt",
        proposal_filename="custom_proposal.md",
    )

    assert repository.prompt_path == tmp_path / "custom_prompt.txt"
    assert repository.proposal_path == tmp_path / "custom_proposal.md"
