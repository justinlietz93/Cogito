#!/usr/bin/env python
"""
ArXiv Reference Integration Demo

This script demonstrates the ArXiv reference integration with ContentAssessor.
It extracts points from sample content and attaches relevant ArXiv references.

Usage:
    python test_arxiv_integration_demo.py
"""

import os
import sys
import json
import logging
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("arxiv_demo")

# Ensure proper import paths
sys.path.insert(0, os.path.abspath('.'))
from src.content_assessor import ContentAssessor

def main():
    """Run the ArXiv integration demo."""
    logger.info("Starting ArXiv integration demo")
    
    # Create sample content with scientific topics
    sample_content = """
    Quantum computing is a form of computing that uses quantum bits or qubits instead of 
    classical bits. Qubits can exist in multiple states simultaneously due to superposition.
    
    Machine learning models, particularly neural networks, have shown remarkable success
    in tasks such as image recognition and natural language processing. Deep learning
    involves neural networks with many layers.
    
    Graph theory is a branch of mathematics that studies graphs, which are mathematical
    structures used to model pairwise relations between objects. A graph is made up of
    vertices and edges that connect pairs of vertices.
    """
    
    logger.info("Created sample content with scientific topics")
    
    # Create configuration
    config = {
        'api': {
            'primary_provider': 'openai',
            'openai': {
                'model': 'o3-mini',
                'retries': 1
            }
        },
        'arxiv': {
            'enabled': True,
            'max_references_per_point': 3,
            'cache_dir': 'storage/arxiv_cache',
            'use_cache': True,
            'search_sort_by': 'relevance',
            'search_sort_order': 'descending',
            'update_bibliography': True
        },
        'latex': {
            'output_dir': 'latex_output',
            'output_filename': 'arxiv_demo_report'
        }
    }
    
    # Create content assessor
    assessor = ContentAssessor()
    assessor.set_logger(logger)
    
    # Try to get a mock result first (to avoid API call if not needed)
    try:
        # Create a sample result for testing without API call
        logger.info("Using mock extraction result for demonstration")
        points = [
            {"id": "point-1", "point": "Quantum computing uses quantum bits or qubits instead of classical bits."},
            {"id": "point-2", "point": "Qubits can exist in multiple states simultaneously due to quantum superposition."},
            {"id": "point-3", "point": "Neural networks are a form of machine learning used for tasks like image recognition."},
            {"id": "point-4", "point": "Deep learning involves neural networks with many layers."},
            {"id": "point-5", "point": "Graph theory studies mathematical structures used to model relations between objects."}
        ]
        
        # Manually call the reference attachment method
        logger.info("Attaching ArXiv references to points...")
        assessor._attach_arxiv_references(points, sample_content, config)
        
        # Check if references were attached
        refs_attached = any('references' in point for point in points)
        
        if not refs_attached:
            logger.warning("No references were attached. Trying full extraction with API call...")
            # If no references were attached, try the full extraction (will call API)
            points = assessor.extract_points(sample_content, config)
    except Exception as e:
        logger.warning(f"Mock extraction failed: {e}. Trying full extraction...")
        # If mock extraction fails, try the full extraction (will call API)
        points = assessor.extract_points(sample_content, config)
    
    # Display results
    logger.info(f"Extracted {len(points)} points with references:")
    
    for i, point in enumerate(points):
        print(f"\nPoint {i+1}: {point['point']}")
        
        if 'references' in point and point['references']:
            print(f"  References ({len(point['references'])}):")
            for j, ref in enumerate(point['references']):
                print(f"    {j+1}. {ref['title']}")
                print(f"       Authors: {', '.join(ref.get('authors', []))}")
                print(f"       URL: {ref.get('url', 'N/A')}")
                print(f"       Published: {ref.get('published', 'N/A')}")
                if 'summary' in ref:
                    summary = ref['summary'].replace('\n', ' ')
                    print(f"       Summary: {summary[:100]}...")
        else:
            print("  No references found.")
    
    # Check if bibliography was created
    bib_path = os.path.join(
        config['latex']['output_dir'],
        f"{config['latex']['output_filename']}_bibliography.bib"
    )
    
    if os.path.exists(bib_path):
        print(f"\nBibliography file created at: {bib_path}")
        
        # Print first few lines of bibliography
        with open(bib_path, 'r', encoding='utf-8') as f:
            bib_content = f.read()
            print("\nBibliography preview:")
            print("-------------------")
            # Print first 10 lines or less
            for line in bib_content.split('\n')[:10]:
                print(line)
            print("-------------------")
    else:
        print("\nNo bibliography file was created.")
    
    logger.info("ArXiv integration demo completed")

if __name__ == "__main__":
    main()
