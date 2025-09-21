from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.application.critique.configuration import ModuleConfigBuilder
from src.application.critique.requests import (
    DirectoryInputRequest,
    FileInputRequest,
    LiteralTextInputRequest,
)
from src.application.critique.services import CritiqueRunResult, CritiqueRunner
from src.domain.user_settings.models import UserSettings
from src.pipeline_input import PipelineInput


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


@pytest.fixture
def default_settings() -> UserSettings:
    return UserSettings(peer_review_default=True, scientific_mode_default=False)


def test_run_with_pipeline_input_records_source(default_settings: UserSettings) -> None:
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

    assert service.recorded == ["example.md"]
    assert gateway.calls[0]["input"] is pipeline_input


def test_run_resolves_existing_path_and_boolean_flags(tmp_path: Path, default_settings: UserSettings) -> None:
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


def test_run_handles_literal_text_and_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
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


def test_run_accepts_literal_text_request(default_settings: UserSettings) -> None:
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


def test_run_with_pipeline_input_metadata_preserved(default_settings: UserSettings) -> None:
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
