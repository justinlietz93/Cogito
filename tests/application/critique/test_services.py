from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.application.critique.configuration import ModuleConfigBuilder
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
    runner = CritiqueRunner(service, builder, gateway)

    pipeline_input = PipelineInput(content="body", source="example.md", metadata={"input_type": "file"})

    result = runner.run(pipeline_input)

    assert isinstance(result, CritiqueRunResult)
    assert result.critique_report == "CRITIQUE"
    assert result.peer_review_enabled is True
    assert result.scientific_mode_enabled is False
    assert result.module_config == {"api": {"providers": {"openai": {}}}}

    assert service.recorded == ["example.md"]
    assert gateway.calls[0]["input"] is pipeline_input


def test_run_resolves_existing_path_and_boolean_flags(tmp_path: Path, default_settings: UserSettings) -> None:
    settings = UserSettings(peer_review_default=False, scientific_mode_default=False)
    service = _DummySettingsService(settings)
    builder = _StaticBuilder({"api": {"providers": {}}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway)

    input_path = tmp_path / "doc.txt"
    input_path.write_text("content", encoding="utf-8")

    result = runner.run(str(input_path), peer_review=False, scientific_mode=True)

    assert result.peer_review_enabled is False
    assert result.scientific_mode_enabled is True
    assert service.recorded == [str(input_path)]
    assert gateway.calls[0]["input"] == str(input_path)


def test_run_handles_literal_text_and_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    settings = UserSettings(peer_review_default=False, scientific_mode_default=True)
    service = _DummySettingsService(settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway)

    with caplog.at_level("DEBUG"):
        result = runner.run("literal content")

    assert service.recorded == []
    assert "treated as literal content" in caplog.text
    assert result.critique_report == "CRITIQUE"


def test_run_with_pipeline_input_metadata_preserved(default_settings: UserSettings) -> None:
    service = _DummySettingsService(default_settings)
    builder = _StaticBuilder({"api": {}})
    gateway = _DummyGateway(calls=[])
    runner = CritiqueRunner(service, builder, gateway)

    payload = PipelineInput(content="body", metadata={"source_path": "missing.txt"})
    runner.run(payload)

    assert service.recorded == []
    assert gateway.calls[0]["peer_review"] is True
    assert gateway.calls[0]["scientific_mode"] is False
