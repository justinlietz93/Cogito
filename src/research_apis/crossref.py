"""CrossRef API integration for DOI resolution and metadata.

Purpose:
    Provide access to CrossRef's database for DOI resolution and scholarly
    metadata retrieval across all disciplines.
External Dependencies:
    Python standard library modules ``logging``, ``time``. Third-party library
    ``requests`` for HTTP operations.
Fallback Semantics:
    Returns empty results on API failures with logged warnings. Cached DOI
    lookups are returned when available.
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


class CrossRefAPI(ResearchAPIBase):
    """CrossRef API client for DOI resolution and metadata.
    
    Provides access to CrossRef's comprehensive database of scholarly works
    with focus on DOI resolution and citation metadata.
    """
    
    BASE_URL = "https://api.crossref.org"
    
    def _setup_client(self) -> None:
        """Initialize CrossRef HTTP session and configuration.
        
        Returns:
            None
        
        Raises:
            None
        
        Side Effects:
            Creates HTTP session with polite user agent for rate limit benefits.
        
        Timeout:
            Not applicable for initialization.
        """
        self.session = requests.Session()
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        
        # Set polite user agent for better rate limits
        contact_email = self.config.get('email', 'cogito@example.com')
        self.session.headers.update({
            'User-Agent': f'Cogito/1.0 (mailto:{contact_email})'
        })
        
        logger.info("CrossRef API client initialized")
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ResearchResult]:
        """Search CrossRef for works matching the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)
            filters: Optional filters (supports 'from_pub_date', 'until_pub_date', 'type')
        
        Returns:
            List of ResearchResult objects with work metadata
        
        Raises:
            None - errors are logged and empty results returned
        
        Side Effects:
            Makes HTTP requests to CrossRef API
        
        Timeout:
            Uses configured timeout (default 30 seconds) per request
        """
        try:
            url = f"{self.BASE_URL}/works"
            
            params = {
                'query': query,
                'rows': min(max_results, 1000),  # API max is 1000
            }
            
            # Apply filters if provided
            if filters:
                filter_parts = []
                if 'from_pub_date' in filters:
                    filter_parts.append(f"from-pub-date:{filters['from_pub_date']}")
                if 'until_pub_date' in filters:
                    filter_parts.append(f"until-pub-date:{filters['until_pub_date']}")
                if 'type' in filters:
                    filter_parts.append(f"type:{filters['type']}")
                
                if filter_parts:
                    params['filter'] = ','.join(filter_parts)
            
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout)
                    response.raise_for_status()
                    data = response.json()
                    
                    results = []
                    for item in data.get('message', {}).get('items', []):
                        result = self._parse_work(item)
                        if result:
                            results.append(result)
                    
                    logger.info("CrossRef search returned %d results", len(results))
                    return results
                    
                except requests.exceptions.RequestException as exc:
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            "CrossRef search attempt %d failed, retrying: %s",
                            attempt + 1,
                            exc
                        )
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
            
            return []
            
        except Exception as exc:  # noqa: BLE001 - defensive handling
            logger.error("CrossRef search failed: %s", exc, exc_info=True)
            return []
    
    def get_by_id(self, item_id: str) -> Optional[ResearchResult]:
        """Retrieve a specific work by DOI.
        
        Args:
            item_id: DOI string (can include or omit 'doi.org/' prefix)
        
        Returns:
            ResearchResult if found, None otherwise
        
        Raises:
            None - errors are logged and None returned
        
        Side Effects:
            Makes HTTP request to CrossRef API
        
        Timeout:
            Uses configured timeout (default 30 seconds)
        """
        try:
            # Normalize DOI
            doi = item_id.replace('https://doi.org/', '').replace('http://doi.org/', '')
            
            url = f"{self.BASE_URL}/works/{doi}"
            
            for attempt in range(self.max_retries):
                try:
                    response = self.session.get(url, timeout=self.timeout)
                    
                    if response.status_code == 404:
                        return None
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    return self._parse_work(data.get('message', {}))
                    
                except requests.exceptions.RequestException as exc:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
            
            return None
            
        except Exception as exc:  # noqa: BLE001 - defensive handling
            logger.error("Failed to fetch CrossRef work %s: %s", item_id, exc)
            return None
    
    def _parse_work(self, work: Dict[str, Any]) -> Optional[ResearchResult]:
        """Parse CrossRef work data into ResearchResult.
        
        Args:
            work: Work data dictionary from API response
        
        Returns:
            ResearchResult object or None if required fields missing
        
        Raises:
            None
        
        Side Effects:
            None
        
        Timeout:
            Not applicable
        """
        if not work.get('DOI'):
            return None
        
        doi = work['DOI']
        
        # Get title
        title_list = work.get('title', [])
        title = title_list[0] if title_list else 'No title'
        
        # Get authors
        authors = []
        for author_data in work.get('author', []):
            given = author_data.get('given', '')
            family = author_data.get('family', '')
            if family:
                name = f"{given} {family}".strip() if given else family
                authors.append(name)
        
        # Get abstract if available
        abstract = work.get('abstract', '')
        
        # Get publication date
        published_date = ''
        if 'published-print' in work:
            date_parts = work['published-print'].get('date-parts', [[]])
            if date_parts and date_parts[0]:
                published_date = '-'.join(str(p) for p in date_parts[0])
        elif 'published-online' in work:
            date_parts = work['published-online'].get('date-parts', [[]])
            if date_parts and date_parts[0]:
                published_date = '-'.join(str(p) for p in date_parts[0])
        
        # Construct URL
        url = f"https://doi.org/{doi}"
        
        return ResearchResult(
            id=doi,
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            published_date=published_date,
            source="crossref",
            metadata={
                'doi': doi,
                'type': work.get('type'),
                'publisher': work.get('publisher'),
                'is_referenced_by_count': work.get('is-referenced-by-count', 0),
            }
        )
    
    @property
    def source_name(self) -> str:
        """Return the source identifier for CrossRef.
        
        Returns:
            String "CrossRef"
        """
        return "CrossRef"
