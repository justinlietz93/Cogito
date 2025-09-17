"""Service that enhances research proposals using vector search and LLMs."""
from __future__ import annotations

import re
from typing import Iterable, Sequence

from ...domain import (
    DEFAULT_DOCUMENT_ORDER,
    EnhancedProposal,
    KeyConcept,
    ProjectDocument,
    ResearchEnhancementResult,
    ResearchGapAnalysis,
    ResearchPaper,
)
from .exceptions import ProjectDocumentsNotFound
from .ports import ContentGenerator, ProjectRepository, ReferenceService


class ResearchEnhancementService:
    """Coordinates the research enhancement workflow."""

    def __init__(
        self,
        *,
        reference_service: ReferenceService,
        project_repository: ProjectRepository,
        content_generator: ContentGenerator,
        document_order: Sequence[str] | None = None,
        max_concepts: int = 10,
        content_query_limit: int = 10_000,
        gap_analysis_tokens: int = 4_000,
        enhancement_tokens: int = 10_000,
    ) -> None:
        self._reference_service = reference_service
        self._repository = project_repository
        self._generator = content_generator
        self._document_order = tuple(document_order or DEFAULT_DOCUMENT_ORDER)
        self._max_concepts = max(1, max_concepts)
        self._content_query_limit = max(1, content_query_limit)
        self._gap_analysis_tokens = max(1, gap_analysis_tokens)
        self._enhancement_tokens = max(1, enhancement_tokens)

    def enhance(
        self,
        *,
        max_papers: int = 20,
        max_concepts: int | None = None,
    ) -> ResearchEnhancementResult:
        """Run the enhancement workflow and return the resulting artefacts."""

        documents = list(self._repository.load_documents())
        ordered_documents = self._order_documents(documents)
        if not ordered_documents:
            raise ProjectDocumentsNotFound("No project documents were found for enhancement.")

        project_title = self._extract_project_title(ordered_documents)
        combined_content = self._combine_documents(ordered_documents)

        concept_limit = max_concepts or self._max_concepts
        concept_values = self._extract_key_concepts(combined_content, max_concepts=concept_limit)
        concepts = [KeyConcept(value=value) for value in concept_values]
        self._repository.persist_key_concepts(concepts)

        papers = self._collect_papers(
            combined_content,
            [concept.value for concept in concepts],
            max_papers=max_papers,
        )
        self._repository.persist_papers(papers)

        gap_analysis_text = self._generate_gap_analysis(combined_content, papers)
        gap_analysis = ResearchGapAnalysis(gap_analysis_text)
        self._repository.persist_gap_analysis(gap_analysis)

        enhanced_proposal_text = self._generate_enhanced_proposal(
            combined_content, papers, gap_analysis
        )
        enhanced_proposal = EnhancedProposal(enhanced_proposal_text)
        self._repository.persist_enhanced_proposal(enhanced_proposal)

        return ResearchEnhancementResult(
            project_title=project_title,
            key_concepts=concepts,
            papers=papers,
            gap_analysis=gap_analysis,
            enhanced_proposal=enhanced_proposal,
        )

    def _order_documents(self, documents: Sequence[ProjectDocument]) -> list[ProjectDocument]:
        order_lookup = {name: index for index, name in enumerate(self._document_order)}
        ordered = sorted(
            documents,
            key=lambda doc: order_lookup.get(doc.name, len(self._document_order)),
        )
        return [doc for doc in ordered if doc.content.strip()]

    def _extract_project_title(self, documents: Sequence[ProjectDocument]) -> str:
        for document in documents:
            if document.name != "BREAKTHROUGH_BLUEPRINT.md":
                continue
            for line in document.content.splitlines():
                if line.startswith("# "):
                    return line[2:].strip() or "Unknown Project"
        return "Unknown Project"

    def _combine_documents(self, documents: Sequence[ProjectDocument]) -> str:
        sections: list[str] = []
        for document in documents:
            section_name = document.name.replace(".md", "").replace("_", " ").title()
            content = document.content.strip()
            if content:
                sections.append(f"## {section_name}\n\n{content}")
        return "\n\n".join(sections)

    def _collect_papers(
        self,
        project_content: str,
        key_concepts: Sequence[str],
        *,
        max_papers: int,
    ) -> list[ResearchPaper]:
        target_total = max(1, max_papers)
        primary_quota = max(1, target_total // 2)
        query = project_content[: self._content_query_limit]
        primary_results = list(
            self._reference_service.search(query, max_results=primary_quota)
        )

        collected: list[ResearchPaper] = []
        seen_identifiers: set[str] = set()
        for paper in primary_results:
            identifier = paper.identifier or ""
            if identifier:
                if identifier in seen_identifiers:
                    continue
                seen_identifiers.add(identifier)
            collected.append(paper)
            if len(collected) >= target_total:
                return collected

        remaining = target_total - len(collected)
        if remaining <= 0 or not key_concepts:
            return collected

        per_concept = max(1, remaining // len(key_concepts))
        for concept in key_concepts:
            if len(collected) >= target_total:
                break
            secondary_results = self._reference_service.search(
                concept, max_results=per_concept
            )
            for paper in secondary_results:
                if len(collected) >= target_total:
                    break
                identifier = paper.identifier or ""
                if identifier and identifier in seen_identifiers:
                    continue
                if identifier:
                    seen_identifiers.add(identifier)
                collected.append(paper)
        return collected

    def _generate_gap_analysis(
        self, project_content: str, papers: Sequence[ResearchPaper]
    ) -> str:
        prompt = self._build_gap_prompt(project_content, papers)
        return self._generator.generate(
            system_prompt=(
                "You are a research scientist with expertise in identifying research gaps and "
                "novel contributions in academic proposals."
            ),
            user_prompt=prompt,
            max_tokens=self._gap_analysis_tokens,
        )

    def _generate_enhanced_proposal(
        self,
        project_content: str,
        papers: Sequence[ResearchPaper],
        gap_analysis: ResearchGapAnalysis,
    ) -> str:
        prompt = self._build_enhancement_prompt(project_content, papers, gap_analysis)
        return self._generator.generate(
            system_prompt=(
                "You are an expert academic writer specializing in creating rigorous research "
                "proposals with proper citations and academic formatting."
            ),
            user_prompt=prompt,
            max_tokens=self._enhancement_tokens,
        )

    def _build_gap_prompt(
        self, project_content: str, papers: Sequence[ResearchPaper]
    ) -> str:
        paper_text = "\n\n".join(self._format_paper_summary(index, paper) for index, paper in enumerate(papers, 1))
        truncated_project = self._truncate(project_content, 5_000)
        return (
            "Research Gap Analysis\n\n"
            "Please analyze the following research project description and identify gaps or "
            "novel contributions when compared to the existing literature provided below.\n\n"
            "Focus on:\n"
            "1. Identifying unique aspects of the proposed research not covered in existing literature\n"
            "2. Potential novel connections between concepts in the project and existing research\n"
            "3. Areas where the project could make meaningful contributions to the field\n"
            "4. Suggestions for strengthening the project's novelty and impact\n\n"
            "=== PROJECT DESCRIPTION ===\n"
            f"{truncated_project}\n\n"
            "=== RELEVANT EXISTING LITERATURE ===\n"
            f"{paper_text or 'No papers were retrieved.'}\n\n"
            "=== ANALYSIS REQUESTED ===\n"
            "Provide a detailed analysis structured in the following sections:\n"
            "1. Uniqueness Analysis\n"
            "2. Novel Connections\n"
            "3. Contribution Opportunities\n"
            "4. Recommendations\n"
        )

    def _build_enhancement_prompt(
        self,
        project_content: str,
        papers: Sequence[ResearchPaper],
        gap_analysis: ResearchGapAnalysis,
    ) -> str:
        citations_text = "\n".join(
            self._format_citation(index, paper) for index, paper in enumerate(papers, 1)
        )
        truncated_content = self._truncate(project_content, 7_000)
        return (
            "Research Proposal Enhancement\n\n"
            "Please enhance the following research project with insights from the research gap analysis "
            "and integrate relevant citations from the provided literature.\n\n"
            "=== PROJECT CONTENT ===\n"
            f"{truncated_content}\n\n"
            "=== RESEARCH GAP ANALYSIS ===\n"
            f"{gap_analysis.content}\n\n"
            "=== RELEVANT LITERATURE (For Citations) ===\n"
            f"{citations_text or 'No literature was retrieved.'}\n\n"
            "=== ENHANCEMENT REQUESTED ===\n"
            "Create an enhanced academic research proposal that:\n"
            "1. Maintains the original project's core ideas and structure\n"
            "2. Incorporates insights from the research gap analysis\n"
            "3. Integrates relevant citations from the literature list\n"
            "4. Strengthens the proposal's academic rigor and novelty claims\n"
            "5. Includes a proper literature review section and bibliography\n\n"
            "Format the proposal as a formal academic document with all necessary sections."
        )

    def _format_paper_summary(self, index: int, paper: ResearchPaper) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
        summary = paper.summary or "No summary available"
        published = paper.published.split("T")[0] if paper.published else "n.d."
        identifier = (paper.identifier or "unknown").split("v")[0]
        summary_snippet = self._truncate(summary, 300)
        return (
            f"{index}. \"{paper.title or 'Unknown Title'}\" by {authors}\n"
            f"Published: {published}\n"
            f"ArXiv ID: {identifier}\n"
            f"Summary: {summary_snippet}"
        )

    def _format_citation(self, index: int, paper: ResearchPaper) -> str:
        authors = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
        published = paper.published.split("T")[0] if paper.published else "n.d."
        identifier = (paper.identifier or "unknown").split("v")[0]
        return (
            f"{index}. {authors}. ({published}). \"{paper.title or 'Unknown Title'}\". "
            f"arXiv:{identifier}."
        )

    def _extract_key_concepts(self, content: str, *, max_concepts: int) -> list[str]:
        paragraphs = re.split(r"\n\n+", content)
        concepts: list[str] = []
        concepts_set: set[str] = set()

        def _append_if_new(values: Iterable[str]) -> None:
            for value in values:
                candidate = value.strip()
                if 3 < len(candidate) < 80 and candidate not in concepts_set:
                    concepts.append(candidate)
                    concepts_set.add(candidate)
                    if len(concepts) >= max_concepts:
                        return

        heading_matches = re.findall(r"#+ ([^\n]+)", content)
        _append_if_new(heading_matches)

        bullet_matches = re.findall(r"[-*] ([^\n]+)", content)
        _append_if_new(bullet_matches)

        emphasis_matches = re.findall(r"\*\*([^*]+)\*\*|\*([^*]+)\*|__([^_]+)__|_([^_]+)_", content)
        for match_tuple in emphasis_matches:
            _append_if_new(value for value in match_tuple if value)
            if len(concepts) >= max_concepts:
                return concepts

        if len(concepts) < max_concepts:
            for paragraph in paragraphs:
                if len(concepts) >= max_concepts:
                    break
                capitalised_phrases = re.findall(
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", paragraph
                )
                _append_if_new(capitalised_phrases)
                if len(concepts) >= max_concepts:
                    break

        return concepts[:max_concepts]

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "..."

