#!/usr/bin/env python
"""
Test script for verifying the fixes for LaTeX configuration and point extraction.

This script tests:
1. The LaTeX configuration with the new miktex section
2. The improved error handling in content extraction
"""

import os
import sys
import logging
import json
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the current directory to the path
sys.path.insert(0, os.path.abspath('.'))

# Test functions
def test_latex_config():
    """Test the LaTeX configuration with the miktex section."""
    from src.latex.config import LatexConfig
    
    print("\n=== Testing LaTeX Configuration ===")
    
    # Test with miktex configuration
    test_config = {
        "compile_pdf": True,
        "miktex": {
            "custom_path": "C:/Program Files/MiKTeX 25.3/miktex/bin/x64",
            "additional_search_paths": ["C:/Custom/Path"]
        }
    }
    
    try:
        config = LatexConfig(test_config)
        miktex_config = config.get('miktex')
        
        if miktex_config and isinstance(miktex_config, dict):
            print(f"✅ PASS: miktex configuration accepted correctly")
            print(f"  - Custom path: {miktex_config.get('custom_path')}")
            print(f"  - Additional paths: {miktex_config.get('additional_search_paths')}")
        else:
            print(f"❌ FAIL: miktex configuration not properly processed")
        
    except ValueError as e:
        print(f"❌ FAIL: Configuration error: {e}")
    except Exception as e:
        print(f"❌ FAIL: Unexpected error: {e}")

def test_content_extraction():
    """Test the improved error handling in content extraction."""
    from src.content_assessor import ContentAssessor
    
    print("\n=== Testing Content Extraction ===")
    
    # Create a mock incomplete JSON string
    incomplete_json = '''
    {
      "points": [
        {
          "id": "point-1",
          "point": "First point"
        },
        {
          "id": "point-2",
          "point": "Second point"
        }
      ]
    '''
    
    # Create a mock text with points but not proper JSON
    text_with_points = '''
    1. First point from text
    2. Second point from text
    3. Third point from text
    '''
    
    assessor = ContentAssessor()
    assessor.set_logger(logger)
    
    # Test JSON repair
    try:
        repaired = assessor._repair_and_parse_json(incomplete_json)
        if repaired and isinstance(repaired, dict) and "points" in repaired:
            print(f"✅ PASS: Successfully repaired broken JSON")
            print(f"  - Extracted {len(repaired['points'])} points")
        else:
            print(f"❌ FAIL: Could not repair JSON")
    except Exception as e:
        print(f"❌ FAIL: JSON repair error: {e}")
    
    # Test text extraction
    try:
        points = assessor._extract_points_from_text(text_with_points)
        if points and len(points) > 0:
            print(f"✅ PASS: Successfully extracted points from text")
            print(f"  - Extracted {len(points)} points")
            for i, point in enumerate(points[:3]):
                print(f"  - Point {i+1}: {point.get('point', '')[:30]}...")
        else:
            print(f"❌ FAIL: Could not extract points from text")
    except Exception as e:
        print(f"❌ FAIL: Text extraction error: {e}")
    
    # Test fallback point generation
    try:
        result = "Some non-JSON, non-structured content"
        points = assessor._validate_and_format_points(result)
        
        if points and len(points) > 0:
            print(f"✅ PASS: Successfully created fallback points")
            print(f"  - Generated {len(points)} fallback point(s)")
        else:
            print(f"❌ FAIL: Did not create fallback points")
    except Exception as e:
        print(f"❌ FAIL: Fallback generation error: {e}")

def main():
    """Run all tests."""
    print("Running tests for LaTeX configuration and content extraction fixes")
    
    test_latex_config()
    test_content_extraction()
    
    print("\nTests completed.")

if __name__ == "__main__":
    main()
