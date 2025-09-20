import json
from pathlib import Path

from syncretic_catalyst.domain import AgentProfile, ResearchPaper
from syncretic_catalyst.infrastructure.thesis.output_repository import (
    FileSystemThesisOutputRepository,
)


def sample_paper(identifier: str, title: str, *, summary: str | None = None) -> ResearchPaper:
    return ResearchPaper(
        identifier=identifier,
        title=title,
        authors=("Ada", "Grace"),
        published="2023-12-01T00:00:00",
        summary=summary,
        raw_payload={"id": identifier},
    )


def test_persist_papers_creates_json_and_markdown(tmp_path: Path) -> None:
    repository = FileSystemThesisOutputRepository(tmp_path)
    papers = [
        sample_paper("1234.1", "Quantum Compiler", summary="Deep dive into quantum circuits"),
        sample_paper("5678.2", "Federated AI"),
    ]

    repository.persist_papers("abc123", papers)

    json_payload = json.loads((tmp_path / "papers_abc123.json").read_text(encoding="utf-8"))
    assert json_payload[0]["id"] == "1234.1"
    assert json_payload[0]["raw_payload"] == {"id": "1234.1"}

    markdown = (tmp_path / "papers_abc123.md").read_text(encoding="utf-8")
    assert "# Relevant Research Papers" in markdown
    assert "Quantum Compiler" in markdown
    assert "Federated AI" in markdown


def test_persist_agent_output_and_thesis(tmp_path: Path) -> None:
    repository = FileSystemThesisOutputRepository(tmp_path)
    profile = AgentProfile(
        name="SystemsArchitect",
        role="Designs cohesive systems",
        system_prompt="Prompt",
    )

    repository.persist_agent_output("abc123", profile, "Agent content")
    agent_path = tmp_path / "agent_SystemsArchitect_abc123.md"
    assert agent_path.read_text(encoding="utf-8").startswith("# SystemsArchitect: Designs cohesive systems")

    repository.persist_thesis("abc123", "Concept", "Thesis body")
    thesis_path = tmp_path / "thesis_abc123.md"
    assert thesis_path.read_text(encoding="utf-8").startswith("# Research Thesis: Concept")


def test_persist_report_writes_markdown(tmp_path: Path) -> None:
    repository = FileSystemThesisOutputRepository(tmp_path)

    repository.persist_report("abc123", "Summary report")

    assert (tmp_path / "research_report_abc123.md").read_text(encoding="utf-8") == "Summary report"


def test_persist_papers_truncates_long_summaries(tmp_path: Path) -> None:
    repository = FileSystemThesisOutputRepository(tmp_path)
    lengthy_summary = "Detailed analysis " + "of findings " * 30
    paper = sample_paper("9999.9", "Expansive Study", summary=lengthy_summary)

    repository.persist_papers("research42", [paper])

    markdown = (tmp_path / "papers_research42.md").read_text(encoding="utf-8")
    assert "Summary: Detailed analysis of findings of findings of findings" in markdown
    assert markdown.count("...") >= 1
