from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import logging

import pytest

from src.application.critique.configuration import ModuleConfigBuilder
from src.application.critique.requests import (
    DirectoryInputRequest,
    FileInputRequest,
    LiteralTextInputRequest,
)
from src.application.critique.services import CritiqueRunResult, CritiqueRunner
from src.application.preflight.orchestrator import PreflightOptions, PreflightRunResult
from src.domain.user_settings.models import UserSettings
from src.pipeline_input import PipelineInput


LOGGER = logging.getLogger(__name__)


@dataclass
class _DummyGateway:
    calls: List[Dict[str, Any]]
    result: str = "CRITIQUE"

    def run(self, input_source: Any, module_config: Dict[str, Any], peer_review: bool, scientific_mode: bool) -> str:
        self.calls.append(
            {
                "input": input_source,
                "config": module_config,
                "peer_review": peer_review,
                "scientific_mode": scientific_mode,
            }
        )
        return self.result


class _DummySettingsService:
    def __init__(self, settings: UserSettings) -> None:
        self._settings = settings
        self.recorded: List[str] = []

    def get_settings(self) -> UserSettings:
        return self._settings

    def record_recent_file(self, path: str) -> None:
        self.recorded.append(path)


@dataclass
class _StubRepository:
    payload: PipelineInput
    load_calls: int = 0

    def load_input(self) -> PipelineInput:
        self.load_calls += 1
        return self.payload


class _StubRepositoryFactory:
    def __init__(
        self,
        *,
        file_repository: _StubRepository | None = None,
        directory_repository: _StubRepository | None = None,
    ) -> None:
        self.file_repository = file_repository
        self.directory_repository = directory_repository
        self.file_requests: List[FileInputRequest] = []
        self.directory_requests: List[DirectoryInputRequest] = []

    def create_for_file(self, request: FileInputRequest) -> _StubRepository:
        self.file_requests.append(request)
        if self.file_repository is None:
            raise AssertionError("Unexpected call to create_for_file")
        return self.file_repository

    def create_for_directory(self, request: DirectoryInputRequest) -> _StubRepository:
        self.directory_requests.append(request)
        if self.directory_repository is None:
            raise AssertionError("Unexpected call to create_for_directory")
        return self.directory_repository


class _StaticBuilder(ModuleConfigBuilder):
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def build(self) -> Dict[str, Any]:  # type: ignore[override]
        return dict(self._payload)


@dataclass
class _StubPreflightOrchestrator:
    """Capture invocations made by :class:`CritiqueRunner` during preflight."""

    result: PreflightRunResult
    calls: List[Dict[str, Any]]

    def __init__(self, result: PreflightRunResult) -> None:
        self.result = result
        self.calls = []

    def run(self, pipeline_input: PipelineInput, options: PreflightOptions) -> PreflightRunResult:
        self.calls.append({"input": pipeline_input, "options": options})
        return self.result


@pytest.fixture
def default_settings() -> UserSettings:
    return UserSettings(peer_review_default=True, scientific_mode_default=False)


def test_run_with_pipeline_input_records_source(default_settings: UserSettings) -> None:
    LOGGER.info("Ensuring CritiqueRunner records sources and exposes no preflight by default.")
    service = _DummySettingsService(default_settings)
    builder = _StaticBuilder({"api": {"providers": {"openai": {}}}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway, _StubRepositoryFactory())

    pipeline_input = PipelineInput(content="body", source="example.md", metadata={"input_type": "file"})

    result = runner.run(pipeline_input)

    assert isinstance(result, CritiqueRunResult)
    assert result.critique_report == "CRITIQUE"
    assert result.peer_review_enabled is True
    assert result.scientific_mode_enabled is False
    assert result.module_config == {"api": {"providers": {"openai": {}}}}
    assert result.pipeline_input is pipeline_input
    assert result.preflight is None

    assert service.recorded == ["example.md"]
    assert gateway.calls[0]["input"] is pipeline_input


def test_run_resolves_existing_path_and_boolean_flags(tmp_path: Path, default_settings: UserSettings) -> None:
    LOGGER.info("Verifying repositories resolve file inputs and propagate flags without preflight.")
    settings = UserSettings(peer_review_default=False, scientific_mode_default=False)
    service = _DummySettingsService(settings)
    builder = _StaticBuilder({"api": {"providers": {}}})
    gateway = _DummyGateway(calls=[])
    request = FileInputRequest(path=tmp_path / "doc.txt")
    resolved_input = PipelineInput(
        content="content",
        source=str(request.path),
        metadata={"input_type": "file"},
    )
    repository = _StubRepository(payload=resolved_input)
    factory = _StubRepositoryFactory(file_repository=repository)
    runner = CritiqueRunner(service, builder, gateway, factory)

    result = runner.run(request, peer_review=False, scientific_mode=True)

    assert result.peer_review_enabled is False
    assert result.scientific_mode_enabled is True
    assert service.recorded == [str(request.path)]
    assert gateway.calls[0]["input"] is resolved_input
    assert result.pipeline_input is resolved_input
    assert factory.file_requests[0].path == request.path
    assert repository.load_calls == 1
    assert result.preflight is None


def test_run_handles_literal_text_and_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Checking literal text inputs are accepted and no preflight metadata is added by default.")
    settings = UserSettings(peer_review_default=False, scientific_mode_default=True)
    service = _DummySettingsService(settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway, _StubRepositoryFactory())

    with caplog.at_level("DEBUG"):
        result = runner.run("literal content")

    assert service.recorded == []
    assert "Treating raw string input as literal pipeline content." in caplog.text
    assert result.critique_report == "CRITIQUE"
    assert result.pipeline_input.content == "literal content"
    assert result.preflight is None


def test_run_accepts_literal_text_request(default_settings: UserSettings) -> None:
    LOGGER.info("Validating literal text requests preserve metadata and skip preflight stages by default.")
    service = _DummySettingsService(default_settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway, _StubRepositoryFactory())

    request = LiteralTextInputRequest(text="body", label="notes")
    result = runner.run(request)

    assert result.critique_report == "CRITIQUE"
    assert gateway.calls[0]["input"].metadata["input_label"] == "notes"
    assert result.pipeline_input.metadata["input_label"] == "notes"
    assert service.recorded == []
    assert result.preflight is None


def test_run_with_pipeline_input_metadata_preserved(default_settings: UserSettings) -> None:
    LOGGER.info("Confirming pipeline metadata survives runs and no preflight data is attached when unused.")
    service = _DummySettingsService(default_settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway, _StubRepositoryFactory())

    payload = PipelineInput(content="body", metadata={"source_path": "missing.txt"})
    runner.run(payload)

    assert service.recorded == ["missing.txt"]
    assert gateway.calls[0]["peer_review"] is True
    assert gateway.calls[0]["scientific_mode"] is False
    assert gateway.calls[0]["input"] is payload
    assert payload.metadata.get("preflight_artifacts") is None


def test_run_invokes_preflight_when_configured(default_settings: UserSettings) -> None:
    LOGGER.info("Ensuring preflight orchestrator is invoked and metadata captures artefact hints.")
    service = _DummySettingsService(default_settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    preflight_result = PreflightRunResult(artifact_paths={"extraction": "artifacts/points.json"})
    orchestrator = _StubPreflightOrchestrator(result=preflight_result)
    runner = CritiqueRunner(
        service,
        builder,
        gateway,
        _StubRepositoryFactory(),
        preflight_orchestrator=orchestrator,
    )

    pipeline_input = PipelineInput(content="body", metadata={})
    options = PreflightOptions(enable_extraction=True)
    result = runner.run(pipeline_input, preflight_options=options)

    assert orchestrator.calls[0]["input"] is pipeline_input
    assert orchestrator.calls[0]["options"] == options
    assert result.preflight is preflight_result
    assert pipeline_input.metadata["preflight_artifacts"] == {"extraction": "artifacts/points.json"}


def test_run_warns_when_preflight_requested_without_orchestrator(caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Validating warning is emitted when preflight options are provided but no orchestrator is configured.")
    settings = UserSettings(peer_review_default=False, scientific_mode_default=False)
    service = _DummySettingsService(settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway, _StubRepositoryFactory())

    pipeline_input = PipelineInput(content="text")
    options = PreflightOptions(enable_extraction=True)
    with caplog.at_level("WARNING"):
        result = runner.run(pipeline_input, preflight_options=options)

    assert "event=preflight status=skipped reason=orchestrator_missing" in caplog.text
    assert result.preflight is None
    assert "preflight_artifacts" not in pipeline_input.metadata


def test_run_skips_preflight_when_no_stages_enabled(default_settings: UserSettings, caplog: pytest.LogCaptureFixture) -> None:
    LOGGER.info("Checking preflight options without stages result in a debug skip and no metadata changes.")
    service = _DummySettingsService(default_settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    preflight_result = PreflightRunResult(artifact_paths={})
    orchestrator = _StubPreflightOrchestrator(result=preflight_result)
    runner = CritiqueRunner(
        service,
        builder,
        gateway,
        _StubRepositoryFactory(),
        preflight_orchestrator=orchestrator,
    )

    pipeline_input = PipelineInput(content="body")
    options = PreflightOptions()
    with caplog.at_level("DEBUG"):
        result = runner.run(pipeline_input, preflight_options=options)

    assert orchestrator.calls == []
    assert "event=preflight status=skipped reason=no_stages_enabled" in caplog.text
    assert result.preflight is None
    assert "preflight_artifacts" not in pipeline_input.metadata
