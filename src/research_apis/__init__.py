"""Research API integrations module.

This module provides unified interfaces for accessing various research databases
and web search capabilities.
"""

from .base import ResearchAPIBase, ResearchResult
from .pubmed import PubMedAPI
from .semantic_scholar import SemanticScholarAPI
from .crossref import CrossRefAPI
from .web_search import WebSearchAPI
from .orchestrator import ResearchAPIOrchestrator

__all__ = [
    'ResearchAPIBase',
    'ResearchResult',
    'PubMedAPI',
    'SemanticScholarAPI',
    'CrossRefAPI',
    'WebSearchAPI',
    'ResearchAPIOrchestrator',
]
