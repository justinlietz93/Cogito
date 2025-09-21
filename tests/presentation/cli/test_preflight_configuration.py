"""Tests for CLI preflight configuration helpers and config resolution."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from run_critique import determine_config_path
from src.presentation.cli.preflight import PreflightCliDefaults, load_preflight_defaults
from tests.presentation.cli.helpers import FakeSettings, FakeSettingsService


def _build_config(
    *,
    extract_enabled: bool = False,
    query_enabled: bool = False,
    max_points: int | None = None,
    max_queries: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Return a representative configuration mapping for tests."""

    return {
        "preflight": {
            "provider": "openai",
            "metadata": dict(metadata or {}),
            "extract": {
                "enabled": extract_enabled,
                "max_points": max_points,
                "artifact_path": "artifacts/points.json",
            },
            "queries": {
                "enabled": query_enabled,
                "max_queries": max_queries,
                "artifact_path": "artifacts/queries.json",
            },
        }
    }


def test_load_preflight_defaults_reads_configuration() -> None:
    """Ensure `load_preflight_defaults` reflects the JSON configuration."""

    config = _build_config(
        extract_enabled=True,
        query_enabled=True,
        max_points=7,
        max_queries=5,
        metadata={"stage": "preflight"},
    )

    defaults = load_preflight_defaults(config)

    assert isinstance(defaults, PreflightCliDefaults)
    assert defaults.provider == "openai"
    assert defaults.extract_enabled is True
    assert defaults.query_enabled is True
    assert defaults.max_points == 7
    assert defaults.max_queries == 5
    assert defaults.points_artifact == "artifacts/points.json"
    assert defaults.queries_artifact == "artifacts/queries.json"
    assert defaults.metadata == {"stage": "preflight"}


def test_load_preflight_defaults_handles_missing_sections() -> None:
    """Verify defaults remain safe when configuration entries are absent."""

    defaults = load_preflight_defaults({})

    assert defaults.extract_enabled is False
    assert defaults.query_enabled is False
    assert defaults.max_points is None
    assert defaults.max_queries is None
    assert defaults.points_artifact == "artifacts/points.json"
    assert defaults.queries_artifact == "artifacts/queries.json"
    assert defaults.metadata == {}


def test_determine_config_path_accepts_json_override(tmp_path: Path) -> None:
    """Ensure CLI override returning a JSON file is honoured as-is."""

    config_path = tmp_path / "custom.json"
    config_path.write_text("{}", encoding="utf-8")
    args = SimpleNamespace(config=str(config_path))
    service = FakeSettingsService()

    resolved = determine_config_path(args, service)

    assert resolved == config_path


def test_determine_config_path_rejects_yaml_paths() -> None:
    """Verify YAML configuration entries fall back to ``config.json``."""

    service = FakeSettingsService(FakeSettings())
    service.get_settings().config_path = "settings.yaml"
    args = SimpleNamespace(config=None)

    resolved = determine_config_path(args, service)

    assert resolved == Path("config.json")


def test_determine_config_path_prefers_cli_override_over_settings(tmp_path: Path) -> None:
    """Confirm CLI overrides supersede stored settings with JSON paths."""

    config_path = tmp_path / "run.json"
    config_path.write_text("{}", encoding="utf-8")
    service = FakeSettingsService(FakeSettings())
    service.get_settings().config_path = str(tmp_path / "old.json")
    args = SimpleNamespace(config=str(config_path))

    resolved = determine_config_path(args, service)

    assert resolved == config_path
