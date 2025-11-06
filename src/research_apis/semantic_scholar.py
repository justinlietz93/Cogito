"""Semantic Scholar API integration for computer science research.

Purpose:
    Provide access to Semantic Scholar's database of academic papers with
    focus on computer science and related fields.
External Dependencies:
    Python standard library modules ``logging``, ``time``. Third-party library
    ``requests`` for HTTP operations.
Fallback Semantics:
    Returns empty results on API failures with logged warnings. Implements
    exponential backoff for rate limit errors.
Timeout Strategy:
    Uses configurable HTTP timeout (default 30 seconds) with automatic retries
    for transient failures up to a maximum retry count.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from .base import ResearchAPIBase, ResearchResult

logger = logging.getLogger(__name__)


class SemanticScholarAPI(ResearchAPIBase):
    """Semantic Scholar research database API client.
    
    Provides access to academic papers with rich metadata including citations,
    references, and paper embeddings for semantic search.
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def _setup_client(self) -> None:
        """Initialize Semantic Scholar HTTP session and configuration.
        
        Returns:
            None
        
        Raises:
            None
        
        Side Effects:
            Creates HTTP session with authentication headers if API key provided.
        
        Timeout:
            Not applicable for initialization.
        """
        self.session = requests.Session()
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        
        # Set API key header if provided
        if self.api_key:
            self.session.headers.update({'x-api-key': self.api_key})
        
        logger.info(
            "Semantic Scholar API client initialized (has_api_key=%s)",
            bool(self.api_key)
        )
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ResearchResult]:
        """Search Semantic Scholar for papers matching the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)
            filters: Optional filters (supports 'year', 'fields_of_study', 'venue')
        
        Returns:
            List of ResearchResult objects with paper metadata
        
        Raises:
            None - errors are logged and empty results returned
        
        Side Effects:
            Makes HTTP requests to Semantic Scholar API
        
        Timeout:
            Uses configured timeout (default 30 seconds) per request
        """
        try:
            url = f"{self.BASE_URL}/paper/search"
            
            params = {
                'query': query,
                'limit': min(max_results, 100),  # API max is 100
                'fields': 'paperId,title,abstract,authors,year,url,citationCount,referenceCount,publicationDate',
            }
            
            # Apply filters if provided
            if filters:
                if 'year' in filters:
                    params['year'] = filters['year']
                if 'fields_of_study' in filters:
                    params['fieldsOfStudy'] = filters['fields_of_study']
                if 'venue' in filters:
                    params['venue'] = filters['venue']
            
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout)
                    
                    # Handle rate limiting with exponential backoff
                    if response.status_code == 429:
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)
                            logger.warning(
                                "Semantic Scholar rate limit hit, waiting %.1f seconds",
                                wait_time
                            )
                            time.sleep(wait_time)
                            continue
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    results = []
                    for paper in data.get('data', []):
                        result = self._parse_paper(paper)
                        if result:
                            results.append(result)
                    
                    logger.info("Semantic Scholar search returned %d results", len(results))
                    return results
                    
                except requests.exceptions.RequestException as exc:
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            "Semantic Scholar search attempt %d failed, retrying: %s",
                            attempt + 1,
                            exc
                        )
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
            
            return []
            
        except Exception as exc:  # noqa: BLE001 - defensive handling
            logger.error("Semantic Scholar search failed: %s", exc, exc_info=True)
            return []
    
    def get_by_id(self, item_id: str) -> Optional[ResearchResult]:
        """Retrieve a specific paper by Semantic Scholar paper ID.
        
        Args:
            item_id: Semantic Scholar paper ID or DOI
        
        Returns:
            ResearchResult if found, None otherwise
        
        Raises:
            None - errors are logged and None returned
        
        Side Effects:
            Makes HTTP request to Semantic Scholar API
        
        Timeout:
            Uses configured timeout (default 30 seconds)
        """
        try:
            url = f"{self.BASE_URL}/paper/{item_id}"
            params = {
                'fields': 'paperId,title,abstract,authors,year,url,citationCount,referenceCount,publicationDate',
            }
            
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout)
                    
                    if response.status_code == 404:
                        return None
                    
                    if response.status_code == 429:
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)
                            time.sleep(wait_time)
                            continue
                    
                    response.raise_for_status()
                    paper = response.json()
                    
                    return self._parse_paper(paper)
                    
                except requests.exceptions.RequestException as exc:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
            
            return None
            
        except Exception as exc:  # noqa: BLE001 - defensive handling
            logger.error("Failed to fetch Semantic Scholar paper %s: %s", item_id, exc)
            return None
    
    def _parse_paper(self, paper: Dict[str, Any]) -> Optional[ResearchResult]:
        """Parse Semantic Scholar paper data into ResearchResult.
        
        Args:
            paper: Paper data dictionary from API response
        
        Returns:
            ResearchResult object or None if required fields missing
        
        Raises:
            None
        
        Side Effects:
            None
        
        Timeout:
            Not applicable
        """
        if not paper.get('paperId'):
            return None
        
        paper_id = paper['paperId']
        title = paper.get('title', 'No title')
        abstract = paper.get('abstract', '')
        
        # Extract authors
        authors = []
        for author_data in paper.get('authors', []):
            if author_data.get('name'):
                authors.append(author_data['name'])
        
        # Get publication date
        published_date = paper.get('publicationDate', '')
        if not published_date and paper.get('year'):
            published_date = str(paper['year'])
        
        # Construct URL
        url = paper.get('url', f"https://www.semanticscholar.org/paper/{paper_id}")
        
        return ResearchResult(
            id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract or "",
            url=url,
            published_date=published_date,
            source="semantic_scholar",
            metadata={
                'paper_id': paper_id,
                'citation_count': paper.get('citationCount', 0),
                'reference_count': paper.get('referenceCount', 0),
                'year': paper.get('year'),
            }
        )
    
    @property
    def source_name(self) -> str:
        """Return the source identifier for Semantic Scholar.
        
        Returns:
            String "Semantic Scholar"
        """
        return "Semantic Scholar"
