#!/usr/bin/env python3
"""
Test script to verify the LaTeX generation from peer review files.

This script tests the changes to the LaTeX formatting system that allow
it to properly use peer review files as the source for LaTeX generation.
"""

import os
import logging
import argparse
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add repository root to path
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.latex.formatter import format_as_latex

def test_peer_review_latex_generation():
    """
    Test LaTeX generation using peer review files as the source.
    """
    logger.info("Testing LaTeX generation from peer review files")
    
    # Find the most recent peer review file
    critiques_dir = Path("critiques")
    peer_review_files = list(critiques_dir.glob("content_peer_review_*.md"))
    
    if not peer_review_files:
        logger.error("No peer review files found in 'critiques' directory")
        return False
    
    # Sort by modification time to get the most recent
    peer_review_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    peer_review_file = peer_review_files[0]
    
    # Find the corresponding critique report
    critique_file_name = peer_review_file.name.replace("peer_review", "critique")
    critique_file = critiques_dir / critique_file_name
    
    if not critique_file.exists():
        logger.error(f"Corresponding critique file not found: {critique_file}")
        return False
    
    logger.info(f"Using peer review file: {peer_review_file}")
    logger.info(f"Using critique file: {critique_file}")
    
    # Read content files
    with open("content.txt", "r", encoding="utf-8") as f:
        original_content = f.read()
    
    with open(critique_file, "r", encoding="utf-8") as f:
        critique_content = f.read()
    
    with open(peer_review_file, "r", encoding="utf-8") as f:
        peer_review_content = f.read()
    
    # Configure LaTeX settings
    latex_config = {
        'output_dir': 'latex_output',
        'compile_pdf': True,
        'scientific_mode': True,
        'scientific_objectivity_level': 'high',
        'output_filename': 'peer_review_report'
    }
    
    # Generate LaTeX
    try:
        tex_path, pdf_path = format_as_latex(
            original_content,
            critique_content,
            peer_review_content,
            latex_config
        )
        
        if tex_path and pdf_path:
            logger.info(f"Successfully generated LaTeX document: {tex_path}")
            logger.info(f"Successfully generated PDF document: {pdf_path}")
            return True
        else:
            logger.error("LaTeX generation failed to produce output files")
            return False
    except Exception as e:
        logger.error(f"LaTeX generation failed with error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test LaTeX generation from peer review files')
    args = parser.parse_args()
    
    success = test_peer_review_latex_generation()
    
    if success:
        print("\nSUCCESS: Peer review LaTeX generation test completed successfully")
        sys.exit(0)
    else:
        print("\nFAILURE: Peer review LaTeX generation test failed")
        sys.exit(1)
