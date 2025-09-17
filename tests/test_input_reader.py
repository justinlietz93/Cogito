# tests/test_input_reader.py

import pytest
import os
import sys

# Adjust path to import from the new src directory
# Assumes tests are run from the 'critique_council' directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.input_reader import read_file_content

# Define paths relative to the 'critique_council/tests' directory
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
EXISTING_FILE = os.path.join(TEST_DATA_DIR, 'sample_input.txt')
NON_EXISTENT_FILE = os.path.join(TEST_DATA_DIR, 'does_not_exist.txt')
NOT_A_FILE = TEST_DATA_DIR # Directory path
INVALID_UTF8_FILE = os.path.join(TEST_DATA_DIR, 'invalid_utf8.bin')

# Create dummy test data directory and file before tests run
@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    """Creates necessary directories and files for testing."""
    print("\nSetting up test data...")
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    sample_content = "This is sample content.\nLine two."
    with open(EXISTING_FILE, 'w', encoding='utf-8') as f:
        f.write(sample_content)
    print(f"Created {EXISTING_FILE}")

    with open(INVALID_UTF8_FILE, 'wb') as f:
        f.write(b"\xff\xfe\xfa\xfa")
    print(f"Created {INVALID_UTF8_FILE}")

    yield # Let tests run

    # Teardown: Remove created files/dirs after tests
    print("\nTearing down test data...")
    if os.path.exists(EXISTING_FILE):
        os.remove(EXISTING_FILE)
        print(f"Removed {EXISTING_FILE}")
    if os.path.exists(INVALID_UTF8_FILE):
        os.remove(INVALID_UTF8_FILE)
        print(f"Removed {INVALID_UTF8_FILE}")
    if os.path.exists(TEST_DATA_DIR):
        # Only remove if empty, handle potential race conditions if needed
        try:
            # Check if directory is empty before removing
            if not os.listdir(TEST_DATA_DIR):
                 os.rmdir(TEST_DATA_DIR)
                 print(f"Removed {TEST_DATA_DIR}")
            else:
                 print(f"Directory {TEST_DATA_DIR} not empty, skipping removal.")
        except OSError as e:
             print(f"Error removing directory {TEST_DATA_DIR}: {e}")


def test_read_existing_file():
    """Tests reading content from an existing UTF-8 file."""
    expected_content = "This is sample content.\nLine two."
    actual_content = read_file_content(EXISTING_FILE)
    assert actual_content == expected_content

def test_read_non_existent_file():
    """Tests that FileNotFoundError is raised for a non-existent file."""
    with pytest.raises(FileNotFoundError, match="Input file not found"):
        read_file_content(NON_EXISTENT_FILE)

def test_read_directory_path():
    """Tests that FileNotFoundError is raised when path is a directory."""
    with pytest.raises(FileNotFoundError, match="Input path is not a file"):
        read_file_content(NOT_A_FILE)


def test_read_non_utf8_file():
    """Tests that UnicodeDecodeError is raised with helpful context."""
    with pytest.raises(UnicodeDecodeError) as exc_info:
        read_file_content(INVALID_UTF8_FILE)

    message = str(exc_info.value)
    assert "while decoding" in message
    assert INVALID_UTF8_FILE in message

# Note: Testing UnicodeDecodeError requires creating a non-UTF8 file,
# which can be platform-dependent or tricky. Mocking open() might be
# a more robust approach for this specific error case in more complex scenarios.
