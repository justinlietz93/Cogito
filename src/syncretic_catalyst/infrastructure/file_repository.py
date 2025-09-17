"""Filesystem-backed repository for Syncretic Catalyst project files."""
from __future__ import annotations

import datetime
import os
import traceback
from pathlib import Path
from typing import Dict, List

from ..domain import ProjectFile


class ProjectFileRepository:
    """Persist and retrieve project files for the breakthrough workflow."""

    _BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exe", ".dll"}

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    # Workspace preparation -------------------------------------------------
    def prepare_workspace(self) -> List[str]:
        messages = ["PRE-CHECK: Verifying we can create and write to directories..."]
        project_dir = self.project_root
        doc_dir = project_dir / "doc"
        try:
            project_dir.mkdir(exist_ok=True)
            doc_dir.mkdir(exist_ok=True)

            test_file = doc_dir / "test_write.txt"
            test_file.write_text(
                f"Test write permission - {datetime.datetime.now()}",
                encoding="utf-8",
            )
            messages.append(f"PRE-CHECK: Successfully created test file at {test_file}")

            test_content = test_file.read_text(encoding="utf-8")
            preview = test_content[:20]
            messages.append(f"PRE-CHECK: Successfully read test file content: '{preview}...'")
        except Exception as exc:  # pragma: no cover - defensive logging
            messages.append(f"ERROR in pre-check: {exc}")
            messages.append(traceback.format_exc())
        finally:
            project_dir.mkdir(exist_ok=True)
            doc_dir.mkdir(exist_ok=True)
        return messages

    # Loading ----------------------------------------------------------------
    def load(self) -> Dict[str, ProjectFile]:
        file_map: Dict[str, ProjectFile] = {}
        root = self.project_root
        if not root.is_dir():
            return file_map

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_path = str(path.relative_to(root))
            if ".git" in rel_path:
                continue
            if path.suffix.lower() in self._BINARY_EXTENSIONS:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:  # pragma: no cover - skip unreadable files
                continue
            file_map[rel_path] = ProjectFile(rel_path, content)
        return file_map

    # Persistence ------------------------------------------------------------
    def save(self, project_file: ProjectFile) -> List[str]:
        messages: List[str] = []
        target = self.project_root / project_file.path
        messages.append(f"DEBUG: Attempting to write to {target}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            messages.append(f"DEBUG: Ensured parent directory exists: {target.parent}")

            target.write_text(project_file.content, encoding="utf-8")
            messages.append(
                f"DEBUG: Successfully wrote {len(project_file.content)} characters to {target}"
            )

            if target.exists():
                messages.append(f"DEBUG: File exists verification passed for {target}")
                messages.append(f"DEBUG: File size: {target.stat().st_size} bytes")
            else:  # pragma: no cover - sanity check
                messages.append(f"ERROR: File should exist but doesn't: {target}")
        except Exception as exc:  # pragma: no cover - defensive logging
            messages.append(f"ERROR writing to {target}: {exc}")
            messages.append(traceback.format_exc())
        return messages

    def save_all(self, file_map: Dict[str, ProjectFile]) -> List[str]:
        messages: List[str] = []
        for project_file in file_map.values():
            messages.extend(self.save(project_file))
        if messages:
            messages.append("Changes saved to some_project/.")
        return messages

    # AI response integration ------------------------------------------------
    def apply_ai_response(
        self,
        ai_text: str,
        file_map: Dict[str, ProjectFile],
    ) -> List[str]:
        messages: List[str] = []
        lines = ai_text.splitlines()
        current_file: str | None = None
        buffer: List[str] = []

        def commit_file() -> None:
            nonlocal current_file, buffer
            if not current_file:
                return
            normalized_path = current_file.replace('/', os.path.sep)
            project_file = file_map.get(normalized_path)
            if not project_file:
                project_file = ProjectFile(normalized_path, "")
                file_map[normalized_path] = project_file
            project_file.content = "\n".join(buffer)
            messages.append(f"DEBUG: Processed file {normalized_path}")
            current_file = None
            buffer = []

        for line in lines:
            if line.startswith("=== File: "):
                commit_file()
                current_file = line.replace("=== File: ", "").strip()
                buffer = []
            else:
                buffer.append(line)
        commit_file()
        return messages

    # Utilities --------------------------------------------------------------
    @staticmethod
    def extract_file_paths_from_structure(structure_file: ProjectFile | None) -> List[str]:
        if not structure_file:
            return []

        file_paths: List[str] = []
        for line in structure_file.content.splitlines():
            stripped = line.strip()
            if ("." in stripped and not stripped.startswith(("#", "-"))) or any(
                stripped.endswith(ext)
                for ext in [".py", ".js", ".html", ".css", ".md", ".txt", ".json"]
            ):
                candidate = stripped.lstrip('- */')
                token = candidate.split()[0] if candidate.split() else ""
                if token and "." in token:
                    file_paths.append(token)
        return file_paths

    @staticmethod
    def parse_todo_list(todo_content: str) -> List[Dict[str, object]]:
        files_to_implement: List[Dict[str, object]] = []
        for line in todo_content.splitlines():
            if ("- [ ]" in line or "* [ ]" in line) and "." in line:
                for part in line.split():
                    if "." in part and not part.endswith(".") and not part.startswith('.'):
                        path = part.strip("(),;:\"\\'-")
                        files_to_implement.append({"path": path, "completed": False})
                        break
        return files_to_implement

    @staticmethod
    def mark_file_complete(todo_content: str, file_path: str) -> str:
        updated_lines: List[str] = []
        for line in todo_content.splitlines():
            if file_path in line and ("- [ ]" in line or "* [ ]" in line):
                updated_lines.append(
                    line.replace("- [ ]", "- [x]").replace("* [ ]", "* [x]")
                )
            else:
                updated_lines.append(line)
        return "\n".join(updated_lines)
