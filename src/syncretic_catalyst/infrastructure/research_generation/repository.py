"""Filesystem adapters for the research generation workflow."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from ...domain import (
    DEFAULT_DOCUMENT_ORDER,
    ProjectDocument,
    ResearchProposalResult,
)


_LOGGER = logging.getLogger(__name__)


class FileSystemResearchGenerationRepository:
    """Loads project documents and persists generated artefacts."""

    def __init__(
        self,
        base_dir: Path,
        *,
        document_order: Sequence[str] | None = None,
        documents_subdir: str = "doc",
        prompt_filename: str = "ai_prompt.txt",
        proposal_filename: str = "ai_research_proposal.md",
        encoding: str = "utf-8",
    ) -> None:
        self._base_dir = base_dir
        self._documents_dir = base_dir / documents_subdir
        self._prompt_path = base_dir / prompt_filename
        self._proposal_path = base_dir / proposal_filename
        self._document_order = tuple(document_order or DEFAULT_DOCUMENT_ORDER)
        self._encoding = encoding

        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._documents_dir.mkdir(parents=True, exist_ok=True)

    @property
    def prompt_path(self) -> Path:
        """Location where the assembled prompt is persisted."""

        return self._prompt_path

    @property
    def proposal_path(self) -> Path:
        """Location where the generated proposal is persisted."""

        return self._proposal_path

    def load_documents(self) -> Sequence[ProjectDocument]:
        documents: list[ProjectDocument] = []
        for name in self._document_order:
            path = self._documents_dir / name
            if not path.exists():
                continue
            try:
                content = path.read_text(encoding=self._encoding)
            except UnicodeDecodeError as exc:
                _LOGGER.warning(
                    "Skipping document '%s' due to decode error: %s", name, exc
                )
                continue
            except OSError as exc:
                _LOGGER.warning(
                    "Skipping document '%s' due to read error: %s", name, exc
                )
                continue
            documents.append(ProjectDocument(name=name, content=content))
        return documents

    def persist_generation(self, result: ResearchProposalResult) -> None:
        self._prompt_path.write_text(result.prompt.content, encoding=self._encoding)
        self._proposal_path.write_text(result.proposal.content, encoding=self._encoding)
