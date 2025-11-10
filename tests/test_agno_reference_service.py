#!/usr/bin/env python
"""
Test script for the Agno-powered ArXiv reference service.

This script demonstrates:
1. Setting up the Agno-powered ArXiv reference service
2. Retrieving references for content points
3. Updating bibliography files
4. Comparing performance with the SQLite-based implementation
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, List, Any, Tuple
from datetime import datetime

if "pytest" in sys.modules:
    import pytest

    pytest.importorskip("agno", reason="Agno optional dependency is not installed.")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("arxiv_agno_service_demo")

# Ensure proper import paths
sys.path.insert(0, os.path.abspath('.'))
from src.arxiv.arxiv_agno_service import ArxivAgnoReferenceService
from src.arxiv.arxiv_reference_service import ArxivReferenceService

# Sample content points
SAMPLE_POINTS = [
    "Quantum computing uses quantum bits or qubits instead of classical bits.",
    "Qubits can exist in multiple states simultaneously due to quantum superposition.",
    "Neural networks are a form of machine learning used for tasks like image recognition.",
    "Deep learning involves neural networks with many layers.",
    "Graph theory studies mathematical structures used to model relations between objects."
]

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    config_path = 'config.json'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.warning(f"Failed to load config from {config_path}: {e}")
        # Return default config
        return {
            'arxiv': {
                'cache_dir': 'storage/arxiv_cache',
                'use_db_cache': True,
                'use_cache': True,
                'cache_ttl_days': 30,
                'max_references_per_point': 3,
                'default_sort_by': 'relevance',
                'default_sort_order': 'descending',
                'update_bibliography': True,
            }
        }

def demo_agno_reference_service(config: Dict[str, Any], openai_api_key: str = None):
    """
    Demonstrate the Agno-powered ArXiv reference service.
    
    Args:
        config: Configuration dictionary
        openai_api_key: OpenAI API key (optional)
    """
    logger.info("Starting Agno-powered ArXiv reference service demo")
    
    # Set up Agno reference service
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key
    
    # Initialize service
    agno_service = ArxivAgnoReferenceService(config=config)
    
    # Clear cache for clean demo
    agno_service.clear_cache()
    
    # Process sample points
    logger.info(f"Processing {len(SAMPLE_POINTS)} sample points")
    all_references = []
    
    # Measure performance
    start_time = time.time()
    
    # Get references for each point
    for i, point in enumerate(SAMPLE_POINTS, 1):
        logger.info(f"\nProcessing point {i}: {point}")
        
        # Get references
        references = agno_service.get_references_for_point(point)
        
        # Log results
        logger.info(f"Found {len(references)} references:")
        for j, ref in enumerate(references, 1):
            logger.info(f"  {j}. {ref.get('title', 'Unknown')}")
            logger.info(f"     Authors: {', '.join([a.get('name', '') for a in ref.get('authors', [])])}")
            logger.info(f"     Published: {ref.get('published', 'Unknown')}")
            
            # Add to all references
            all_references.append(ref)
    
    # Calculate time elapsed
    elapsed_time = time.time() - start_time
    logger.info(f"\nProcessing completed in {elapsed_time:.2f} seconds")
    
    # Update bibliography
    output_path = "latex_output/agno_demo_bibliography.bib"
    agno_service.update_bibliography_file(all_references, output_path)
    logger.info(f"Bibliography updated at {output_path}")
    
    # Get cache statistics
    cache_stats = agno_service.get_cache_stats()
    if cache_stats:
        logger.info(f"Cache statistics: {cache_stats}")
    
    logger.info("Agno-powered demo completed")
    
    return elapsed_time, len(all_references)

def demo_sqlite_reference_service(config: Dict[str, Any]):
    """
    Demonstrate the SQLite-based ArXiv reference service for comparison.
    
    Args:
        config: Configuration dictionary
    """
    logger.info("\nStarting SQLite-based ArXiv reference service demo")
    
    # Initialize service
    sqlite_service = ArxivReferenceService(config=config)
    
    # Clear cache for clean demo
    try:
        sqlite_service.clear_cache()
    except Exception as e:
        logger.warning(f"Failed to clear SQLite cache: {e}")
    
    # Process sample points
    logger.info(f"Processing {len(SAMPLE_POINTS)} sample points")
    all_references = []
    
    # Measure performance
    start_time = time.time()
    
    # Process all points
    point_refs = sqlite_service.attach_references_to_points(SAMPLE_POINTS)
    
    # Log results
    for i, (point, references) in enumerate(point_refs, 1):
        logger.info(f"\nProcessing point {i}: {point}")
        logger.info(f"Found {len(references)} references:")
        
        for j, ref in enumerate(references, 1):
            logger.info(f"  {j}. {ref.get('title', 'Unknown')}")
            
            # Add to all references
            all_references.append(ref)
    
    # Calculate time elapsed
    elapsed_time = time.time() - start_time
    logger.info(f"\nProcessing completed in {elapsed_time:.2f} seconds")
    
    # Update bibliography
    output_path = "latex_output/sqlite_demo_bibliography.bib"
    sqlite_service.update_bibliography_file(all_references, output_path)
    logger.info(f"Bibliography updated at {output_path}")
    
    # Get cache statistics
    try:
        cache_stats = sqlite_service.get_cache_stats()
        if cache_stats:
            logger.info(f"Cache statistics: {cache_stats}")
    except Exception as e:
        logger.warning(f"Failed to get SQLite cache stats: {e}")
    
    logger.info("SQLite-based demo completed")
    
    return elapsed_time, len(all_references)

def run_performance_comparison(config: Dict[str, Any], openai_api_key: str = None):
    """
    Run performance comparison between Agno and SQLite implementations.
    
    Args:
        config: Configuration dictionary
        openai_api_key: OpenAI API key (optional)
    """
    logger.info("\n======== PERFORMANCE COMPARISON ========")
    
    # Run SQLite demo
    sqlite_time, sqlite_refs = demo_sqlite_reference_service(config)
    
    # Run Agno demo
    agno_time, agno_refs = demo_agno_reference_service(config, openai_api_key)
    
    # Compare results
    logger.info("\n======== COMPARISON RESULTS ========")
    logger.info(f"SQLite implementation: {sqlite_time:.2f} seconds, {sqlite_refs} references")
    logger.info(f"Agno implementation: {agno_time:.2f} seconds, {agno_refs} references")
    
    # Calculate speedup on second run (when cached)
    logger.info("\n======== SECOND RUN (CACHED) ========")
    
    # Run SQLite demo again (should use cache)
    sqlite_time2, _ = demo_sqlite_reference_service(config)
    
    # Run Agno demo again (should use cache)
    agno_time2, _ = demo_agno_reference_service(config, openai_api_key)
    
    # Compare cached results
    logger.info("\n======== CACHED COMPARISON RESULTS ========")
    logger.info(f"SQLite implementation (cached): {sqlite_time2:.2f} seconds")
    logger.info(f"Agno implementation (cached): {agno_time2:.2f} seconds")
    logger.info(f"Speedup: {sqlite_time2 / max(0.001, agno_time2):.2f}x")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='ArXiv Agno Reference Service Demo')
    parser.add_argument('--openai-api-key', help='OpenAI API key for embeddings')
    parser.add_argument('--compare', action='store_true', help='Run performance comparison')
    
    args = parser.parse_args()
    
    # Get the API key from args or environment
    openai_api_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("No OpenAI API key provided. Will look for OPENAI_API_KEY in environment.")
    
    # Load configuration
    config = load_config()
    
    # Run demo
    if args.compare:
        run_performance_comparison(config, openai_api_key)
    else:
        demo_agno_reference_service(config, openai_api_key)

if __name__ == "__main__":
    main()
