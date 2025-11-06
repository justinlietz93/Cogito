"""Research API orchestrator for coordinating multiple search sources.

Purpose:
    Coordinate searches across multiple research databases and web search
    providers, merging results and removing duplicates to provide comprehensive
    research coverage.
External Dependencies:
    Python standard library modules ``logging``, ``concurrent.futures``.
Fallback Semantics:
    Continues with available providers when some fail. Returns combined results
    from successful providers with logged warnings for failures.
Timeout Strategy:
    Uses configured timeout per provider with parallel execution to minimize
    total search time. Individual provider timeouts are independent.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set

from .base import ResearchAPIBase, ResearchResult
from .pubmed import PubMedAPI
from .semantic_scholar import SemanticScholarAPI
from .crossref import CrossRefAPI
from .web_search import WebSearchAPI

logger = logging.getLogger(__name__)


class ResearchAPIOrchestrator:
    """Orchestrate searches across multiple research APIs.
    
    Coordinates parallel searches across configured research databases and
    web search providers, merging results intelligently and removing duplicates
    based on title similarity and URL matching.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the research API orchestrator.
        
        Args:
            config: Configuration dictionary with provider settings and API keys
        
        Returns:
            None
        
        Raises:
            None
        
        Side Effects:
            Initializes all configured research API clients.
        
        Timeout:
            Not applicable for initialization.
        """
        self.config = config or {}
        self.providers: Dict[str, ResearchAPIBase] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize all enabled research API providers.
        
        Returns:
            None
        
        Raises:
            None - provider initialization errors are logged
        
        Side Effects:
            Creates and stores provider instances in self.providers
        
        Timeout:
            Not applicable
        """
        research_config = self.config.get('research_apis', {})
        
        # Initialize PubMed (biomedical research)
        if research_config.get('pubmed', {}).get('enabled', True):
            try:
                pubmed_config = research_config.get('pubmed', {})
                self.providers['pubmed'] = PubMedAPI(
                    api_key=pubmed_config.get('api_key'),
                    config=pubmed_config
                )
                logger.info("PubMed provider initialized")
            except Exception as exc:  # noqa: BLE001 - continue with other providers
                logger.error("Failed to initialize PubMed provider: %s", exc)
        
        # Initialize Semantic Scholar (computer science)
        if research_config.get('semantic_scholar', {}).get('enabled', True):
            try:
                ss_config = research_config.get('semantic_scholar', {})
                self.providers['semantic_scholar'] = SemanticScholarAPI(
                    api_key=ss_config.get('api_key'),
                    config=ss_config
                )
                logger.info("Semantic Scholar provider initialized")
            except Exception as exc:  # noqa: BLE001 - continue with other providers
                logger.error("Failed to initialize Semantic Scholar provider: %s", exc)
        
        # Initialize CrossRef (DOI resolution)
        if research_config.get('crossref', {}).get('enabled', True):
            try:
                crossref_config = research_config.get('crossref', {})
                self.providers['crossref'] = CrossRefAPI(
                    config=crossref_config
                )
                logger.info("CrossRef provider initialized")
            except Exception as exc:  # noqa: BLE001 - continue with other providers
                logger.error("Failed to initialize CrossRef provider: %s", exc)
        
        # Initialize Web Search
        if research_config.get('web_search', {}).get('enabled', True):
            try:
                web_config = research_config.get('web_search', {})
                self.providers['web_search'] = WebSearchAPI(
                    api_key=web_config.get('api_key'),  # SerpAPI key if available
                    config=web_config
                )
                logger.info("Web Search provider initialized")
            except Exception as exc:  # noqa: BLE001 - continue with other providers
                logger.error("Failed to initialize Web Search provider: %s", exc)
        
        logger.info("Research API orchestrator initialized with %d providers", len(self.providers))
    
    def search_all(
        self,
        query: str,
        max_results_per_source: int = 10,
        sources: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        parallel: bool = True
    ) -> List[ResearchResult]:
        """Search across all enabled research sources.
        
        Args:
            query: Search query string
            max_results_per_source: Maximum results from each source (default: 10)
            sources: Optional list of source names to query (queries all if None)
            filters: Optional provider-specific filters
            parallel: Execute searches in parallel when True (default: True)
        
        Returns:
            Combined list of ResearchResult objects from all sources,
            deduplicated and sorted by relevance when available
        
        Raises:
            None - individual provider failures are logged
        
        Side Effects:
            Makes HTTP requests to multiple research APIs
        
        Timeout:
            Total time depends on slowest provider when parallel=True,
            sum of all timeouts when parallel=False
        """
        if not self.providers:
            logger.warning("No research providers are available")
            return []
        
        # Determine which providers to query
        active_sources = sources if sources else list(self.providers.keys())
        active_providers = {
            name: provider
            for name, provider in self.providers.items()
            if name in active_sources
        }
        
        if not active_providers:
            logger.warning("No matching providers for sources: %s", sources)
            return []
        
        logger.info(
            "Searching across %d sources: %s",
            len(active_providers),
            ', '.join(active_providers.keys())
        )
        
        # Execute searches
        if parallel:
            all_results = self._search_parallel(
                active_providers,
                query,
                max_results_per_source,
                filters
            )
        else:
            all_results = self._search_sequential(
                active_providers,
                query,
                max_results_per_source,
                filters
            )
        
        # Deduplicate results
        deduplicated = self._deduplicate_results(all_results)
        
        logger.info(
            "Search complete: %d total results, %d after deduplication",
            len(all_results),
            len(deduplicated)
        )
        
        return deduplicated
    
    def _search_parallel(
        self,
        providers: Dict[str, ResearchAPIBase],
        query: str,
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[ResearchResult]:
        """Execute searches in parallel across providers.
        
        Args:
            providers: Dictionary of provider name to instance
            query: Search query string
            max_results: Maximum results per provider
            filters: Optional filters
        
        Returns:
            Combined list of results from all providers
        
        Raises:
            None - individual failures are logged
        
        Side Effects:
            Makes parallel HTTP requests
        
        Timeout:
            Limited by slowest provider
        """
        all_results = []
        
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            future_to_source = {
                executor.submit(
                    provider.search,
                    query,
                    max_results,
                    filters
                ): name
                for name, provider in providers.items()
            }
            
            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.debug(
                        "Provider %s returned %d results",
                        source_name,
                        len(results)
                    )
                except Exception as exc:  # noqa: BLE001 - continue with other providers
                    logger.error(
                        "Search failed for provider %s: %s",
                        source_name,
                        exc,
                        exc_info=True
                    )
        
        return all_results
    
    def _search_sequential(
        self,
        providers: Dict[str, ResearchAPIBase],
        query: str,
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[ResearchResult]:
        """Execute searches sequentially across providers.
        
        Args:
            providers: Dictionary of provider name to instance
            query: Search query string
            max_results: Maximum results per provider
            filters: Optional filters
        
        Returns:
            Combined list of results from all providers
        
        Raises:
            None - individual failures are logged
        
        Side Effects:
            Makes sequential HTTP requests
        
        Timeout:
            Sum of all provider timeouts
        """
        all_results = []
        
        for name, provider in providers.items():
            try:
                results = provider.search(query, max_results, filters)
                all_results.extend(results)
                logger.debug("Provider %s returned %d results", name, len(results))
            except Exception as exc:  # noqa: BLE001 - continue with other providers
                logger.error(
                    "Search failed for provider %s: %s",
                    name,
                    exc,
                    exc_info=True
                )
        
        return all_results
    
    def _deduplicate_results(self, results: List[ResearchResult]) -> List[ResearchResult]:
        """Remove duplicate results based on URL and title similarity.
        
        Args:
            results: List of ResearchResult objects
        
        Returns:
            Deduplicated list of ResearchResult objects
        
        Raises:
            None
        
        Side Effects:
            None
        
        Timeout:
            Not applicable for in-memory deduplication
        """
        if not results:
            return []
        
        seen_urls: Set[str] = set()
        seen_titles: Set[str] = set()
        deduplicated: List[ResearchResult] = []
        
        for result in results:
            # Normalize for comparison
            url_key = result.url.lower().strip('/')
            title_key = result.title.lower().strip()
            
            # Skip if we've seen this URL or very similar title
            if url_key in seen_urls:
                continue
            if title_key in seen_titles:
                continue
            
            seen_urls.add(url_key)
            seen_titles.add(title_key)
            deduplicated.append(result)
        
        return deduplicated
    
    def get_available_sources(self) -> List[str]:
        """Return list of available research source names.
        
        Returns:
            List of source name strings
        """
        return list(self.providers.keys())
