# src/critique_module/input_reader.py

"""
Component responsible for discovering and reading input content from the INPUT/ folder.
Supports:
- Text files by default
- PDFs via multiple backends (PyMuPDF, pdfminer.six, PyPDF2)
- Images via OCR (pytesseract)
- Audio via Whisper (local) or OpenAI Whisper API

Batch mode: concatenate multiple files from INPUT/ in a stable order.
Backends and toggles are configurable via config.yaml under 'ingestion'.
"""

import os
import tempfile
from typing import List, Optional, Tuple, Dict, Any

try:
    # Optional import of unified configuration
    from src.config_loader import config_loader
except Exception:
    config_loader = None

# --- Default preferences used for discovery/sorting ---

PREFERRED_NAMES = [
    'content.txt',
    'input.txt',
    'prompt.txt',
    'user_prompt.txt',
]

# Discovery order for extensions (earlier has higher priority)
PREFERRED_EXT_ORDER = [
    '.txt', '.md', '.markdown', '.json', '.yaml', '.yml',
    '.pdf',
    '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp',
    '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.webm',
]

TEXT_EXTS = {'.txt', '.md', '.markdown', '.json', '.yaml', '.yml'}
PDF_EXTS = {'.pdf'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp'}
AUDIO_EXTS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.webm'}

# --- Helpers to get config ---

def _get_ingestion_config(override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if override is not None:
        return override
    if config_loader:
        return config_loader.get_section('ingestion') or {}
    return {}

# --- Core Readers: Text / PDF backends / OCR / Audio ---

def _read_text_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def _read_pdf_pymupdf(path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except Exception:
        raise RuntimeError("PyMuPDF not installed. Install with: pip install PyMuPDF")
    try:
        doc = fitz.open(path)
        parts: List[str] = []
        for page in doc:
            parts.append(page.get_text("text") or "")
        return "\n".join(parts).strip()
    except Exception as e:
        raise RuntimeError(f"PyMuPDF failed to extract text from '{path}': {e}")

def _read_pdf_pdfminer(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        raise RuntimeError("pdfminer.six not installed. Install with: pip install pdfminer.six")
    try:
        return (extract_text(path) or "").strip()
    except Exception as e:
        raise RuntimeError(f"pdfminer.six failed to extract text from '{path}': {e}")

def _read_pdf_pypdf2(path: str) -> str:
    try:
        import PyPDF2  # type: ignore
    except Exception:
        raise RuntimeError("PyPDF2 not installed. Install with: pip install PyPDF2")
    try:
        text_parts: List[str] = []
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts).strip()
    except Exception as e:
        raise RuntimeError(f"PyPDF2 failed to extract text from '{path}': {e}")

def _read_pdf_file(path: str, backend: str = "auto") -> str:
    backend = (backend or "auto").lower()
    if backend == "pymupdf":
        return _read_pdf_pymupdf(path)
    if backend == "pdfminer":
        return _read_pdf_pdfminer(path)
    if backend == "pypdf2":
        return _read_pdf_pypdf2(path)
    # auto detect: prefer PyMuPDF → pdfminer → PyPDF2
    for fn in (_read_pdf_pymupdf, _read_pdf_pdfminer, _read_pdf_pypdf2):
        try:
            return fn(path)
        except Exception:
            continue
    raise RuntimeError("No working PDF backend available. Install one of: PyMuPDF, pdfminer.six, PyPDF2")

def _read_image_ocr(path: str, ocr_cfg: Dict[str, Any]) -> str:
    if not ocr_cfg.get("enabled", False):
        raise RuntimeError("OCR disabled by configuration")
    try:
        from PIL import Image
        import pytesseract
    except Exception:
        raise RuntimeError("OCR requires Pillow and pytesseract. Install with: pip install pillow pytesseract")
    tcmd = ocr_cfg.get("tesseract_cmd") or ""
    if tcmd:
        import pytesseract as _pt
        _pt.pytesseract.tesseract_cmd = tcmd
    lang = ocr_cfg.get("languages", "eng")
    try:
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang=lang) or ""
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"OCR failed for image '{path}': {e}")

def _read_audio_whisper_local(path: str, model_name: str = "base") -> str:
    try:
        import whisper  # openai-whisper
    except Exception:
        raise RuntimeError("Local Whisper requires openai-whisper. Install with: pip install openai-whisper")
    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(path)
        return (result.get("text") or "").strip()
    except Exception as e:
        raise RuntimeError(f"Local Whisper failed for '{path}': {e}")

def _read_audio_whisper_openai(path: str) -> str:
    try:
        from openai import OpenAI
    except Exception:
        raise RuntimeError("OpenAI Whisper backend requires openai>=1.0.0. Install with: pip install openai")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set for OpenAI Whisper backend")
    try:
        client = OpenAI(api_key=api_key)
        # Use current audio transcription endpoint
        with open(path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        # Support both dict-like and object-like returns
        text = getattr(transcription, "text", None)
        if text is None and isinstance(transcription, dict):
            text = transcription.get("text")
        return (text or "").strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI Whisper transcription failed for '{path}': {e}")

def _read_audio_file(path: str, audio_cfg: Dict[str, Any]) -> str:
    if not audio_cfg.get("enabled", False):
        raise RuntimeError("Audio transcription disabled by configuration")
    backend = (audio_cfg.get("backend") or "whisper_local").lower()
    if backend == "whisper_local":
        model = audio_cfg.get("whisper_model", "base")
        return _read_audio_whisper_local(path, model_name=model)
    if backend == "whisper_openai":
        return _read_audio_whisper_openai(path)
    raise RuntimeError(f"Unknown audio backend: {backend}")

# --- Public: Read a single file according to config/backends ---

def read_file_content(file_path: str, ingestion_cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Read and return textual content from a supported file type.

    Supported:
      - Text: .txt, .md, .markdown, .json, .yaml, .yml
      - PDF:  via backends (pymupdf, pdfminer, pypdf2)
      - Image: OCR via pytesseract
      - Audio: Whisper (local or OpenAI)

    Raises:
      FileNotFoundError, IOError, UnicodeDecodeError, RuntimeError
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at path: {file_path}")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Input path is not a file: {file_path}")

    cfg = _get_ingestion_config(ingestion_cfg)
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in TEXT_EXTS:
            return _read_text_file(file_path)
        if ext in PDF_EXTS:
            pdf_cfg = (cfg.get('pdf') or {})
            backend = pdf_cfg.get('backend', 'auto')
            return _read_pdf_file(file_path, backend=backend)
        if ext in IMAGE_EXTS:
            ocr_cfg = (cfg.get('ocr') or {})
            return _read_image_ocr(file_path, ocr_cfg)
        if ext in AUDIO_EXTS:
            audio_cfg = (cfg.get('audio') or {})
            return _read_audio_file(file_path, audio_cfg)
        # Default: try reading as text
        return _read_text_file(file_path)
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(f"Error decoding file {file_path} as UTF-8: {e}")  # type: ignore
    except IOError as e:
        raise IOError(f"Could not read file {file_path}: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred while reading {file_path}: {e}")

# --- INPUT/ Discovery Utilities ---

def _sort_key_for_candidates(path: str) -> Tuple[int, int, str]:
    """
    Sort by:
      1) preferred filename match index (lower is better)
      2) preferred extension order (lower is better)
      3) lexicographic path as tiebreaker
    """
    base = os.path.basename(path).lower()
    name_rank = next((i for i, n in enumerate(PREFERRED_NAMES) if base == n), len(PREFERRED_NAMES))
    ext = os.path.splitext(base)[1].lower()
    ext_rank = PREFERRED_EXT_ORDER.index(ext) if ext in PREFERRED_EXT_ORDER else len(PREFERRED_EXT_ORDER)
    return (name_rank, ext_rank, path.lower())

def find_default_input_file(base_dir: Optional[str] = None, input_dir_name: str = 'INPUT', recursive: bool = True) -> Optional[str]:
    """
    Scan the INPUT/ directory for a suitable entry file.

    Priority:
      - Exact preferred filenames (content.txt, input.txt, prompt.txt, user_prompt.txt)
      - Then preferred extensions in order
      - Returns the best candidate or None if empty

    Note:
      - By default, this now searches recursively (subdirectories included).
        Set recursive=False to limit to top-level files only.
    """
    base = base_dir or os.getcwd()
    input_dir = os.path.abspath(os.path.join(base, input_dir_name))
    if not os.path.isdir(input_dir):
        return None

    candidates: List[str] = []
    try:
        if recursive:
            for root, _, files in os.walk(input_dir):
                for fname in files:
                    p = os.path.join(root, fname)
                    if os.path.isfile(p):
                        candidates.append(p)
        else:
            for entry in os.listdir(input_dir):
                p = os.path.join(input_dir, entry)
                if os.path.isfile(p):
                    candidates.append(p)
    except Exception:
        return None

    if not candidates:
        return None

    candidates.sort(key=_sort_key_for_candidates)
    return candidates[0]

def find_all_input_files(base_dir: Optional[str] = None, input_dir_name: str = 'INPUT', recursive: bool = True) -> List[str]:
    """
    Return all files in INPUT/ sorted by preferred name and extension.

    Note:
      - By default, this now searches recursively (subdirectories included).
        Set recursive=False to limit to top-level files only.
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
                    files.append(p)
    else:
        for entry in os.listdir(input_dir):
            p = os.path.join(input_dir, entry)
            if os.path.isfile(p):
                files.append(p)

    files.sort(key=_sort_key_for_candidates)
    return files

def concatenate_inputs(input_paths: List[str], ingestion_cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Read and concatenate multiple files into a single text blob.
    Inserts clear headers to preserve context.
    """
    parts: List[str] = []
    for p in input_paths:
        try:
            txt = read_file_content(p, ingestion_cfg)
            header = f"\n\n===== FILE: {os.path.basename(p)} =====\n\n"
            parts.append(header + txt.strip() + "\n")
        except Exception as e:
            # Include a note but continue
            parts.append(f"\n\n===== FILE: {os.path.basename(p)} (ERROR) =====\n{e}\n")
    return "".join(parts).strip()

def materialize_concatenation_to_temp(text: str, suffix: str = ".txt") -> str:
    """
    Write concatenated text to a temporary file and return its path.
    The caller is responsible for cleanup if desired.
    """
    fd, path = tempfile.mkstemp(prefix="cogito_input_", suffix=suffix, text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path
