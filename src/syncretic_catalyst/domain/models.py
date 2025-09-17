"""Domain objects used by the Syncretic Catalyst orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProjectFile:
    """Represents a file generated within the project workspace."""

    path: str
    content: str = ""


@dataclass
class FrameworkStep:
    """Describes a single stage in the breakthrough workflow."""

    index: int
    phase_name: str
    system_prompt: str
    user_prompt_template: str
    output_file: Optional[str] = None
