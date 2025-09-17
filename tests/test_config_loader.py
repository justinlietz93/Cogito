from pathlib import Path
import sys

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import ConfigLoader


def test_loader_handles_missing_file(tmp_path: Path) -> None:
    loader = ConfigLoader(config_path=str(tmp_path / "missing.yaml"))

    assert loader.get_section("latex") == {}
    assert loader.config == {}


def test_loader_reads_existing_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
api:
  providers:
    openai:
      model: gpt-4o
  primary_provider: openai
        """.strip()
    )

    loader = ConfigLoader(config_path=str(config_file))

    api_config = loader.get_section("api")
    assert api_config["primary_provider"] == "openai"
    assert api_config["providers"]["openai"]["model"] == "gpt-4o"
    assert loader.config["api"]["primary_provider"] == "openai"


def test_loader_handles_malformed_yaml(tmp_path: Path) -> None:
    malformed_yaml_path = tmp_path / "malformed.yaml"
    malformed_yaml_path.write_text("latex: [unclosed_list\nanother: value")

    with pytest.raises(yaml.YAMLError):
        ConfigLoader(config_path=str(malformed_yaml_path), eager_load=True)
