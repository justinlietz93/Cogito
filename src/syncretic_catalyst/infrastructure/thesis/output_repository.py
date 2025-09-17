"""Filesystem repository for thesis builder artefacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from ...domain import AgentProfile, ResearchPaper


class FileSystemThesisOutputRepository:
    """Persists thesis builder outputs under a target directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def persist_papers(self, research_id: str, papers: Sequence[ResearchPaper]) -> None:
        json_path = self._base_dir / f"papers_{research_id}.json"
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump([self._serialise_paper(paper) for paper in papers], handle, indent=2)

        markdown_path = self._base_dir / f"papers_{research_id}.md"
        markdown_content = self._format_papers_markdown(papers)
        markdown_path.write_text(markdown_content, encoding="utf-8")

    def persist_agent_output(self, research_id: str, agent: AgentProfile, content: str) -> None:
        agent_path = self._base_dir / f"agent_{agent.name}_{research_id}.md"
        agent_path.write_text(
            f"# {agent.name}: {agent.role}\n\n{content}", encoding="utf-8"
        )

    def persist_thesis(self, research_id: str, concept: str, thesis: str) -> None:
        thesis_path = self._base_dir / f"thesis_{research_id}.md"
        thesis_path.write_text(
            f"# Research Thesis: {concept}\n\n{thesis}", encoding="utf-8"
        )

    def persist_report(self, research_id: str, report: str) -> None:
        report_path = self._base_dir / f"research_report_{research_id}.md"
        report_path.write_text(report, encoding="utf-8")

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
                summary_text = paper.summary[:300]
                if len(paper.summary) > 300:
                    summary_text += "..."
                entry.append(f"   Summary: {summary_text}")
            lines.extend(entry)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
