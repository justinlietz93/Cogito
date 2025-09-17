"""Ports for coordinating critique runs."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class CritiqueGateway(Protocol):
    """Abstraction over the critique execution pipeline."""

    def run(
        self,
        input_data: Any,
        config: Dict[str, Any],
        peer_review: bool,
        scientific_mode: bool,
    ) -> str:
        """Execute the critique and return a formatted report."""


__all__ = ["CritiqueGateway"]
