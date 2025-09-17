"""Application services for running critiques."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..user_settings.services import UserSettingsService
from .configuration import ModuleConfigBuilder
from .ports import CritiqueGateway
from ...pipeline_input import PipelineInput


@dataclass
class CritiqueRunResult:
    """Container for critique execution results."""

    critique_report: str
    peer_review_enabled: bool
    scientific_mode_enabled: bool
    module_config: Dict[str, Any]


_LOGGER = logging.getLogger(__name__)


class CritiqueRunner:
    """Coordinates critique execution using the configured gateway."""

    def __init__(
        self,
        settings_service: UserSettingsService,
        config_builder: ModuleConfigBuilder,
        gateway: CritiqueGateway,
    ) -> None:
        self._settings_service = settings_service
        self._config_builder = config_builder
        self._gateway = gateway

    def run(
        self,
        input_source: Any,
        peer_review: Optional[bool] = None,
        scientific_mode: Optional[bool] = None,
    ) -> CritiqueRunResult:
        settings = self._settings_service.get_settings()
        effective_peer_review = settings.peer_review_default if peer_review is None else bool(peer_review)
        effective_scientific_mode = (
            settings.scientific_mode_default if scientific_mode is None else bool(scientific_mode)
        )

        module_config = self._config_builder.build()
        critique_report = self._gateway.run(
            input_source,
            module_config,
            effective_peer_review,
            effective_scientific_mode,
        )

        if isinstance(input_source, PipelineInput):
            if input_source.source:
                self._settings_service.record_recent_file(input_source.source)
        elif isinstance(input_source, str):
            candidate = Path(input_source).expanduser()
            if candidate.exists():
                self._settings_service.record_recent_file(str(candidate))
            else:
                preview = input_source if len(input_source) <= 120 else f"{input_source[:117]}..."
                _LOGGER.debug(
                    "Received critique input string that is treated as literal content: %r",
                    preview,
                )

        return CritiqueRunResult(
            critique_report=critique_report,
            peer_review_enabled=effective_peer_review,
            scientific_mode_enabled=effective_scientific_mode,
            module_config=module_config,
        )


__all__ = ["CritiqueRunResult", "CritiqueRunner"]
