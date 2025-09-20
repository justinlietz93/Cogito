#!/usr/bin/env python
"""
Test script for the simplified vector store implementation.

This script demonstrates:
1. Setting up the ArXiv vector store
2. Adding sample papers to the store
3. Performing search queries
4. Retrieving specific papers by ID
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
logger = logging.getLogger("arxiv_vector_demo")

# Ensure proper import paths
sys.path.insert(0, os.path.abspath('.'))
from src.arxiv.vector_store import ArxivVectorStore

# Sample paper data for testing (same as in the Agno test)
SAMPLE_PAPERS = [
    {
        "id": "2109.00558v1",
        "title": "Implementing a Ternary Decomposition of the Toffoli Gate on Fixed-Frequency Transmon Qutrits",
        "summary": "Quantum computing with qutrits (three-level systems) offers advantages in terms of circuit depth and gate count compared to standard qubit-based approaches.",
        "authors": [
            {"name": "Alexey Galda"},
            {"name": "Michael Cubeddu"},
            {"name": "Naoki Kanazawa"},
            {"name": "Prineha Narang"},
            {"name": "Nathan Earnest-Noble"}
        ],
        "published": "2021-09-01T18:01:34Z",
        "categories": ["quant-ph", "cond-mat.mes-hall"]
    },
    {
        "id": "1905.10481v1",
        "title": "Asymptotic Improvements to Quantum Circuits via Qutrits",
        "summary": "We introduce a general technique for using qutrits to reduce the resource requirements of quantum circuits, and show how to use it to optimize Toffoli gates and several other common quantum operations.",
        "authors": [
            {"name": "Pranav Gokhale"},
            {"name": "Jonathan M. Baker"},
            {"name": "Casey Duckering"},
            {"name": "Natalie C. Brown"},
            {"name": "Kenneth R. Brown"},
            {"name": "Frederic T. Chong"}
        ],
        "published": "2019-05-24T23:31:30Z",
        "categories": ["quant-ph"]
    },
    {
        "id": "2301.11375v3",
        "title": "Neural networks learn to magnify areas near decision boundaries",
        "summary": "Deep learning models have shown remarkable classification accuracy, but understanding how they achieve this performance remains challenging. This paper shows neural networks adaptively learn to distribute their resources to focus on difficult-to-classify regions near decision boundaries.",
        "authors": [
            {"name": "Jacob A. Zavatone-Veth"},
            {"name": "Sheng Yang"},
            {"name": "Julian A. Rubinfien"},
            {"name": "Cengiz Pehlevan"}
        ],
        "published": "2023-01-26T19:43:16Z",
        "categories": ["cs.LG", "cs.AI", "cs.NE"]
    },
    {
        "id": "2205.06571v1",
        "title": "Convergence Analysis of Deep Residual Networks",
        "summary": "Deep residual networks (ResNets) have shown remarkable performance in various machine learning tasks. We provide a theoretical analysis of their convergence properties and optimization dynamics.",
        "authors": [
            {"name": "Wentao Huang"},
            {"name": "Haizhang Zhang"}
        ],
        "published": "2022-05-13T11:53:09Z",
        "categories": ["cs.LG", "math.NA"]
    },
    {
        "id": "1710.04073v1",
        "title": "Stream Graphs and Link Streams for the Modeling of Interactions over Time",
        "summary": "Graph theory provides a language for studying the structure of relations between entities. In many cases, though, these relations are not static but evolve over time. We introduce stream graphs and link streams as a formalism for such time-varying networks.",
        "authors": [
            {"name": "Matthieu Latapy"},
            {"name": "Tiphaine Viard"},
            {"name": "Clémence Magnien"}
        ],
        "published": "2017-10-11T14:03:40Z",
        "categories": ["cs.SI", "cs.DM", "physics.soc-ph"]
    }
]

def demo_vector_store():
    """Demonstrate the ArXiv vector store."""
    logger.info("Starting ArXiv vector store demo")
    
    # Initialize the store with a test cache directory
    cache_dir = "storage/vector_demo"
    store = ArxivVectorStore(
        cache_dir=cache_dir,
        table_name="arxiv_demo"
    )
    
    # Clear any existing data for clean demo
    logger.info("Clearing any existing data")
    store.clear()
    
    # Add sample papers
    logger.info(f"Adding {len(SAMPLE_PAPERS)} sample papers to the vector store")
    added_count = store.add_papers(SAMPLE_PAPERS)
    logger.info(f"Added {added_count} papers")
    
    # Get statistics
    stats = store.get_stats()
    logger.info(f"Vector store statistics: {json.dumps(stats, indent=2)}")
    
    # Perform searches across different domains
    search_queries = [
        "quantum computing with qutrits",
        "neural networks decision boundaries",
        "graph theory temporal networks"
    ]
    
    for query in search_queries:
        logger.info(f"\nSearching for: {query}")
        results = store.search(query, max_results=3)
        
        logger.info(f"Found {len(results)} results:")
        for i, paper in enumerate(results, 1):
            logger.info(f"{i}. {paper.get('title', 'Unknown')} (ID: {paper.get('id', 'Unknown')})")
            logger.info(f"   Authors: {', '.join([a.get('name', '') for a in paper.get('authors', [])])}")
            logger.info(f"   Published: {paper.get('published', 'Unknown')}")
            logger.info(f"   Summary: {paper.get('summary', 'No summary')[:100]}...")
    
    # Retrieve a specific paper by ID
    paper_id = "1905.10481v1"
    logger.info(f"\nRetrieving paper by ID: {paper_id}")
    paper = store.get_paper(paper_id)
    
    if paper:
        logger.info(f"Found paper: {paper.get('title')}")
        logger.info(f"Authors: {', '.join([a.get('name', '') for a in paper.get('authors', [])])}")
        logger.info(f"Published: {paper.get('published')}")
        logger.info(f"Summary: {paper.get('summary')}")
    else:
        logger.info(f"Paper not found: {paper_id}")
    
    logger.info("\nDemo completed")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='ArXiv Vector Store Demo')
    
    args = parser.parse_args()
    
    # Run the demo
    demo_vector_store()

if __name__ == "__main__":
    main()
