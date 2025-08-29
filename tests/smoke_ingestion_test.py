#!/usr/bin/env python3
"""
Smoke test for ingestion discovery and batch concatenation.

- Does NOT call any external model API.
- Does NOT require OCR/PDF/Whisper dependencies.
- Exercises INPUT/ directory discovery, ordering, concatenation, and temp materialization.

Run (from repo root):
  python Cogito/tests/smoke_ingestion_test.py
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

# Ensure the Cogito/ directory is on sys.path so "src" package is importable
THIS_DIR = Path(__file__).resolve().parent
COGITO_DIR = THIS_DIR.parent
if str(COGITO_DIR) not in sys.path:
    sys.path.insert(0, str(COGITO_DIR))

# Import ingestion helpers from the app
from src.input_reader import (  # type: ignore
    find_default_input_file,
    find_all_input_files,
    read_file_content,
    concatenate_inputs,
    materialize_concatenation_to_temp,
)


def main():
    print("=== Ingestion Smoke Test ===")

    # Create a temporary INPUT-like directory structure
    tmp_root = tempfile.mkdtemp(prefix="cogito_ingest_smoke_")
    input_dir = Path(tmp_root) / "INPUT"
    input_dir.mkdir(parents=True, exist_ok=True)
    print(f"[info] Created temp INPUT dir: {input_dir}")

    # Write a couple of small text files (cover preferred filenames and ordering)
    files = [
        ("prompt.txt", "This is the prompt file."),
        ("content.txt", "This is the main content file."),
        ("notes.md", "# Some Notes\nA few lines for testing ordering."),
    ]

    for name, text in files:
        (input_dir / name).write_text(text, encoding="utf-8")
    print(f"[info] Wrote {len(files)} text files")

    # 1) Default file discovery
    default_path = find_default_input_file(base_dir=str(tmp_root), input_dir_name="INPUT")
    print(f"[discovery] default: {default_path}")

    # 2) List all files (ordered) and show
    all_paths = find_all_input_files(base_dir=str(tmp_root), input_dir_name="INPUT")
    print("[discovery] all files (ordered):")
    for p in all_paths:
        print(f"  - {p}")

    # 3) Read the discovered default file to ensure basic read works
    if default_path:
        default_text = read_file_content(default_path)
        print(f"[read] default file preview: {default_text[:60]!r}")

    # 4) Concatenate all files and materialize into a temp file
    combined = concatenate_inputs(all_paths)
    temp_combined_path = materialize_concatenation_to_temp(combined, suffix=".txt")
    print(f"[concat] combined length: {len(combined)} chars")
    print(f"[concat] materialized to: {temp_combined_path}")

    # Preview first few lines of the combined file
    preview = Path(temp_combined_path).read_text(encoding="utf-8")
    print(f"[concat] preview:\n{preview[:200]}")

    # Cleanup temp root (keep materialized file so devs can inspect if desired)
    try:
        shutil.rmtree(tmp_root, ignore_errors=True)
        print(f"[cleanup] removed temp dir: {tmp_root} (kept materialized file)")
    except Exception as e:
        print(f"[warn] failed to cleanup temp dir {tmp_root}: {e}")

    print("=== OK ===")


if __name__ == "__main__":
    main()