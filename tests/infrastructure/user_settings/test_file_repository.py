from pathlib import Path

import json
import pytest

from src.infrastructure.user_settings.file_repository import (
    JsonFileSettingsRepository,
    default_settings_path,
)


def test_load_returns_default_when_missing(tmp_path: Path) -> None:
    repo = JsonFileSettingsRepository(path=tmp_path / "settings.json")
    settings = repo.load()
    assert settings == settings.__class__()


def test_load_raises_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not-json", encoding="utf-8")
    repo = JsonFileSettingsRepository(path=path)

    with pytest.raises(ValueError):
        repo.load()


def test_save_writes_file(tmp_path: Path) -> None:
    repo = JsonFileSettingsRepository(path=tmp_path / "settings.json")
    settings = repo.load()
    settings.theme = "dark"
    repo.save(settings)

    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["theme"] == "dark"


def test_load_returns_saved_settings(tmp_path: Path) -> None:
    repo = JsonFileSettingsRepository(path=tmp_path / "settings.json")
    settings = repo.load()
    settings.theme = "light"
    repo.save(settings)

    reloaded = repo.load()
    assert reloaded.theme == "light"


def test_load_handles_missing_file_after_exists_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    repo = JsonFileSettingsRepository(path=path)

    original_open = Path.open

    def fail_open(self: Path, *args, **kwargs):  # type: ignore[override]
        if self == path:
            raise FileNotFoundError("removed")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_open)

    settings = repo.load()
    assert settings == settings.__class__()


def test_default_settings_path_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(custom))
    expected = custom / "cogito" / "settings.json"
    assert default_settings_path() == expected


def test_repository_uses_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "home" / ".config" / "cogito" / "settings.json"

    def fake_home() -> Path:
        return tmp_path / "home"

    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setattr(Path, "home", staticmethod(fake_home))

    repo = JsonFileSettingsRepository()
    repo.save(repo.load())

    assert target.exists()
