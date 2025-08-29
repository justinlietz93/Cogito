"""
Integration test for the ArXiv reference service.

This module contains tests to verify that the ArXiv reference service works correctly
with its modular implementation.
"""

import os
import sys
import unittest
from pathlib import Path

# Add the parent directory to the path so we can import the src modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.arxiv_reference_service import ArxivReferenceService
from src.arxiv.utils import TextProcessor
from src.arxiv.bibtex_converter import BibTexConverter

class TestArxivReferenceService(unittest.TestCase):
    """Test the ArXiv reference service integration."""
    
    def setUp(self):
        """Set up the test."""
        # Use a test cache directory to avoid polluting the real cache
        test_cache_dir = 'storage/test_arxiv_cache'
        # Ensure the directory exists
        os.makedirs(test_cache_dir, exist_ok=True)
        # Initialize the service
        self.service = ArxivReferenceService(cache_dir=test_cache_dir)
    
    def test_text_processor(self):
        """Test the text processor."""
        # Test keyword extraction
        text = """
        Quantum mechanics is the study of physical phenomena at nanoscopic scales, 
        where the action is on the order of the Planck constant. It departs from 
        classical mechanics primarily at the quantum realm of atomic and subatomic 
        length scales. Quantum mechanics provides a mathematical description of much 
        of the dual particle-like and wave-like behavior and interactions of energy 
        and matter.
        """
        keywords = TextProcessor.extract_keywords(text, max_keywords=5)
        self.assertTrue(len(keywords) > 0, "Should extract at least one keyword")
        self.assertTrue(any("quantum" in kw for kw in keywords), 
                        "Should extract 'quantum' as a keyword")
        
        # Test domain-specific terms
        domains = ["physics"]
        domain_terms = TextProcessor.extract_domain_specific_terms(text, domains=domains)
        self.assertTrue(len(domain_terms) > 0, "Should extract at least one domain term")
    
    def test_search_query_creation(self):
        """Test creating search queries."""
        terms = ["quantum mechanics", "physics", "particles"]
        query = TextProcessor.create_arxiv_search_query(terms)
        
        # Check that all terms are in the query
        for term in terms:
            if " " in term:
                self.assertIn(f'all:"{term}"', query)
            else:
                self.assertIn(f'all:{term}', query)
        
        # Check that OR is used to join terms
        self.assertIn(" OR ", query)
    
    def test_bibtex_conversion(self):
        """Test BibTeX conversion."""
        # Create a sample paper
        paper = {
            'id': '2203.01234',
            'title': 'Understanding Quantum Mechanics',
            'authors': ['Alice Researcher', 'Bob Scientist'],
            'published': '2022-03-01T12:00:00Z',
            'abstract': 'This paper describes quantum mechanics in detail.',
            'primary_category': 'quant-ph',
        }
        
        # Convert to BibTeX
        bibtex = BibTexConverter.paper_to_bibtex(paper)
        
        # Check that the BibTeX entry contains the expected fields
        self.assertIn('@', bibtex)
        self.assertIn('author = {Alice Researcher and Bob Scientist}', bibtex)
        self.assertIn('title = {Understanding Quantum Mechanics}', bibtex)
        self.assertIn('year = {2022}', bibtex)
        self.assertIn('eprint = {2203.01234}', bibtex)
        self.assertIn('archivePrefix = {arXiv}', bibtex)
    
    def test_offline_functionality(self):
        """Test offline functionality with dummy data."""
        # Add a paper to global references
        paper_id = "2203.01234"
        paper = {
            'id': paper_id,
            'title': 'Understanding Quantum Mechanics',
            'authors': ['Alice Researcher', 'Bob Scientist'],
            'published': '2022-03-01T12:00:00Z',
            'abstract': 'This paper describes quantum mechanics in detail.',
            'primary_category': 'quant-ph',
        }
        self.service.global_references[paper_id] = paper
        
        # Register for an agent
        agent_name = "Aristotle"
        self.service.register_reference_for_agent(agent_name, paper_id)
        
        # Get references for the agent
        agent_refs = self.service.get_agent_references(agent_name)
        self.assertEqual(len(agent_refs), 1)
        self.assertEqual(agent_refs[0]['id'], paper_id)
        
        # Generate BibTeX
        bibtex = self.service.generate_bibtex_for_all_references()
        self.assertIn(paper_id, bibtex)
    
    @unittest.skip("Skipping online test to avoid real API calls")
    def test_online_search(self):
        """Test searching ArXiv online (skipped by default)."""
        # This test makes actual API calls and should be enabled manually
        results = self.service.search_arxiv(
            'quantum mechanics',
            max_results=2,
            use_cache=True
        )
        self.assertTrue(len(results) > 0, "Should find at least one result")
        self.assertTrue(all('id' in paper for paper in results), 
                        "All papers should have an ID")


if __name__ == '__main__':
    unittest.main()
