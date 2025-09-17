"""Pytest coverage for LaTeX generation using stored peer review artifacts."""

import logging
from pathlib import Path
from typing import Tuple

import pytest

from src.latex.formatter import format_as_latex

logger = logging.getLogger(__name__)

CRITIQUES_DIR = Path("critiques")
CONTENT_PATH = Path("content.txt")


def _locate_peer_review_pair() -> Tuple[Path, Path]:
    if not CRITIQUES_DIR.exists():
        pytest.skip("'critiques' directory not available")

    peer_reviews = sorted(
        CRITIQUES_DIR.glob("content_peer_review_*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not peer_reviews:
        pytest.skip("No peer review files found in 'critiques' directory")

    peer_review_file = peer_reviews[0]
    critique_file = CRITIQUES_DIR / peer_review_file.name.replace("peer_review", "critique")
    if not critique_file.exists():
        pytest.skip(f"Corresponding critique file not found: {critique_file}")

    logger.info("Using peer review file %s", peer_review_file)
    logger.info("Using critique file %s", critique_file)
    return peer_review_file, critique_file


def _read_text(path: Path) -> str:
    if not path.exists():
        pytest.skip(f"Required fixture missing: {path}")
    return path.read_text(encoding="utf-8")


@pytest.mark.integration
def test_peer_review_latex_generation(tmp_path):
    peer_review_file, critique_file = _locate_peer_review_pair()

    original_content = _read_text(CONTENT_PATH)
    critique_content = _read_text(critique_file)
    peer_review_content = _read_text(peer_review_file)

    output_dir = tmp_path / "latex_output"
    latex_config = {
        "output_dir": str(output_dir),
        "compile_pdf": False,
        "scientific_mode": True,
        "scientific_objectivity_level": "high",
        "output_filename": "peer_review_report",
    }

    tex_path, pdf_path = format_as_latex(
        original_content,
        critique_content,
        peer_review_content,
        latex_config,
    )

    assert tex_path, "Expected LaTeX formatter to return a tex path"
    tex_file = Path(tex_path)
    assert tex_file.exists() and tex_file.is_file()
    assert tex_file.parent == output_dir

    if pdf_path:
        pdf_file = Path(pdf_path)
        assert pdf_file.exists() and pdf_file.is_file()
