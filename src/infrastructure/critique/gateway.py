"""Infrastructure implementation of the critique gateway."""

from __future__ import annotations

from typing import Any, Dict

from ...application.critique.ports import CritiqueGateway
from ... import critique_goal_document


class ModuleCritiqueGateway(CritiqueGateway):
    """Adapt the existing module entry point to the application layer."""

    def run(
        self,
        input_data: Any,
        config: Dict[str, Any],
        peer_review: bool,
        scientific_mode: bool,
    ) -> str:
        return critique_goal_document(
            input_data,
            config=config,
            peer_review=peer_review,
            scientific_mode=scientific_mode,
        )


__all__ = ["ModuleCritiqueGateway"]
