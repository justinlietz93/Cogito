#!/usr/bin/env python
"""
Test script for the ArXiv Vector Reference Service.

This script demonstrates:
1. Setting up the vector-enhanced reference service
2. Adding papers to both the regular cache and vector store
3. Performing content-based searches with semantic matching
4. Comparing results with the regular reference service
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, List, Any
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("arxiv_vector_reference_demo")

# Ensure proper import paths
sys.path.insert(0, os.path.abspath('.'))
from src.arxiv.arxiv_reference_service import ArxivReferenceService
from src.arxiv.arxiv_vector_reference_service import ArxivVectorReferenceService

# Sample content for searching
SAMPLE_CONTENT = """
Quantum computing offers significant potential advantages for solving certain computational problems.
The principle of quantum superposition allows quantum bits (qubits) to exist in multiple states simultaneously,
enabling parallel computation at a scale impossible for classical computers.
However, quantum decoherence presents a major challenge to building practical quantum computers.
Recent advances in error correction codes and topological quantum computing may provide solutions to these issues.
"""

PHILOSOPHICAL_CONTENT = """
The nature of consciousness and its relation to physical reality remains one of the most challenging problems
in philosophy of mind. The hard problem of consciousness refers to the difficulty in explaining how and why
physical processes in the brain give rise to subjective experience. Various theories, including functionalism,
dualism, and panpsychism, attempt to address this gap between physical processes and qualia.
"""

MACHINE_LEARNING_CONTENT = """
Deep neural networks have revolutionized the field of machine learning by enabling unprecedented accuracy in tasks
like image recognition, natural language processing, and reinforcement learning. However, these models often act
as black boxes, making their decision-making processes opaque. Explainable AI (XAI) techniques aim to address
this issue by making neural network decisions more interpretable and transparent to humans.
"""

def demo_vector_reference_service(force_fallback: bool = False, openai_api_key: str = None):
    """
    Demonstrate the ArXiv vector reference service.
    
    Args:
        force_fallback: Force use of the fallback implementation
        openai_api_key: OpenAI API key for embeddings
    """
    logger.info("Starting ArXiv vector reference service demo")
    
    # Initialize configuration
    cache_dir = "storage/vector_reference_demo"
    config = {
        'arxiv': {
            'cache_dir': cache_dir,
            'vector_cache_dir': os.path.join(cache_dir, 'vector'),
            'cache_ttl_days': 30,
            'force_vector_fallback': force_fallback
        }
    }
    
    if openai_api_key:
        config['arxiv']['openai_api_key'] = openai_api_key
    
    # Initialize services
    logger.info("Initializing standard reference service")
    regular_service = ArxivReferenceService(config=config)
    
    logger.info("Initializing vector-enhanced reference service")
    vector_service = ArxivVectorReferenceService(config=config)
    
    # Warm up the services with some initial queries
    logger.info("\nWarming up services with initial searches...")
    warmup_queries = [
        "quantum computing error correction",
        "consciousness philosophy mind",
        "machine learning interpretability"
    ]
    
    for query in warmup_queries:
        logger.info(f"Searching for: {query}")
        # Search with regular service (also warms up vector service)
        vector_service.search_arxiv(query, max_results=5)
    
    # Get cache stats
    logger.info("\nCache statistics after warmup:")
    regular_stats = regular_service.get_cache_stats()
    vector_stats = vector_service.get_cache_stats()
    
    if regular_stats:
        logger.info(f"Regular service cache stats: {json.dumps(regular_stats, indent=2)}")
    if vector_stats:
        logger.info(f"Vector service cache stats: {json.dumps(vector_stats, indent=2)}")
    
    # Demonstrate content-based reference retrieval
    logger.info("\nDemonstrating content-based reference retrieval...")
    
    # Test with quantum computing content
    logger.info("\n=== Quantum Computing Content ===")
    logger.info(SAMPLE_CONTENT)
    
    logger.info("\nRegular service results:")
    regular_results = regular_service.get_references_for_content(SAMPLE_CONTENT, max_results=3)
    for i, paper in enumerate(regular_results, 1):
        logger.info(f"{i}. {paper.get('title', 'Unknown')} (ID: {paper.get('id', 'Unknown')})")
        
        # Handle different author formats
        authors_list = paper.get('authors', [])
        author_names = []
        for author in authors_list:
            if isinstance(author, dict):
                # Dictionary format: {"name": "Author Name", ...}
                author_name = author.get('name', '')
                if author_name:
                    author_names.append(author_name)
            elif isinstance(author, str):
                # String format: "Author Name"
                author_names.append(author)
        authors_str = ', '.join(author_names)
        
        logger.info(f"   Authors: {authors_str}")
        logger.info(f"   Summary: {paper.get('summary', 'No summary')[:150]}...")
    
    logger.info("\nVector service results:")
    vector_results = vector_service.get_references_for_content(SAMPLE_CONTENT, max_results=3)
    for i, paper in enumerate(vector_results, 1):
        logger.info(f"{i}. {paper.get('title', 'Unknown')} (ID: {paper.get('id', 'Unknown')})")
        
        # Handle different author formats
        authors_list = paper.get('authors', [])
        author_names = []
        for author in authors_list:
            if isinstance(author, dict):
                # Dictionary format: {"name": "Author Name", ...}
                author_name = author.get('name', '')
                if author_name:
                    author_names.append(author_name)
            elif isinstance(author, str):
                # String format: "Author Name"
                author_names.append(author)
        authors_str = ', '.join(author_names)
        
        logger.info(f"   Authors: {authors_str}")
        logger.info(f"   Summary: {paper.get('summary', 'No summary')[:150]}...")
    
    # Test with philosophical content
    logger.info("\n=== Philosophy of Mind Content ===")
    logger.info(PHILOSOPHICAL_CONTENT)
    
    logger.info("\nRegular service results:")
    regular_results = regular_service.get_references_for_content(PHILOSOPHICAL_CONTENT, max_results=3)
    for i, paper in enumerate(regular_results, 1):
        logger.info(f"{i}. {paper.get('title', 'Unknown')} (ID: {paper.get('id', 'Unknown')})")
        
        # Handle different author formats
        authors_list = paper.get('authors', [])
        author_names = []
        for author in authors_list:
            if isinstance(author, dict):
                # Dictionary format: {"name": "Author Name", ...}
                author_name = author.get('name', '')
                if author_name:
                    author_names.append(author_name)
            elif isinstance(author, str):
                # String format: "Author Name"
                author_names.append(author)
        authors_str = ', '.join(author_names)
        
        logger.info(f"   Authors: {authors_str}")
        logger.info(f"   Summary: {paper.get('summary', 'No summary')[:150]}...")
    
    logger.info("\nVector service results:")
    vector_results = vector_service.get_references_for_content(PHILOSOPHICAL_CONTENT, max_results=3)
    for i, paper in enumerate(vector_results, 1):
        logger.info(f"{i}. {paper.get('title', 'Unknown')} (ID: {paper.get('id', 'Unknown')})")
        
        # Handle different author formats
        authors_list = paper.get('authors', [])
        author_names = []
        for author in authors_list:
            if isinstance(author, dict):
                # Dictionary format: {"name": "Author Name", ...}
                author_name = author.get('name', '')
                if author_name:
                    author_names.append(author_name)
            elif isinstance(author, str):
                # String format: "Author Name"
                author_names.append(author)
        authors_str = ', '.join(author_names)
        
        logger.info(f"   Authors: {authors_str}")
        logger.info(f"   Summary: {paper.get('summary', 'No summary')[:150]}...")
    
    # Test with machine learning content
    logger.info("\n=== Machine Learning Content ===")
    logger.info(MACHINE_LEARNING_CONTENT)
    
    logger.info("\nDemonstrating agent perspective influence:")
    perspectives = [
        "Interpretability and explainability in deep learning",
        "Ethics of black-box AI systems",
        "Applications in healthcare diagnostics"
    ]
    
    for perspective in perspectives:
        logger.info(f"\nAgent perspective: {perspective}")
        results = vector_service.suggest_references_for_agent(
            f"test_agent_{perspective.replace(' ', '_')[:10]}",
            MACHINE_LEARNING_CONTENT,
            agent_perspective=perspective,
            max_results=2
        )
        
        for i, paper in enumerate(results, 1):
            logger.info(f"{i}. {paper.get('title', 'Unknown')} (ID: {paper.get('id', 'Unknown')})")
            
            # Handle different author formats
            authors_list = paper.get('authors', [])
            author_names = []
            for author in authors_list:
                if isinstance(author, dict):
                    # Dictionary format: {"name": "Author Name", ...}
                    author_name = author.get('name', '')
                    if author_name:
                        author_names.append(author_name)
                elif isinstance(author, str):
                    # String format: "Author Name"
                    author_names.append(author)
            authors_str = ', '.join(author_names)
            
            logger.info(f"   Authors: {authors_str}")
            logger.info(f"   Summary: {paper.get('summary', 'No summary')[:150]}...")
    
    # Generate BibTeX
    logger.info("\nGenerating BibTeX for all referenced papers:")
    bibtex = vector_service.generate_bibtex_for_all_references()
    logger.info(f"Generated BibTeX with {bibtex.count('@article')} entries")
    
    # Final stats
    logger.info("\nFinal cache statistics:")
    final_stats = vector_service.get_cache_stats()
    if final_stats:
        logger.info(f"Vector service stats: {json.dumps(final_stats, indent=2)}")
    
    logger.info("\nDemo completed")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='ArXiv Vector Reference Service Demo')
    parser.add_argument('--openai-api-key', help='OpenAI API key for embeddings')
    parser.add_argument('--force-fallback', action='store_true', help='Force use of the fallback implementation')
    
    args = parser.parse_args()
    
    # Get the API key from args or environment
    openai_api_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not openai_api_key and not args.force_fallback:
        logger.warning("No OpenAI API key provided and Agno may require it.")
        logger.warning("You can force the use of the fallback implementation with --force-fallback")
    
    # Run the demo
    demo_vector_reference_service(args.force_fallback, openai_api_key)

if __name__ == "__main__":
    main()
