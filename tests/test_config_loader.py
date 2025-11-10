import sys
from pathlib import Path
import json
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import ConfigLoader


def test_loader_handles_missing_file(tmp_path: Path) -> None:
    loader = ConfigLoader(config_path=str(tmp_path / "missing.json"))
    assert loader.get_section("latex") == {}
    assert loader.config == {}


def test_loader_reads_existing_json(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "api": {
                    "providers": {
                        "openai": {"model": "gpt-4o"}
                    },
                    "primary_provider": "openai",
                }
            }
        )
    )

    loader = ConfigLoader(config_path=str(config_file))

    api_config = loader.get_section("api")
    assert api_config["primary_provider"] == "openai"
    assert api_config["providers"]["openai"]["model"] == "gpt-4o"
    assert loader.config["api"]["primary_provider"] == "openai"


def test_loader_handles_malformed_json(tmp_path: Path) -> None:
    malformed_json_path = tmp_path / "malformed.json"
    # Intentionally malformed JSON (missing closing brace)
    malformed_json_path.write_text('{"latex": {"documentclass": "article" ')

    with pytest.raises(json.JSONDecodeError):
        ConfigLoader(config_path=str(malformed_json_path), eager_load=True)


def test_get_helpers_and_overrides(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "latex": {"documentclass": "article"},
                "reasoning_tree": {"enabled": True},
                "council_orchestrator": {"timeout": 30},
                "misc": {"answer": 42},
            }
        )
    )

    loader = ConfigLoader(config_path=str(config_file))

    assert loader.get("misc", "answer") == 42
    assert loader.get("misc", "missing", default="fallback") == "fallback"
    assert loader.get_latex_config()["documentclass"] == "article"
    assert loader.get_reasoning_tree_config()["enabled"] is True
    assert loader.get_council_orchestrator_config()["timeout"] == 30

    loader.config = {"override": True}
    assert loader.config["override"] is True
