"""Thesis builder workflow coordination."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ...domain import (
    AgentOutput,
    AgentProfile,
    ResearchPaper,
    ThesisResearchResult,
    DEFAULT_AGENT_PROFILES,
)
from ...prompt_texts import (
    THESIS_AGENT_ADDITIONAL_CONTEXT_TEMPLATE,
    THESIS_AGENT_USER_PROMPT_TEMPLATE,
)
from .ports import Clock, ContentGenerator, ReferenceService, ThesisOutputRepository


@dataclass(frozen=True)
class _ResearchAgentRunner:
    """Coordinates prompt assembly for a single agent."""

    profile: AgentProfile
    generator: ContentGenerator
    max_tokens: int

    def run(
        self,
        *,
        concept: str,
        papers: Sequence[ResearchPaper],
        context: str | None,
    ) -> str:
        user_prompt = self._build_user_prompt(concept, papers, context)
        return self.generator.generate(
            system_prompt=self.profile.system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.max_tokens,
        )

    def _build_user_prompt(
        self, concept: str, papers: Sequence[ResearchPaper], context: str | None
    ) -> str:
        paper_information = self._format_papers(papers)
        context_section = (
            THESIS_AGENT_ADDITIONAL_CONTEXT_TEMPLATE.format(context=context)
            if context
            else ""
        )

        return THESIS_AGENT_USER_PROMPT_TEMPLATE.format(
            agent_name=self.profile.name,
            agent_role=self.profile.role,
            concept=concept,
            paper_information=paper_information,
            additional_context_section=context_section,
        )

    @staticmethod
    def _format_papers(papers: Sequence[ResearchPaper]) -> str:
        formatted: list[str] = []
        for index, paper in enumerate(papers, start=1):
            authors = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
            published = paper.published.split("T")[0] if paper.published else "n.d."
            identifier = (paper.identifier or "unknown").split("v")[0]
            summary = paper.summary or "No summary available"
            formatted.append(
                "\n".join(
                    [
                        f"Paper {index}:",
                        f"Title: {paper.title or 'Unknown Title'}",
                        f"Authors: {authors}",
                        f"Published: {published}",
                        f"ArXiv ID: {identifier}",
                        f"Summary: {summary}",
                    ]
                )
            )
        return "\n".join(formatted)


class ThesisBuilderService:
    """Coordinates the multi-agent thesis building experience."""

    def __init__(
        self,
        *,
        reference_service: ReferenceService,
        output_repository: ThesisOutputRepository,
        content_generator: ContentGenerator,
        clock: Clock,
        agent_profiles: Sequence[AgentProfile] | None = None,
        max_tokens: int = 4000,
    ) -> None:
        self._reference_service = reference_service
        self._output_repository = output_repository
        self._clock = clock
        profiles = list(agent_profiles or DEFAULT_AGENT_PROFILES)
        self._agents = {
            profile.name: _ResearchAgentRunner(profile, content_generator, max_tokens)
            for profile in profiles
        }
        self._synthesis_agent_name = "SynthesisArbitrator"

    def build_thesis(
        self, concept: str, *, max_papers: int = 50
    ) -> ThesisResearchResult:
        timestamp = self._clock.now()
        research_id = timestamp.strftime("%Y%m%d_%H%M%S")

        papers = self._collect_papers(concept, max_papers)
        self._output_repository.persist_papers(research_id, papers)

        agent_outputs: list[AgentOutput] = []
        context_fragments: list[str] = []

        for name, agent in self._agents.items():
            if name == self._synthesis_agent_name:
                continue
            content = agent.run(concept=concept, papers=papers, context=None)
            agent_outputs.append(AgentOutput(agent.profile, content))
            context_fragments.append(
                f"=== {agent.profile.name}: {agent.profile.role} ===\n\n{content}\n"
            )
            self._output_repository.persist_agent_output(
                research_id, agent.profile, content
            )

        synthesis_runner = self._agents.get(self._synthesis_agent_name)
        synthesis = None
        if synthesis_runner is not None:
            synthesis = synthesis_runner.run(
                concept=concept,
                papers=papers,
                context="\n".join(context_fragments) if context_fragments else None,
            )
            agent_outputs.append(AgentOutput(synthesis_runner.profile, synthesis))
            self._output_repository.persist_thesis(research_id, concept, synthesis)

        report = self._build_report(
            concept=concept,
            timestamp=timestamp,
            research_id=research_id,
            papers=papers,
            outputs=agent_outputs,
            thesis=synthesis,
        )
        self._output_repository.persist_report(research_id, report)

        return ThesisResearchResult(
            concept=concept,
            research_id=research_id,
            timestamp=timestamp,
            papers=papers,
            agent_outputs=agent_outputs,
            thesis=synthesis,
        )

    def _collect_papers(self, concept: str, max_papers: int) -> Sequence[ResearchPaper]:
        primary_quota = max(1, max_papers // 2)
        collected = list(self._reference_service.search(concept, max_results=primary_quota))
        remaining = max(0, max_papers - len(collected))
        key_terms = self._extract_key_terms(concept)

        if remaining and key_terms:
            per_term = max(1, remaining // len(key_terms))
            for term in key_terms:
                if len(collected) >= max_papers:
                    break
                results = self._reference_service.search(term, max_results=per_term)
                for paper in results:
                    if len(collected) >= max_papers:
                        break
                    if paper.identifier and any(
                        paper.identifier == existing.identifier for existing in collected
                    ):
                        continue
                    collected.append(paper)
        return collected[:max_papers]

    @staticmethod
    def _extract_key_terms(concept: str, *, max_terms: int = 5) -> Sequence[str]:
        words = re.findall(r"\b\w+\b", concept.lower())
        phrases = re.findall(r"\b\w+(?:\s+\w+){1,3}\b", concept)
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "about",
            "as",
        }
        filtered_words = [word for word in words if word not in stopwords and len(word) > 3]

        capitalized_phrases = [p for p in phrases if any(token[0].isupper() for token in p.split())]
        other_phrases = [p for p in phrases if p not in capitalized_phrases]

        candidates: list[str] = (
            sorted(capitalized_phrases, key=len, reverse=True)
            + sorted(other_phrases, key=len, reverse=True)
            + sorted(filtered_words, key=len, reverse=True)
        )

        seen: set[str] = set()
        unique_terms: list[str] = []
        for term in candidates:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_terms.append(term)
            if len(unique_terms) >= max_terms:
                break
        return unique_terms

    def _build_report(
        self,
        *,
        concept: str,
        timestamp: datetime,
        research_id: str,
        papers: Sequence[ResearchPaper],
        outputs: Sequence[AgentOutput],
        thesis: str | None,
    ) -> str:
        lines: list[str] = [
            "# Comprehensive Research Report",
            "",
            "## Concept",
            concept,
            "",
            "## Research Overview",
            "This report presents a comprehensive analysis of the concept using a multi-agent research approach.",
            f"The research was conducted on {timestamp.isoformat()} with ID: {research_id}.",
            "",
            "## Research Methodology",
            "The research employed a syncretic catalyst approach with specialized research agents:",
            "",
        ]

        for output in outputs:
            lines.append(f"- **{output.agent.name}**: {output.agent.role}")
        lines.extend(
            [
                "",
                "## Research Papers",
                f"This analysis drew from {len(papers)} relevant academic papers retrieved through semantic vector search.",
                f"The complete list of papers can be found in `papers_{research_id}.md`.",
                "",
                "## Research Findings",
            ]
        )

        for output in outputs:
            summary = self._summarise_output(output.content)
            lines.extend([f"### {output.agent.name}", summary, ""])

        lines.extend(
            [
                "## Thesis",
                f"The complete synthesized thesis can be found in `thesis_{research_id}.md`." if thesis else "No thesis was generated.",
                "",
                "### Thesis Summary",
            ]
        )
        if thesis:
            lines.append(self._summarise_output(thesis, limit=500))
        return "\n".join(lines)

    @staticmethod
    def _summarise_output(content: str, *, limit: int = 300) -> str:
        if "\n\n" in content:
            return content.split("\n\n", 1)[0]
        return content[:limit] + ("..." if len(content) > limit else "")
