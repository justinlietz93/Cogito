#!/usr/bin/env python
"""
Test script for LaTeX configuration and MiKTeX detection.

This script tests the LaTeX configuration system and verifies that
the LaTeX compiler can find and use the LaTeX installation.
"""

import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the current directory to the path
sys.path.insert(0, os.path.abspath('.'))

# Import our modules
from src.config_loader import config_loader
from src.latex.utils.latex_compiler import LatexCompiler

def main():
    print("LaTeX Configuration Test")
    print("======================")

    # Load the LaTeX configuration
    print("\n1. Loading LaTeX configuration from YAML:")
    latex_config = config_loader.get_latex_config()
    print(f"  - LaTeX engine: {latex_config.get('latex_engine')}")
    print(f"  - Compile PDF: {latex_config.get('compile_pdf')}")
    print(f"  - BibTeX run: {latex_config.get('bibtex_run')}")
    print(f"  - LaTeX runs: {latex_config.get('latex_runs')}")
    
    # Get MiKTeX configuration
    miktex_config = latex_config.get('miktex', {})
    print(f"  - Custom MiKTeX path: {miktex_config.get('custom_path', 'Not specified')}")
    additional_paths = miktex_config.get('additional_search_paths', [])
    print(f"  - Additional search paths: {len(additional_paths)} paths configured")
    
    # Initialize the LaTeX compiler
    print("\n2. Initializing LaTeX compiler and searching for LaTeX:")
    compiler = LatexCompiler(latex_config)
    
    # Check if LaTeX is available
    print(f"\n3. LaTeX availability:")
    print(f"  - LaTeX available: {compiler.latex_available}")
    print(f"  - LaTeX engine used: {compiler.latex_engine}")
    
    # If an engine path was found, print it
    engine_path = getattr(compiler, '_engine_path', None)
    if engine_path:
        print(f"  - Full engine path: {engine_path}")
        print(f"  - Engine directory: {os.path.dirname(engine_path)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    main()
