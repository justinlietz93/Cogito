#!/usr/bin/env python3
"""Research query execution CLI for Cogito.

This script provides command-line access to research query execution across
multiple databases (PubMed, Semantic Scholar, CrossRef) and web search.
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.presentation.cli.research_cli import main

if __name__ == '__main__':
    sys.exit(main())
