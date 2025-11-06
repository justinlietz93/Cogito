"""Base class and data structures for research API integrations.

Purpose:
    Provide abstract base class and common data structures for all research API
    implementations, ensuring consistent interfaces across different research
    databases and search providers.
External Dependencies:
    Python standard library modules ``abc``, ``dataclasses``, ``typing``.
Fallback Semantics:
    Concrete implementations must define their own fallback strategies.
Timeout Strategy:
    Timeout handling is delegated to concrete implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResearchResult:
    """Container for research API results with standardized fields.
    
    Attributes:
        id: Unique identifier for the research item (paper ID, DOI, URL, etc.)
        title: Title of the research item
        authors: List of author names
        abstract: Abstract or summary text
        url: Direct URL to the resource
        published_date: Publication date (ISO format string)
        source: Source database or provider (e.g., "pubmed", "semantic_scholar")
        metadata: Additional source-specific metadata
        relevance_score: Optional relevance score (0.0-1.0)
    """
    
    id: str
    title: str
    authors: List[str]
    abstract: str
    url: str
    published_date: Optional[str] = None
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: Optional[float] = None


class ResearchAPIBase(ABC):
    """Abstract base class for research API integrations.
    
    All concrete implementations must provide search functionality and handle
    their own rate limiting, caching, and error recovery strategies.
    """
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the research API client.
        
        Args:
            api_key: Optional API key for authenticated access
            config: Optional configuration dictionary with provider-specific settings
        
        Returns:
            None
        
        Raises:
            None
        
        Side Effects:
            May configure logging or initialize cache managers.
        
        Timeout:
            Not applicable for initialization.
        """
        self.api_key = api_key
        self.config = config or {}
        self._setup_client()
    
    @abstractmethod
    def _setup_client(self) -> None:
        """Initialize provider-specific client configuration.
        
        Concrete implementations should configure HTTP clients, cache managers,
        rate limiters, and any other provider-specific infrastructure.
        
        Returns:
            None
        
        Raises:
            Provider-specific configuration errors.
        
        Side Effects:
            Initializes internal state and external dependencies.
        
        Timeout:
            Not applicable for setup.
        """
        pass
    
    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ResearchResult]:
        """Search the research database for matching results.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)
            filters: Optional provider-specific filters
        
        Returns:
            List of ResearchResult objects matching the query
        
        Raises:
            Provider-specific search errors
        
        Side Effects:
            Makes HTTP requests to external APIs, may update caches
        
        Timeout:
            Implementations should use provider-appropriate timeout settings
        """
        pass
    
    @abstractmethod
    def get_by_id(self, item_id: str) -> Optional[ResearchResult]:
        """Retrieve a specific research item by its identifier.
        
        Args:
            item_id: Provider-specific identifier (DOI, PubMed ID, etc.)
        
        Returns:
            ResearchResult if found, None otherwise
        
        Raises:
            Provider-specific retrieval errors
        
        Side Effects:
            Makes HTTP requests to external APIs, may update caches
        
        Timeout:
            Implementations should use provider-appropriate timeout settings
        """
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the human-readable name of this research source.
        
        Returns:
            String identifier for this research source
        """
        pass
