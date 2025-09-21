"""Application services coordinating critique executions.

Purpose:
    Provide orchestration logic that bridges presentation-layer requests and the
    critique pipeline gateway. The service resolves pipeline input using content
    repositories supplied via dependency injection and records relevant user
    preferences.
External Dependencies:
    Python standard library modules ``logging`` and ``dataclasses``.
Fallback Semantics:
    Fallback handling is delegated to the injected repositories and gateway.
Timeout Strategy:
    No explicit timeout handling is defined here; callers may wrap ``run`` using
    ``operation_timeout`` utilities if needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..user_settings.services import UserSettingsService
from .configuration import ModuleConfigBuilder
from .ports import ContentRepositoryFactory, CritiqueGateway
from .requests import DirectoryInputRequest, FileInputRequest, LiteralTextInputRequest
from ...pipeline_input import InvalidPipelineInputError, PipelineInput


@dataclass
class CritiqueRunResult:
    """Container for critique execution results."""

    critique_report: str
    peer_review_enabled: bool
    scientific_mode_enabled: bool
    module_config: Dict[str, Any]
    pipeline_input: PipelineInput


_LOGGER = logging.getLogger(__name__)


class CritiqueRunner:
    """Coordinates critique execution using the configured gateway."""

    def __init__(
        self,
        settings_service: UserSettingsService,
        config_builder: ModuleConfigBuilder,
        gateway: CritiqueGateway,
        repository_factory: ContentRepositoryFactory,
    ) -> None:
        self._settings_service = settings_service
        self._config_builder = config_builder
        self._gateway = gateway
        self._repository_factory = repository_factory

    def run(
        self,
        input_source: Any,
        peer_review: Optional[bool] = None,
        scientific_mode: Optional[bool] = None,
    ) -> CritiqueRunResult:
        """Execute the critique pipeline for the supplied input source.

        Args:
            input_source: Either a :class:`PipelineInput` or an application DTO
                describing how to resolve the content.
            peer_review: Optional override for enabling peer review.
            scientific_mode: Optional override for enabling scientific mode.

        Returns:
            Result container with formatted critique output and metadata flags.

        Raises:
            InvalidPipelineInputError: If ``input_source`` cannot be converted into
                a :class:`PipelineInput` instance.

        Side Effects:
            Records recently accessed sources through the settings service.

        Timeout:
            Not enforced. Callers may wrap this method in higher-level timeout
            utilities if necessary.
        """

        settings = self._settings_service.get_settings()
        effective_peer_review = settings.peer_review_default if peer_review is None else bool(peer_review)
        effective_scientific_mode = (
            settings.scientific_mode_default if scientific_mode is None else bool(scientific_mode)
        )

        pipeline_input = self._resolve_pipeline_input(input_source)
        module_config = self._config_builder.build()
        critique_report = self._gateway.run(
            pipeline_input,
            module_config,
            effective_peer_review,
            effective_scientific_mode,
        )

        self._record_recent_source(pipeline_input)

        return CritiqueRunResult(
            critique_report=critique_report,
            peer_review_enabled=effective_peer_review,
            scientific_mode_enabled=effective_scientific_mode,
            module_config=module_config,
            pipeline_input=pipeline_input,
        )

    def _resolve_pipeline_input(self, input_source: Any) -> PipelineInput:
        """Normalise supported request types into a :class:`PipelineInput`.

        Args:
            input_source: Instance describing the desired content source.

        Returns:
            Aggregated pipeline input ready for downstream consumption.

        Raises:
            InvalidPipelineInputError: If ``input_source`` cannot be processed.
        """

        if isinstance(input_source, PipelineInput):
            return input_source
        if isinstance(input_source, DirectoryInputRequest):
            repository = self._repository_factory.create_for_directory(input_source)
            return repository.load_input()
        if isinstance(input_source, FileInputRequest):
            repository = self._repository_factory.create_for_file(input_source)
            return repository.load_input()
        if isinstance(input_source, LiteralTextInputRequest):
            metadata = {"input_type": "text"}
            if input_source.label:
                metadata["input_label"] = input_source.label
            return PipelineInput(content=input_source.text, metadata=metadata)
        if isinstance(input_source, str):
            _LOGGER.debug("Treating raw string input as literal pipeline content.")
            return PipelineInput(content=input_source, metadata={"input_type": "text"})
        raise InvalidPipelineInputError(f"Unsupported critique input type: {type(input_source)!r}")

    def _record_recent_source(self, pipeline_input: PipelineInput) -> None:
        """Record the pipeline input source within the settings service."""

        source_hint = pipeline_input.source or pipeline_input.metadata.get("source_path")
        if isinstance(source_hint, str) and source_hint.strip():
            self._settings_service.record_recent_file(source_hint)


__all__ = ["CritiqueRunResult", "CritiqueRunner"]
