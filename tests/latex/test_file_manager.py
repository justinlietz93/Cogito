from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytest

from src.latex.utils.file_manager import FileManager


def test_read_and_write_template(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_file = template_dir / "sample.tex"
    template_file.write_text("Hello $name$", encoding="utf-8")

    manager = FileManager({"template_dir": str(template_dir), "output_dir": str(tmp_path / "out")})
    content = manager.read_template("sample.tex")
    assert content == "Hello $name$"

    rendered = manager.render_template(content, {"name": "World"})
    assert rendered == "Hello World"

    output_path = manager.write_output_file("result.tex", rendered)
    assert Path(output_path).read_text(encoding="utf-8") == "Hello World"


def test_read_template_missing_file(tmp_path: Path) -> None:
    manager = FileManager({"template_dir": str(tmp_path), "output_dir": str(tmp_path / "out")})
    with pytest.raises(FileNotFoundError):
        manager.read_template("missing.tex")


def test_copy_resource_and_templates(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "a.tex").write_text("A", encoding="utf-8")
    (template_dir / "b.tex").write_text("B", encoding="utf-8")

    resource = tmp_path / "resource.dat"
    resource.write_text("data", encoding="utf-8")

    manager = FileManager({"template_dir": str(template_dir), "output_dir": str(tmp_path / "out")})
    copied_resource = manager.copy_resource(str(resource))
    assert Path(copied_resource).exists()

    copied_templates = manager.copy_templates_to_output(["a.tex", "missing.tex", "b.tex"])
    assert len(copied_templates) == 2


def test_copy_resource_missing(tmp_path: Path) -> None:
    manager = FileManager({"output_dir": str(tmp_path / "out")})
    with pytest.raises(FileNotFoundError):
        manager.copy_resource(str(tmp_path / "nope.txt"))


def test_render_template_conditionals() -> None:
    manager = FileManager({"output_dir": "out"})
    template = "Hello $name$ $if(show)$Visible$endif(show)$"
    rendered = manager.render_template(template, {"name": "World", "show": True})
    assert rendered == "Hello World Visible"

    hidden = manager.render_template(template, {"name": "World", "show": False})
    assert hidden == "Hello World "


def test_clean_output_directory(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "file.txt").write_text("content", encoding="utf-8")
    (out_dir / "sub").mkdir()
    (out_dir / "sub" / "nested.txt").write_text("nested", encoding="utf-8")

    manager = FileManager({"output_dir": str(out_dir)})
    manager.clean_output_directory()

    assert not any(out_dir.iterdir())

    # Ensure directory is created if missing
    shutil_dir = tmp_path / "new_out"
    manager = FileManager({"output_dir": str(shutil_dir)})
    shutil_dir.rmdir()
    manager.clean_output_directory()
    assert shutil_dir.exists()


def test_write_output_file_logs_error(tmp_path: Path, monkeypatch, caplog) -> None:
    manager = FileManager({"output_dir": str(tmp_path)})

    def failing_open(*_args, **_kwargs):  # type: ignore[override]
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", failing_open)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(OSError):
            manager.write_output_file("fail.tex", "content")

    assert "Failed to write output file" in caplog.text


def test_copy_resource_logs_copy_error(tmp_path: Path, monkeypatch, caplog) -> None:
    source = tmp_path / "source.tex"
    source.write_text("body", encoding="utf-8")
    manager = FileManager({"output_dir": str(tmp_path / "out")})

    monkeypatch.setattr("shutil.copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")))

    with caplog.at_level(logging.ERROR):
        with pytest.raises(OSError):
            manager.copy_resource(str(source))

    assert "Failed to copy resource" in caplog.text


def test_copy_templates_logs_copy_error(tmp_path: Path, monkeypatch, caplog) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "a.tex").write_text("A", encoding="utf-8")
    (template_dir / "b.tex").write_text("B", encoding="utf-8")

    manager = FileManager({"template_dir": str(template_dir), "output_dir": str(tmp_path / "out")})

    original_copy = shutil.copy2

    def flaky_copy(src, dest):  # type: ignore[override]
        if src.endswith("b.tex"):
            raise OSError("blocked")
        return original_copy(src, dest)

    monkeypatch.setattr("shutil.copy2", flaky_copy)

    with caplog.at_level(logging.ERROR):
        copied = manager.copy_templates_to_output(["a.tex", "b.tex"])

    assert len(copied) == 1
    assert "Failed to copy template" in caplog.text


def test_clean_output_directory_logs_removal_failure(tmp_path: Path, monkeypatch, caplog) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    target = out_dir / "file.txt"
    target.write_text("content", encoding="utf-8")

    def failing_remove(path):  # type: ignore[override]
        raise OSError("cannot remove")

    monkeypatch.setattr("os.remove", failing_remove)

    with caplog.at_level(logging.ERROR):
        manager = FileManager({"output_dir": str(out_dir)})
        manager.clean_output_directory()

    assert "Failed to remove item" in caplog.text
