"""Domain-aware source selection for research queries.

Purpose:
    Provide a lightweight, deterministic, and testable mechanism to select the
    most appropriate research sources (PubMed, Semantic Scholar, CrossRef, Web)
    based on the semantic context of the query text (and, by proxy, the INPUT/
    corpus from which the query was derived).

External Dependencies:
    - Python standard library only: re, typing.
    - No HTTP/CLI calls are made here to preserve clean layering.

Fallback Semantics:
    - If domain inference is inconclusive or results in an empty set after
      filtering by enabled providers, fall back to a general-safe preference
      order: ["crossref", "web_search", "semantic_scholar", "pubmed"]
      filtered by the enabled providers.

Timeout Strategy:
    - Not applicable; this module performs synchronous, in-memory text analysis.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


class DomainRouter:
    """Heuristic router that selects research sources from enabled providers.

    Summary:
        Given a query text and the set of enabled provider names (as exposed by
        the ResearchAPIOrchestrator), return an ordered list of providers to be
        queried for that specific query. The decision is driven by simple,
        explainable keyword heuristics that bias toward domain-appropriate
        sources. This is intentionally conservative and deterministic.

    Notes:
        - Inputs for queries are typically derived from the INPUT/ corpus through
          extraction and query building; therefore, routing on query text is a
          proxy for routing on INPUT context without re-reading the corpus.
        - If desired, future extensions can accept an optional aggregated corpus
          to refine routing; left out for now to avoid re-ingestion and to keep
          the application-layer concerns clean.

    Public API:
        - select_sources(query_text, enabled_sources) -> List[str]
    """

    # Provider constants to avoid typos
    PUBMED = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    WEB = "web_search"

    # Default preference if domain is unclear (filtered by enabled providers)
    _GENERAL_PREF: Tuple[str, ...] = (CROSSREF, WEB, SEMANTIC_SCHOLAR, PUBMED)

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the router.

        Args:
            config: Optional configuration dict. Reserved for future tuning
                (thresholds/weights). Currently unused.

        Returns:
            None

        Raises:
            None

        Side Effects:
            None

        Timeout:
            Not applicable.
        """
        self.config = config or {}

        # Compile keyword patterns once
        self._bio_kw = self._compile(
            [
                r"\b(bioinformatics|biomedical|genomics?|proteomics?|transcriptomics?)\b",
                r"\b(clinical|medicine|medical|oncology|cardiology|neurology|immunology)\b",
                r"\b(drug|therapy|therapeutic|diagnostic|pathogen|epidemiology|public health)\b",
                r"\b(gene|protein|cell(?:ular)?|rna|dna|mrna|crisper|crispr)\b",
            ]
        )
        self._cs_kw = self._compile(
            [
                r"\b(computer science|software|programming|algorithms?|data structures?)\b",
                r"\b(machine learning|deep learning|neural networks?|llm|transformers?)\b",
                r"\b(nlp|vision|reinforcement learning|retrieval|embeddings?)\b",
                r"\b(distributed systems?|databases?|compiler|operating systems?)\b",
            ]
        )
        self._math_phys_kw = self._compile(
            [
                r"\b(mathematics?|theorem|proof|algebra|topology|geometry|analysis)\b",
                r"\b(physics?|quantum|relativity|thermodynamics|electromagnetism)\b",
                r"\b(statistics?|probability|stochastic|inference)\b",
            ]
        )
        self._finance_econ_kw = self._compile(
            [
                r"\b(finance|financial|market|trading|portfolio|derivatives?)\b",
                r"\b(economics?|macroeconomics?|microeconomics?|econometrics?)\b",
                r"\b(inflation|gdp|monetary|fiscal|central bank)\b",
            ]
        )
        self._humanities_kw = self._compile(
            [
                r"\b(history|philosophy|linguistics?|anthropology|sociology)\b",
                r"\b(ethics?|epistemology|ontology|aesthetics?)\b",
                r"\b(literature|classics|theology|religion|arts?)\b",
            ]
        )
        self._law_policy_kw = self._compile(
            [
                r"\b(law|legal|jurisprudence|regulation|policy|governance)\b",
                r"\b(copyright|patent|antitrust|compliance|privacy|gdpr|hipaa)\b",
            ]
        )

    @staticmethod
    def _compile(patterns: Sequence[str]) -> List[re.Pattern[str]]:
        return [re.compile(p, flags=re.IGNORECASE) for p in patterns]

    @staticmethod
    def _count_hits(text: str, patterns: Sequence[re.Pattern[str]]) -> int:
        # Count unique keyword matches to reduce over-weighting repeated words
        hits: Set[str] = set()
        for pat in patterns:
            for m in pat.finditer(text):
                # Use normalized snippet to register a hit
                span = m.group(0).lower()
                hits.add(span)
        return len(hits)

    def _score_domains(self, text: str) -> Dict[str, int]:
        # Simple additive scores across domain keyword sets
        scores = {
            "bio": self._count_hits(text, self._bio_kw),
            "cs": self._count_hits(text, self._cs_kw),
            "math_phys": self._count_hits(text, self._math_phys_kw),
            "finance_econ": self._count_hits(text, self._finance_econ_kw),
            "humanities": self._count_hits(text, self._humanities_kw),
            "law_policy": self._count_hits(text, self._law_policy_kw),
        }
        return scores

    def _providers_for_domain(self, domain: str) -> Tuple[str, ...]:
        # Preference lists by domain. Ordered high → low.
        if domain == "bio":
            return (self.PUBMED, self.CROSSREF, self.WEB, self.SEMANTIC_SCHOLAR)
        if domain == "cs":
            return (self.SEMANTIC_SCHOLAR, self.CROSSREF, self.WEB)
        if domain == "math_phys":
            return (self.CROSSREF, self.SEMANTIC_SCHOLAR, self.WEB)
        if domain == "finance_econ":
            return (self.CROSSREF, self.WEB, self.SEMANTIC_SCHOLAR)
        if domain == "humanities":
            return (self.CROSSREF, self.WEB)
        if domain == "law_policy":
            return (self.CROSSREF, self.WEB)
        # General fallback
        return self._GENERAL_PREF

    def _ranked_domains(self, scores: Dict[str, int]) -> List[str]:
        # Sort domains by score desc; stable order for ties by domain name
        return sorted(scores.keys(), key=lambda d: (-scores[d], d))

    def select_sources(self, query_text: str, enabled_sources: Iterable[str]) -> List[str]:
        """Return ordered provider names for a query, filtered by enabled sources.

        Args:
            query_text: The research query text (derived from INPUT/ context).
            enabled_sources: Providers currently available (as provided by the
                ResearchAPIOrchestrator.get_available_sources()).

        Returns:
            Ordered list of provider names to query for this input.
        """
        enabled: List[str] = list(enabled_sources)
        enabled_set: Set[str] = set(enabled)
        if not enabled:
            return []

        text = (query_text or "").lower()

        scores = self._score_domains(text)
        ranked = self._ranked_domains(scores)

        # Pick the first domain with any hits; otherwise use general
        chosen_domain: Optional[str] = None
        for d in ranked:
            if scores[d] > 0:
                chosen_domain = d
                break

        pref: Tuple[str, ...] = (
            self._providers_for_domain(chosen_domain) if chosen_domain else self._GENERAL_PREF
        )

        # Filter by enabled and preserve preference order
        ordered: List[str] = [p for p in pref if p in enabled_set]

        # If empty (e.g., all preferred providers disabled), fall back to general preference
        if not ordered:
            ordered = [p for p in self._GENERAL_PREF if p in enabled_set]

        # As a last resort (shouldn't happen), return any enabled sources in stable order
        if not ordered:
            ordered = enabled

        return ordered