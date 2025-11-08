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

# Ingestion utilities: discover and concatenate all files under INPUT/
from typing import List, Optional, Dict, Any
from datetime import datetime

def find_all_input_files(base_dir: Optional[str] = None, input_dir_name: str = 'INPUT', recursive: bool = True, allowed_exts: Optional[List[str]] = None) -> List[str]:
    """
    Return all files in INPUT/ sorted deterministically.

    Args:
        base_dir: Base directory to resolve INPUT from. Defaults to current working directory.
        input_dir_name: The name of the input directory (default 'INPUT').
        recursive: When True, include files from subdirectories.
        allowed_exts: Optional list of extensions (lowercase, with leading dot) to include. If None, include all.

    Returns:
        List of absolute file paths under INPUT.
    """
    base = base_dir or os.getcwd()
    input_dir = os.path.abspath(os.path.join(base, input_dir_name))
    if not os.path.isdir(input_dir):
        return []

    files: List[str] = []
    if recursive:
        for root, _, fnames in os.walk(input_dir):
            for fname in fnames:
                p = os.path.join(root, fname)
                if os.path.isfile(p):
                    if allowed_exts is None or os.path.splitext(fname)[1].lower() in set(allowed_exts):
                        files.append(p)
    else:
        for entry in os.listdir(input_dir):
            p = os.path.join(input_dir, entry)
            if os.path.isfile(p):
                if allowed_exts is None or os.path.splitext(entry)[1].lower() in set(allowed_exts):
                    files.append(p)

    # Stable sort: by relative path from input_dir
    files.sort(key=lambda p: os.path.relpath(p, input_dir).lower())
    return files

def concatenate_inputs(input_paths: List[str], ingestion_cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Read and concatenate multiple files into a single text blob.
    Inserts clear headers to preserve context. Non-readable files are noted and skipped.
    """
    parts: List[str] = []
    for p in input_paths:
        rel_name = os.path.basename(p)
        header = f"\n\n===== FILE: {rel_name} =====\n\n"
        try:
            txt = read_file_content(p) if ingestion_cfg is None else read_file_content(p)
            parts.append(header + txt.strip() + "\n")
        except Exception as e:
            parts.append(f"{header}[ERROR] {e}\n")
    return "".join(parts).strip()

def materialize_concatenation_to_temp(content: str, tmp_dir: Optional[str] = None, filename_prefix: str = "combined_", suffix: str = ".txt") -> str:
    """
    Write concatenated content to a temporary file under INPUT/.combined and return the file path.
    """
    base = os.getcwd()
    tmp_root = tmp_dir or os.path.join(base, "INPUT", ".combined")
    os.makedirs(tmp_root, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(tmp_root, f"{filename_prefix}{ts}{suffix}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path
