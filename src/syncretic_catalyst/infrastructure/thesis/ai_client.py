"""Content generation adapters for the thesis builder."""
from __future__ import annotations

from ...ai_clients import AIOrchestrator


class OrchestratorContentGenerator:
    """Adapter that exposes :class:`AIOrchestrator` as a content generator."""

    def __init__(self, orchestrator: AIOrchestrator, *, default_max_tokens: int = 4000) -> None:
        self._orchestrator = orchestrator
        self._default_max_tokens = default_max_tokens

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        requested_tokens = max_tokens or self._default_max_tokens
        return self._orchestrator.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=requested_tokens,
        )
