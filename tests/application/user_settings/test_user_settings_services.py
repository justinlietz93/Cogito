from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.application.user_settings.services import (
    InvalidPreferenceError,
    SettingsPersistenceError,
    UserSettingsService,
)
from src.domain.user_settings.models import UserSettings


class InMemoryRepository:
    def __init__(self, initial: UserSettings | None = None, fail_on_save: bool = False, fail_on_load: bool = False) -> None:
        self._settings = initial or UserSettings()
        self.fail_on_save = fail_on_save
        self.fail_on_load = fail_on_load

    def load(self) -> UserSettings:
        if self.fail_on_load:
            raise IOError("failed to load")
        return self._settings

    def save(self, settings: UserSettings) -> None:
        if self.fail_on_save:
            raise IOError("failed to save")
        self._settings = settings


def test_record_recent_file_tracks_latest_first(tmp_path: Path) -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo, recent_limit=3)

    paths = [tmp_path / f"file_{idx}.txt" for idx in range(5)]
    for path in paths:
        service.record_recent_file(str(path))

    stored = service.get_settings().recent_files
    assert len(stored) == 3
    assert stored[0] == str(paths[-1].resolve())
    assert stored[1] == str(paths[-2].resolve())

    # Recording an existing file moves it to the front
    service.record_recent_file(str(paths[-2]))
    stored = service.get_settings().recent_files
    assert stored[0] == str(paths[-2].resolve())


def test_set_api_key_normalises_provider() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    service.set_api_key("OpenAI", "secret")
    assert service.get_settings().api_keys["openai"] == "secret"

    service.remove_api_key("OPENAI")
    assert "openai" not in service.get_settings().api_keys


def test_set_preferred_provider_normalises_and_persists() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    service.set_preferred_provider("OpenAI")

    settings = service.get_settings()
    assert settings.preferred_provider == "openai"
    assert repo._settings.preferred_provider == "openai"


def test_set_preferred_provider_rejects_blank_strings() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    with pytest.raises(InvalidPreferenceError):
        service.set_preferred_provider("   ")

    service.set_preferred_provider(None)
    assert service.get_settings().preferred_provider is None


def test_set_default_paths_are_normalised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    service.set_default_input_path("~/document.txt")
    assert service.get_settings().default_input_path == str((home / "document.txt").resolve())

    service.set_default_output_dir("~/output")
    assert service.get_settings().default_output_dir == str((home / "output").resolve())


def test_clear_recent_files() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)
    service.record_recent_file("/tmp/a.txt")
    service.clear_recent_files()
    assert service.get_settings().recent_files == []


def test_save_failure_raises(tmp_path: Path) -> None:
    repo = InMemoryRepository(fail_on_save=True)
    service = UserSettingsService(repo)
    with pytest.raises(SettingsPersistenceError):
        service.set_peer_review_default(True)


def test_invalid_preference_errors() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    with pytest.raises(InvalidPreferenceError):
        service.set_api_key(" ", "value")

    with pytest.raises(InvalidPreferenceError):
        service.set_api_key("provider", " ")

    with pytest.raises(InvalidPreferenceError):
        service.remove_api_key(" ")


def test_existing_preferred_provider_is_normalised_on_load() -> None:
    repo = InMemoryRepository(initial=UserSettings(preferred_provider="OpenAI"))
    service = UserSettingsService(repo)

    assert service.get_settings().preferred_provider == "openai"


def test_blank_recent_file_is_ignored() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    service.record_recent_file("")
    assert service.get_settings().recent_files == []


def test_set_config_path_normalises_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    service.set_config_path("~/settings.yaml")
    stored = service.get_settings().config_path
    assert stored == str((home / "settings.yaml").resolve())


def test_set_theme_validates_input() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    with pytest.raises(InvalidPreferenceError):
        service.set_theme("")

    service.set_theme("dark")
    assert service.get_settings().theme == "dark"


def test_remove_api_key_is_noop_for_missing_provider() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    service.set_api_key("test", "value")
    service.remove_api_key("other")
    assert service.get_settings().api_keys == {"test": "value"}


def test_constructor_normalises_recent_limit_and_load_errors(tmp_path: Path) -> None:
    repo = InMemoryRepository(fail_on_load=True)
    with pytest.raises(SettingsPersistenceError):
        UserSettingsService(repo)

    repo = InMemoryRepository()
    service = UserSettingsService(repo, recent_limit=0)
    service.record_recent_file("/tmp/a.txt")
    assert len(service.get_settings().recent_files) == 1


def test_remove_api_key_propagates_save_failure() -> None:
    repo = InMemoryRepository(initial=UserSettings(api_keys={"openai": "token"}), fail_on_save=True)
    service = UserSettingsService(repo)

    with pytest.raises(SettingsPersistenceError):
        service.remove_api_key("openai")


def test_constructor_defaults_when_repository_returns_non_model() -> None:
    class DictRepository:
        def __init__(self) -> None:
            self.saved: UserSettings | None = None

        def load(self):
            return {"preferred_provider": "openai"}

        def save(self, settings: UserSettings) -> None:
            self.saved = settings

    repo = DictRepository()
    service = UserSettingsService(repo)  # type: ignore[arg-type]

    assert isinstance(service.get_settings(), UserSettings)
    assert service.get_settings().preferred_provider is None


def test_set_scientific_mode_default_forces_boolean() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    service.set_scientific_mode_default(1)
    assert service.get_settings().scientific_mode_default is True


def test_list_api_keys_returns_copy() -> None:
    repo = InMemoryRepository(initial=UserSettings(api_keys={"openai": "token"}))
    service = UserSettingsService(repo)

    listed = service.list_api_keys()
    listed["anthropic"] = "new"

    assert "anthropic" not in service.get_settings().api_keys


def test_set_default_input_path_accepts_none() -> None:
    repo = InMemoryRepository()
    service = UserSettingsService(repo)

    service.set_default_input_path(None)

    assert service.get_settings().default_input_path is None
