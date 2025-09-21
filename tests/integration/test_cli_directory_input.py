from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.critique.services import CritiqueRunner
from src.domain.user_settings.models import UserSettings
from src.infrastructure.io.file_repository import FileSystemContentRepositoryFactory
from src.presentation.cli.app import CliApp, DirectoryInputDefaults


class _StubSettingsService:
    """In-memory settings service implementation for integration testing."""

    def __init__(self) -> None:
        self._settings = UserSettings()
        self.recorded: list[str] = []

    def get_settings(self) -> UserSettings:
        return self._settings

    def record_recent_file(self, path: str) -> None:
        self.recorded.append(path)


class _StaticConfigBuilder:
    """Configuration builder returning a stable payload for tests."""

    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self._payload = payload or {"api": {"providers": {}}}

    def build(self) -> dict[str, object]:
        return dict(self._payload)


class _RecordingGateway:
    """Gateway stub that records received pipeline inputs."""

    def __init__(self) -> None:
        self.inputs: list[dict[str, object]] = []

    def run(self, input_data, config, peer_review: bool, scientific_mode: bool) -> str:
        """Record the supplied pipeline input and return a canned response."""

        self.inputs.append(
            {
                "input": input_data,
                "config": config,
                "peer_review": peer_review,
                "scientific_mode": scientific_mode,
            }
        )
        return "Rendered critique"


@pytest.mark.integration
def test_cli_directory_run_emits_outputs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = tmp_path / "research_notes"
    root.mkdir()
    (root / "alpha.md").write_text("Alpha insight\n\nDetails", encoding="utf-8")
    (root / "beta.md").write_text("Beta findings", encoding="utf-8")

    settings_service = _StubSettingsService()
    repository_factory = FileSystemContentRepositoryFactory()
    gateway = _RecordingGateway()
    runner = CritiqueRunner(settings_service, _StaticConfigBuilder(), gateway, repository_factory)
    defaults = DirectoryInputDefaults(section_separator="\n\n===\n\n", label_sections=True)
    app = CliApp(settings_service, runner, directory_defaults=defaults, output_func=lambda _: None)

    args = SimpleNamespace(
        input_file=None,
        input_dir=str(root),
        include=None,
        exclude=None,
        order=None,
        order_from=None,
        recursive=None,
        label_sections=None,
        max_files=None,
        max_chars=None,
        section_separator=None,
        output_dir=str(tmp_path / "out"),
        remember_output=False,
        peer_review=None,
        scientific_mode=None,
        latex=False,
        latex_compile=False,
        latex_output_dir=None,
        latex_scientific_level="high",
        direct_latex=False,
    )

    caplog.set_level("INFO", logger="src.infrastructure.io.directory_repository")
    app.run(args, interactive=False)

    output_files = list((tmp_path / "out").glob("*_critique_*.md"))
    assert len(output_files) == 1
    critique_path = output_files[0]
    assert critique_path.name.startswith("research_notes_critique_")

    assert settings_service.recorded
    recorded_source = settings_service.recorded[0]
    assert recorded_source.endswith("research_notes")

    assert gateway.inputs
    pipeline_input = gateway.inputs[0]["input"]
    assert "## alpha.md" in pipeline_input.content
    assert "## beta.md" in pipeline_input.content
    assert "\n\n===\n\n" in pipeline_input.content
    assert pipeline_input.metadata["files"]

    summaries = [
        record.message for record in caplog.records if "Directory aggregation summary" in record.message
    ]
    assert summaries, "expected aggregation summary log"
    summary_payload = summaries[-1].split(": ", 1)[1]
    data = json.loads(summary_payload)
    assert data["processed_files"] == 2
    assert data["total_bytes"] > 0
