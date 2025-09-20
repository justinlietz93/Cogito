import os
from pathlib import Path

import pytest

from syncretic_catalyst.domain import ProjectFile
from syncretic_catalyst.infrastructure.file_repository import ProjectFileRepository


class RecordingIO:
    """Test helper that records display output."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def test_prepare_workspace_creates_directories_and_test_file(tmp_path: Path) -> None:
    repository = ProjectFileRepository(tmp_path / "project")

    messages = repository.prepare_workspace()

    project_dir = tmp_path / "project"
    doc_dir = project_dir / "doc"
    assert project_dir.is_dir()
    assert doc_dir.is_dir()
    test_file = doc_dir / "test_write.txt"
    assert test_file.is_file()
    assert any("Successfully created test file" in message for message in messages)
    assert any("Successfully read test file content" in message for message in messages)


def test_load_skips_binary_and_git_artifacts(tmp_path: Path) -> None:
    project_dir = tmp_path / "workspace"
    doc_dir = project_dir / "doc"
    doc_dir.mkdir(parents=True)
    (doc_dir / "notes.txt").write_text("meeting notes", encoding="utf-8")
    (doc_dir / "image.png").write_bytes(b"\x89PNG\x00data")
    git_dir = project_dir / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("data", encoding="utf-8")

    repository = ProjectFileRepository(project_dir)

    files = repository.load()

    assert files == {
        os.path.join("doc", "notes.txt"): ProjectFile(os.path.join("doc", "notes.txt"), "meeting notes"),
    }


def test_save_and_save_all_write_files(tmp_path: Path) -> None:
    repository = ProjectFileRepository(tmp_path / "proj")
    first = ProjectFile(os.path.join("doc", "info.txt"), "first version")
    messages = repository.save(first)

    target = tmp_path / "proj" / "doc" / "info.txt"
    assert target.read_text(encoding="utf-8") == "first version"
    assert any("Successfully wrote" in message for message in messages)

    second = ProjectFile(os.path.join("doc", "second.txt"), "follow up")
    message_log = repository.save_all({first.path: first, second.path: second})
    assert target.read_text(encoding="utf-8") == "first version"
    second_target = tmp_path / "proj" / "doc" / "second.txt"
    assert second_target.read_text(encoding="utf-8") == "follow up"
    assert message_log[-1] == "Changes saved to some_project/."


def test_apply_ai_response_updates_existing_and_new_files(tmp_path: Path) -> None:
    repository = ProjectFileRepository(tmp_path)
    existing_path = os.path.join("doc", "existing.md")
    existing = ProjectFile(existing_path, "old")
    file_map = {existing_path: existing}

    response = (
        "=== File: doc/existing.md\nFirst line\nSecond line\n"
        "=== File: doc/new_file.md\nGenerated content"
    )

    messages = repository.apply_ai_response(response, file_map)

    assert file_map[existing_path].content == "First line\nSecond line"
    new_path = os.path.join("doc", "new_file.md")
    assert new_path in file_map
    assert file_map[new_path].content == "Generated content"
    assert any("Processed file" in message for message in messages)


def test_extract_file_paths_from_structure_handles_mixed_input() -> None:
    structure = ProjectFile(
        "structure.txt",
        """
        project/
        - README.md
        * setup.py
        notes.txt
        # comment
        scripts/run.py
        images/logo.png
        """.strip(),
    )

    result = ProjectFileRepository.extract_file_paths_from_structure(structure)

    assert result == [
        "README.md",
        "setup.py",
        "notes.txt",
        "scripts/run.py",
        "images/logo.png",
    ]


def test_parse_todo_list_and_mark_file_complete() -> None:
    todo_content = """
    - [ ] docs/plan.md needs diagrams
    * [ ] scripts/run.py
    Irrelevant line
    """.strip()

    parsed = ProjectFileRepository.parse_todo_list(todo_content)
    assert parsed == [
        {"path": "docs/plan.md", "completed": False},
        {"path": "scripts/run.py", "completed": False},
    ]

    updated = ProjectFileRepository.mark_file_complete(todo_content, "scripts/run.py")
    assert "* [x] scripts/run.py" in updated
    assert "- [ ] docs/plan.md" in updated


@pytest.mark.parametrize(
    "structure, expected",
    [
        (None, []),
        (ProjectFile("structure.md", ""), []),
    ],
)
def test_extract_file_paths_handles_empty_cases(
    structure: ProjectFile | None, expected: list[str]
) -> None:
    assert ProjectFileRepository.extract_file_paths_from_structure(structure) == expected


def test_load_returns_empty_when_root_missing(tmp_path: Path) -> None:
    repository = ProjectFileRepository(tmp_path / "missing")

    assert repository.load() == {}
