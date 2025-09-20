from typing import Mapping

from typing import Mapping

from src.domain.user_settings.models import (
    UserSettings,
    user_settings_from_dict,
    user_settings_to_dict,
)


def test_user_settings_from_dict_coerces_fields() -> None:
    raw: Mapping[str, object] = {
        "default_input_path": "/tmp/input.txt",
        "default_output_dir": "/tmp/output",
        "preferred_provider": "OpenAI",
        "peer_review_default": 1,
        "scientific_mode_default": "yes",
        "theme": "dark",
        "api_keys": {"openai": "token"},
        "recent_files": ("a", "b"),
        "config_path": "/tmp/config.yaml",
    }

    settings = user_settings_from_dict(raw)

    assert settings.default_input_path == "/tmp/input.txt"
    assert settings.default_output_dir == "/tmp/output"
    assert settings.preferred_provider == "OpenAI"
    assert settings.peer_review_default is True
    assert settings.scientific_mode_default is True
    assert settings.theme == "dark"
    assert settings.api_keys == {"openai": "token"}
    assert settings.recent_files == ["a", "b"]
    assert settings.config_path == "/tmp/config.yaml"


def test_user_settings_from_dict_returns_defaults_for_invalid_input() -> None:
    settings = user_settings_from_dict(None)
    assert settings == UserSettings()


def test_user_settings_to_dict_roundtrips() -> None:
    original = UserSettings(
        default_input_path="/tmp/input.txt",
        default_output_dir="/tmp/output",
        preferred_provider="openai",
        peer_review_default=True,
        scientific_mode_default=False,
        theme="light",
        api_keys={"openai": "token"},
        recent_files=["a"],
        config_path="/tmp/config.yaml",
    )

    as_dict = user_settings_to_dict(original)
    rebuilt = UserSettings(**as_dict)

    assert rebuilt == original

