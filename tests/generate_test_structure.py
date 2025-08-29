#!/usr/bin/env python
"""
Script to generate an organized test structure for the Critique Council project.

This script creates a hierarchical test directory structure that mirrors the
source code organization, while preserving any existing test files.
"""

import os
import shutil

def create_directory(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")
    else:
        print(f"Directory already exists: {path}")

def create_file(path, content=""):
    """Create file with content if it doesn't exist."""
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created file: {path}")
    else:
        print(f"File already exists: {path}")

def empty_init_py():
    """Return content for an empty __init__.py file."""
    return '# This file is part of the test suite for the Critique Council project.\n'

def fixture_init_py(fixture_type):
    """Return content for a fixtures __init__.py file."""
    return f'''"""
Test fixtures for {fixture_type}.

This module contains test fixtures used for {fixture_type} tests.
"""
'''

def test_file_template(module_name, imports=None, classes=None):
    """Return content for a test file template."""
    if imports is None:
        imports = []
    
    if classes is None:
        classes = []
    
    header = f'''"""
Unit tests for {module_name}.

This module contains tests for the {module_name} functionality.
"""

import unittest
import pytest
'''

    import_section = '\n'.join(imports) + '\n\n' if imports else '\n'
    
    class_sections = []
    for cls in classes:
        class_sections.append(f'''
class Test{cls}(unittest.TestCase):
    """Tests for the {cls} class."""
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def tearDown(self):
        """Tear down test fixtures."""
        pass
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        # TODO: Implement test
        pass
''')
    
    class_content = '\n'.join(class_sections)
    
    footer = '''
if __name__ == '__main__':
    unittest.main()
'''
    
    return header + import_section + class_content + footer

def generate_test_structure():
    """Generate the test directory structure."""
    # Base test directory
    base_dir = "tests"
    create_directory(base_dir)
    
    # Providers tests
    providers_dir = os.path.join(base_dir, "providers")
    create_directory(providers_dir)
    create_file(os.path.join(providers_dir, "__init__.py"), empty_init_py())
    
    # Provider fixtures
    providers_fixtures_dir = os.path.join(providers_dir, "fixtures")
    create_directory(providers_fixtures_dir)
    create_file(os.path.join(providers_fixtures_dir, "__init__.py"), 
                fixture_init_py("API provider responses"))
    
    create_file(os.path.join(providers_fixtures_dir, "openai_responses.py"), 
'''"""
Mock OpenAI API responses for testing.

This module contains mock responses for the OpenAI API for use in tests.
"""

# General successful response
SUCCESSFUL_RESPONSE = {
    "points": [
        {"id": "point-1", "point": "First test point"},
        {"id": "point-2", "point": "Second test point"}
    ]
}

# Incomplete JSON response (missing closing braces/brackets)
INCOMPLETE_JSON_RESPONSE = """
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
"""

# Malformed JSON response
MALFORMED_JSON_RESPONSE = """
{
  "points": [
    {
      "id": "point-1",
      "point": "First point"
    },
    {
      "id": "point-2"
      "point": "Second point with syntax error - missing comma"
    }
  ]
}
"""

# Non-JSON text response
TEXT_RESPONSE = """
Here are some points:
1. First point from text
2. Second point from text
3. Third point from text
"""

# Empty response
EMPTY_RESPONSE = ""
''')
    
    create_file(os.path.join(providers_fixtures_dir, "o3_mini_responses.py"),
'''"""
Mock o3-mini API responses for testing.

This module contains specific mock responses for the o3-mini model for use in tests.
"""

# Successful o3-mini response
O3_MINI_SUCCESS = {
    "output": [
        {"role": "assistant", "content": [{"text": """
{
  "points": [
    {
      "id": "point-1",
      "point": "First point from o3-mini"
    },
    {
      "id": "point-2",
      "point": "Second point from o3-mini"
    }
  ]
}
"""}]}
    ]
}

# Truncated o3-mini response (seen in logs)
O3_MINI_TRUNCATED = {
    "output": [
        {"role": "assistant", "content": [{"text": """
{
  "points": [
    {
      "id": "point-1",
      "point": "First point from o3-mini"
    },
    {
"""}]}
    ]
}

# Non-JSON o3-mini response
O3_MINI_NON_JSON = {
    "output": [
        {"role": "assistant", "content": [{"text": """
I've analyzed the content and extracted the following key points:

1. First point from o3-mini
2. Second point from o3-mini
3. Third point from o3-mini
"""}]}
    ]
}
''')
    
    # Provider test files
    create_file(os.path.join(providers_dir, "test_openai_client.py"),
                test_file_template("OpenAI client",
                                  imports=["from src.providers import openai_client",
                                           "from src.providers.exceptions import JsonParsingError",
                                           "from tests.providers.fixtures.openai_responses import *"],
                                  classes=["OpenAIClient", "JSONParsing", "ErrorHandling", "RetryLogic"]))
    
    create_file(os.path.join(providers_dir, "test_o3_mini_integration.py"),
                test_file_template("o3-mini integration",
                                  imports=["from src.providers import openai_client",
                                           "from tests.providers.fixtures.o3_mini_responses import *"],
                                  classes=["O3MiniResponseHandling", "O3MiniJSONParsing", "O3MiniErrorHandling"]))
    
    # Content tests
    content_dir = os.path.join(base_dir, "content")
    create_directory(content_dir)
    create_file(os.path.join(content_dir, "__init__.py"), empty_init_py())
    
    # Content fixtures
    content_fixtures_dir = os.path.join(content_dir, "fixtures")
    create_directory(content_fixtures_dir)
    create_file(os.path.join(content_fixtures_dir, "__init__.py"), 
                fixture_init_py("content samples"))
    
    # Sample content files
    create_file(os.path.join(content_fixtures_dir, "valid_content.txt"),
"""This is a sample valid content file for testing.

It contains multiple paragraphs with distinct points that can be extracted:

First, this document discusses the importance of testing.
Second, it emphasizes the need for robust error handling.
Third, it mentions the value of well-organized test structures.

These points should be extractable by the content assessor.
""")
    
    create_file(os.path.join(content_fixtures_dir, "edge_cases.txt"),
"""# Edge Case Document

- Very short point
- Point with special characters: λ, π, Σ, Ω
- Point with *formatting* and **emphasis**
- Point with code: `print("hello world")`
- Point with a formula: E=mc^2
- Point with a very long description that exceeds the normal expected length of a typical point and might cause issues with processing or display in certain contexts where space is limited or where there are constraints on how text is parsed or rendered by the system
- 
- Empty point above
""")
    
    # Content test files
    create_file(os.path.join(content_dir, "test_content_assessor.py"),
                test_file_template("content assessor",
                                  imports=["import os", 
                                           "from src.content_assessor import ContentAssessor",
                                           "from unittest.mock import patch, MagicMock"],
                                  classes=["ContentAssessor", "PointExtraction", "ErrorHandling"]))
    
    create_file(os.path.join(content_dir, "test_point_extraction.py"),
                test_file_template("point extraction",
                                  imports=["import os", 
                                           "from src.content_assessor import ContentAssessor",
                                           "from unittest.mock import patch, MagicMock"],
                                  classes=["TextExtraction", "JSONParsing", "FallbackGeneration"]))
    
    # Integration tests
    integration_dir = os.path.join(base_dir, "integration")
    create_directory(integration_dir)
    create_file(os.path.join(integration_dir, "__init__.py"), empty_init_py())
    
    create_file(os.path.join(integration_dir, "test_critique_pipeline.py"),
                test_file_template("critique pipeline",
                                  imports=["import os", 
                                           "from src.main import critique_goal_document",
                                           "from unittest.mock import patch, MagicMock"],
                                  classes=["FullPipeline", "ContentToLatex", "ErrorPropagation"]))
    
    print("\nTest structure generation complete!")
    print("Remember to check and adapt the generated files as needed.")

if __name__ == "__main__":
    generate_test_structure()
