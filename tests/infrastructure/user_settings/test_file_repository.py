from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.domain.user_settings.models import UserSettings
from src.infrastructure.user_settings.file_repository import JsonFileSettingsRepository


def test_load_returns_default_when_file_missing(tmp_path: Path) -> None:
    repo = JsonFileSettingsRepository(tmp_path / "settings.json")
    loaded = repo.load()
    assert isinstance(loaded, UserSettings)
    assert loaded.api_keys == {}


def test_roundtrip_persists_all_fields(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    repo = JsonFileSettingsRepository(path)
    settings = UserSettings(
        default_input_path="/input",
        default_output_dir="/output",
        preferred_provider="openai",
        peer_review_default=True,
        scientific_mode_default=True,
        api_keys={"openai": "abc123"},
        recent_files=["/input/file.txt"],
        config_path="/cfg.json",
    )
    repo.save(settings)

    loaded = JsonFileSettingsRepository(path).load()
    assert loaded.default_input_path == "/input"
    assert loaded.api_keys == {"openai": "abc123"}
    assert loaded.recent_files == ["/input/file.txt"]


def test_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not valid}", encoding="utf-8")
    repo = JsonFileSettingsRepository(path)
    with pytest.raises(ValueError):
        repo.load()
