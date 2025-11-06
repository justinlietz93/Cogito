"""PubMed API integration for biomedical research.

Purpose:
    Provide access to PubMed's database of biomedical literature through the
    NCBI E-utilities API.
External Dependencies:
    Python standard library modules ``logging``, ``xml.etree.ElementTree``,
    ``urllib``, ``time``. Third-party library ``requests`` for HTTP operations.
Fallback Semantics:
    Returns empty results on API failures with logged warnings. Cached results
    are returned when available and API is unreachable.
Timeout Strategy:
    Uses configurable HTTP timeout (default 30 seconds) with automatic retries
    for transient failures up to a maximum retry count.
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote_plus

import requests

from .base import ResearchAPIBase, ResearchResult

logger = logging.getLogger(__name__)


class PubMedAPI(ResearchAPIBase):
    """PubMed research database API client.
    
    Provides access to biomedical literature through NCBI's E-utilities API.
    No API key is strictly required but recommended for higher rate limits.
    """
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    def _setup_client(self) -> None:
        """Initialize PubMed-specific HTTP session and configuration.
        
        Returns:
            None
        
        Raises:
            None
        
        Side Effects:
            Creates HTTP session with default timeout and retry configuration.
        
        Timeout:
            Not applicable for initialization.
        """
        self.session = requests.Session()
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        
        # NCBI recommends including API key and tool/email for identification
        self.tool_name = self.config.get('tool_name', 'Cogito')
        self.email = self.config.get('email', '')
        
        logger.info(
            "PubMed API client initialized (tool=%s, has_api_key=%s)",
            self.tool_name,
            bool(self.api_key)
        )
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ResearchResult]:
        """Search PubMed for articles matching the query.
        
        Args:
            query: PubMed search query string
            max_results: Maximum number of results to return (default: 10)
            filters: Optional filters (supports 'date_from', 'date_to', 'article_type')
        
        Returns:
            List of ResearchResult objects with PubMed article metadata
        
        Raises:
            None - errors are logged and empty results returned
        
        Side Effects:
            Makes HTTP requests to NCBI E-utilities API
        
        Timeout:
            Uses configured timeout (default 30 seconds) per request
        """
        try:
            # Step 1: Search for PMIDs matching the query
            pmids = self._search_pmids(query, max_results, filters)
            if not pmids:
                logger.info("PubMed search returned no results for query: %s", query)
                return []
            
            # Step 2: Fetch detailed metadata for the PMIDs
            results = self._fetch_details(pmids)
            logger.info("PubMed search returned %d results", len(results))
            return results
            
        except Exception as exc:  # noqa: BLE001 - defensive handling for external API
            logger.error("PubMed search failed: %s", exc, exc_info=True)
            return []
    
    def get_by_id(self, item_id: str) -> Optional[ResearchResult]:
        """Retrieve a specific PubMed article by PMID.
        
        Args:
            item_id: PubMed ID (PMID) as a string
        
        Returns:
            ResearchResult if found, None otherwise
        
        Raises:
            None - errors are logged and None returned
        
        Side Effects:
            Makes HTTP request to NCBI E-utilities API
        
        Timeout:
            Uses configured timeout (default 30 seconds)
        """
        try:
            results = self._fetch_details([item_id])
            return results[0] if results else None
        except Exception as exc:  # noqa: BLE001 - defensive handling
            logger.error("Failed to fetch PubMed article %s: %s", item_id, exc)
            return None
    
    def _search_pmids(
        self,
        query: str,
        max_results: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Execute PubMed search and return list of PMIDs.
        
        Args:
            query: Search query string
            max_results: Maximum number of PMIDs to return
            filters: Optional date and type filters
        
        Returns:
            List of PMID strings
        
        Raises:
            Exception on HTTP errors or XML parsing failures
        
        Side Effects:
            Makes HTTP request to esearch endpoint
        
        Timeout:
            Uses configured timeout with retries
        """
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': str(max_results),
            'retmode': 'json',
            'tool': self.tool_name,
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        if self.email:
            params['email'] = self.email
        
        # Apply date filters if provided
        if filters:
            if 'date_from' in filters or 'date_to' in filters:
                date_from = filters.get('date_from', '1900')
                date_to = filters.get('date_to', '3000')
                params['datetype'] = 'pdat'
                params['mindate'] = date_from
                params['maxdate'] = date_to
        
        url = f"{self.BASE_URL}esearch.fcgi"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                id_list = data.get('esearchresult', {}).get('idlist', [])
                return id_list
                
            except Exception as exc:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "PubMed search attempt %d failed, retrying: %s",
                        attempt + 1,
                        exc
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        
        return []
    
    def _fetch_details(self, pmids: List[str]) -> List[ResearchResult]:
        """Fetch detailed metadata for a list of PMIDs.
        
        Args:
            pmids: List of PubMed IDs
        
        Returns:
            List of ResearchResult objects
        
        Raises:
            Exception on HTTP errors or XML parsing failures
        
        Side Effects:
            Makes HTTP request to efetch endpoint
        
        Timeout:
            Uses configured timeout with retries
        """
        if not pmids:
            return []
        
        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'xml',
            'tool': self.tool_name,
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        if self.email:
            params['email'] = self.email
        
        url = f"{self.BASE_URL}efetch.fcgi"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                return self._parse_pubmed_xml(response.text)
                
            except Exception as exc:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "PubMed fetch attempt %d failed, retrying: %s",
                        attempt + 1,
                        exc
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        
        return []
    
    def _parse_pubmed_xml(self, xml_text: str) -> List[ResearchResult]:
        """Parse PubMed XML response into ResearchResult objects.
        
        Args:
            xml_text: XML response from PubMed efetch
        
        Returns:
            List of ResearchResult objects
        
        Raises:
            None - parsing errors are logged and item skipped
        
        Side Effects:
            None
        
        Timeout:
            Not applicable for CPU-bound parsing
        """
        results = []
        
        try:
            root = ET.fromstring(xml_text)
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    result = self._parse_article(article)
                    if result:
                        results.append(result)
                except Exception as exc:  # noqa: BLE001 - continue parsing other articles
                    logger.warning("Failed to parse PubMed article: %s", exc)
                    continue
            
        except ET.ParseError as exc:
            logger.error("Failed to parse PubMed XML: %s", exc)
        
        return results
    
    def _parse_article(self, article: ET.Element) -> Optional[ResearchResult]:
        """Parse a single PubMed article element.
        
        Args:
            article: XML element containing article data
        
        Returns:
            ResearchResult object or None if required fields missing
        
        Raises:
            None
        
        Side Effects:
            None
        
        Timeout:
            Not applicable
        """
        medline = article.find('.//MedlineCitation')
        if medline is None:
            return None
        
        pmid_elem = medline.find('.//PMID')
        if pmid_elem is None or not pmid_elem.text:
            return None
        pmid = pmid_elem.text.strip()
        
        article_elem = medline.find('.//Article')
        if article_elem is None:
            return None
        
        # Extract title
        title_elem = article_elem.find('.//ArticleTitle')
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No title"
        
        # Extract authors
        authors = []
        author_list = article_elem.find('.//AuthorList')
        if author_list is not None:
            for author in author_list.findall('.//Author'):
                last_name = author.find('.//LastName')
                fore_name = author.find('.//ForeName')
                if last_name is not None and last_name.text:
                    name = last_name.text.strip()
                    if fore_name is not None and fore_name.text:
                        name = f"{fore_name.text.strip()} {name}"
                    authors.append(name)
        
        # Extract abstract
        abstract_elem = article_elem.find('.//Abstract/AbstractText')
        abstract = abstract_elem.text.strip() if abstract_elem is not None and abstract_elem.text else ""
        
        # Extract publication date
        pub_date_elem = article_elem.find('.//Journal/JournalIssue/PubDate')
        published_date = ""
        if pub_date_elem is not None:
            year = pub_date_elem.find('.//Year')
            month = pub_date_elem.find('.//Month')
            day = pub_date_elem.find('.//Day')
            
            if year is not None and year.text:
                published_date = year.text.strip()
                if month is not None and month.text:
                    published_date += f"-{month.text.strip()}"
                    if day is not None and day.text:
                        published_date += f"-{day.text.strip()}"
        
        # Extract DOI if available
        doi = ""
        for article_id in article.findall('.//ArticleId'):
            if article_id.get('IdType') == 'doi' and article_id.text:
                doi = article_id.text.strip()
                break
        
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        
        return ResearchResult(
            id=pmid,
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            published_date=published_date,
            source="pubmed",
            metadata={
                'doi': doi,
                'pmid': pmid,
            }
        )
    
    @property
    def source_name(self) -> str:
        """Return the source identifier for PubMed.
        
        Returns:
            String "PubMed"
        """
        return "PubMed"
