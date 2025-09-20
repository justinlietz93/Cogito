import os

import pytest

from src.latex.config import LatexConfig


def test_default_configuration_is_copied() -> None:
    config = LatexConfig()
    assert config.get("document_class") == "article"

    config.set("document_class", "report")

    fresh_config = LatexConfig()
    assert fresh_config.get("document_class") == "article"


def test_user_overrides_are_applied() -> None:
    config = LatexConfig({"document_class": "report", "output_filename": "custom"})

    assert config.get("document_class") == "report"
    assert config.get("output_filename") == "custom"


def test_unknown_keys_raise_value_error() -> None:
    with pytest.raises(ValueError):
        LatexConfig({"unsupported": "value"})


def test_set_rejects_unknown_keys() -> None:
    config = LatexConfig()

    with pytest.raises(ValueError):
        config.set("missing", "value")


def test_output_paths_reflect_output_directory(tmp_path) -> None:
    target_dir = tmp_path / "latex"
    config = LatexConfig({"output_dir": str(target_dir), "output_filename": "result"})

    tex_path = config.output_tex_path
    pdf_path = config.output_pdf_path

    assert target_dir.exists()
    assert tex_path == os.path.join(str(target_dir), "result.tex")
    assert pdf_path == os.path.join(str(target_dir), "result.pdf")


def test_get_template_path_joins_template_directory(tmp_path) -> None:
    template_dir = tmp_path / "templates"
    config = LatexConfig({"template_dir": str(template_dir)})

    assert config.get_template_path("main.tex") == os.path.join(str(template_dir), "main.tex")
