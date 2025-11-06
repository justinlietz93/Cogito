"""Web search API integration using DuckDuckGo and SerpAPI.

Purpose:
    Provide web search capabilities to complement research database queries,
    allowing discovery of non-academic sources, blogs, news, and general web
    content related to research topics.
External Dependencies:
    Python standard library modules ``logging``, ``time``, ``re``. Third-party
    library ``requests`` for HTTP operations.
Fallback Semantics:
    Falls back to DuckDuckGo HTML scraping when SerpAPI is unavailable or
    rate limited. Returns empty results on total failures with logged warnings.
Timeout Strategy:
    Uses configurable HTTP timeout (default 30 seconds) with automatic retries
    for transient failures up to a maximum retry count.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base import ResearchAPIBase, ResearchResult

logger = logging.getLogger(__name__)


class WebSearchAPI(ResearchAPIBase):
    """Web search API client supporting multiple providers.
    
    Provides web search capabilities using SerpAPI (Google, Bing) as primary
    and DuckDuckGo as fallback for broader information discovery.
    """
    
    SERPAPI_URL = "https://serpapi.com/search"
    DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
    
    def _setup_client(self) -> None:
        """Initialize web search HTTP session and configuration.
        
        Returns:
            None
        
        Raises:
            None
        
        Side Effects:
            Creates HTTP session with appropriate user agent headers.
        
        Timeout:
            Not applicable for initialization.
        """
        self.session = requests.Session()
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        
        # Configure search engine preference
        self.search_engine = self.config.get('search_engine', 'google')  # google, bing, duckduckgo
        self.use_fallback = self.config.get('use_fallback', True)
        
        # Set user agent for web scraping
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        logger.info(
            "Web search API client initialized (engine=%s, has_api_key=%s, fallback=%s)",
            self.search_engine,
            bool(self.api_key),
            self.use_fallback
        )
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ResearchResult]:
        """Search the web for content matching the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)
            filters: Optional filters (supports 'domain', 'date_range', 'type')
        
        Returns:
            List of ResearchResult objects with web content metadata
        
        Raises:
            None - errors are logged and empty results returned
        
        Side Effects:
            Makes HTTP requests to search APIs or scrapes web pages
        
        Timeout:
            Uses configured timeout (default 30 seconds) per request
        """
        # Try primary search method (SerpAPI if key available)
        if self.api_key:
            try:
                results = self._search_serpapi(query, max_results, filters)
                if results:
                    logger.info("Web search via SerpAPI returned %d results", len(results))
                    return results
            except Exception as exc:  # noqa: BLE001 - try fallback
                logger.warning("SerpAPI search failed, trying fallback: %s", exc)
        
        # Try fallback method (DuckDuckGo)
        if self.use_fallback:
            try:
                results = self._search_duckduckgo(query, max_results, filters)
                logger.info("Web search via DuckDuckGo returned %d results", len(results))
                return results
            except Exception as exc:  # noqa: BLE001 - defensive handling
                logger.error("DuckDuckGo search failed: %s", exc, exc_info=True)
        
        logger.warning("All web search methods failed for query: %s", query)
        return []
    
    def get_by_id(self, item_id: str) -> Optional[ResearchResult]:
        """Retrieve web content by URL.
        
        Args:
            item_id: URL string
        
        Returns:
            ResearchResult with extracted metadata or None
        
        Raises:
            None - errors are logged and None returned
        
        Side Effects:
            Makes HTTP request to fetch the web page
        
        Timeout:
            Uses configured timeout (default 30 seconds)
        """
        try:
            response = self.session.get(item_id, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.text.strip() if title_tag else "No title"
            
            # Try to extract meta description
            abstract = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                abstract = meta_desc['content'].strip()
            
            return ResearchResult(
                id=item_id,
                title=title,
                authors=[],
                abstract=abstract,
                url=item_id,
                source="web",
                metadata={'fetched_url': item_id}
            )
            
        except Exception as exc:  # noqa: BLE001 - defensive handling
            logger.error("Failed to fetch web content %s: %s", item_id, exc)
            return None
    
    def _search_serpapi(
        self,
        query: str,
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[ResearchResult]:
        """Search using SerpAPI (Google/Bing).
        
        Args:
            query: Search query string
            max_results: Maximum results to return
            filters: Optional search filters
        
        Returns:
            List of ResearchResult objects
        
        Raises:
            Exception on API errors or parsing failures
        
        Side Effects:
            Makes HTTP requests to SerpAPI
        
        Timeout:
            Uses configured timeout with retries
        """
        params = {
            'q': query,
            'api_key': self.api_key,
            'engine': self.search_engine,
            'num': min(max_results, 100),
        }
        
        # Apply domain filter if provided
        if filters and 'domain' in filters:
            params['q'] = f"site:{filters['domain']} {query}"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    self.SERPAPI_URL,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get('organic_results', [])[:max_results]:
                    result = ResearchResult(
                        id=item.get('link', ''),
                        title=item.get('title', 'No title'),
                        authors=[],
                        abstract=item.get('snippet', ''),
                        url=item.get('link', ''),
                        source="web_search",
                        metadata={
                            'search_engine': self.search_engine,
                            'position': item.get('position'),
                        }
                    )
                    results.append(result)
                
                return results
                
            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        
        return []
    
    def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[ResearchResult]:
        """Search using DuckDuckGo HTML interface.
        
        Args:
            query: Search query string
            max_results: Maximum results to return
            filters: Optional search filters
        
        Returns:
            List of ResearchResult objects
        
        Raises:
            Exception on scraping errors or parsing failures
        
        Side Effects:
            Makes HTTP requests to DuckDuckGo and parses HTML
        
        Timeout:
            Uses configured timeout with retries
        """
        # Apply domain filter if provided
        search_query = query
        if filters and 'domain' in filters:
            search_query = f"site:{filters['domain']} {query}"
        
        data = {
            'q': search_query,
            'b': '',  # Start from beginning
        }
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.DUCKDUCKGO_URL,
                    data=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                
                for result_div in soup.find_all('div', class_='result')[:max_results]:
                    # Extract title and URL
                    title_link = result_div.find('a', class_='result__a')
                    if not title_link:
                        continue
                    
                    title = title_link.text.strip()
                    url = title_link.get('href', '')
                    
                    # Extract snippet
                    snippet_div = result_div.find('a', class_='result__snippet')
                    abstract = snippet_div.text.strip() if snippet_div else ''
                    
                    if url and title:
                        result = ResearchResult(
                            id=url,
                            title=title,
                            authors=[],
                            abstract=abstract,
                            url=url,
                            source="web_search",
                            metadata={
                                'search_engine': 'duckduckgo',
                            }
                        )
                        results.append(result)
                
                return results
                
            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        
        return []
    
    @property
    def source_name(self) -> str:
        """Return the source identifier for web search.
        
        Returns:
            String "Web Search"
        """
        return "Web Search"
