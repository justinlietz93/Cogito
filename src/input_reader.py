# src/critique_module/input_reader.py

"""
Component responsible for reading input file content.
"""

import os

def read_file_content(file_path: str) -> str:
    """
    Reads and returns the content of a text file.

    Args:
        file_path: The absolute or relative path to the input text file.

    Returns:
        The content of the file as a string.

    Raises:
        FileNotFoundError: If the file_path does not exist or is not a file.
        IOError: If there is an error reading the file.
        UnicodeDecodeError: If the file is not valid UTF-8 text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at path: {file_path}")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Input path is not a file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError as err:
        encoding = err.encoding or "utf-8"
        # Reconstruct the UnicodeDecodeError with the original context so callers
        # receive the expected exception type without triggering constructor
        # validation errors.
        raise UnicodeDecodeError(
            encoding,
            err.object,
            err.start,
            err.end,
            f"{err.reason} (while decoding {file_path})",
        ) from err
    except IOError as e:
        # Catching broader IOError after specific decode error
        raise IOError(f"Could not read file {file_path}: {e}")
    except Exception as e:
        # Catch any other unexpected exceptions during file reading
        raise Exception(f"An unexpected error occurred while reading {file_path}: {e}")
