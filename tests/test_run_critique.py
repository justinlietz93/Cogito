from pathlib import Path
import sys

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_critique import build_argument_parser, extract_directory_defaults, should_run_interactive
from src.presentation.cli.directory_defaults import DirectoryInputDefaults


def test_interactive_flags_are_mutually_exclusive():
    parser = build_argument_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--interactive", "--no-interactive"])


def test_should_run_interactive_defaults_without_input():
    parser = build_argument_parser()
    args = parser.parse_args([])

    assert should_run_interactive(args) is True


def test_should_run_interactive_respects_provided_input_file():
    parser = build_argument_parser()
    args = parser.parse_args(["input.txt"])

    assert should_run_interactive(args) is False


def test_should_run_interactive_respects_explicit_flag():
    parser = build_argument_parser()
    args = parser.parse_args(["--interactive", "input.txt"])

    assert should_run_interactive(args) is True

    args = parser.parse_args(["--no-interactive"])

    assert should_run_interactive(args) is False

def test_extract_directory_defaults_uses_config_values() -> None:
    config = {
        "critique": {
            "directory_input": {
                "include": ["**/*.md"],
                "exclude": ["**/archive/**"],
                "recursive": False,
                "max_files": 10,
                "max_chars": 1000,
                "section_separator": "\n--\n",
                "label_sections": False,
                "enabled": True,
                "order": ["a.md", "b.md"],
                "order_file": "order.txt",
            }
        }
    }

    defaults = extract_directory_defaults(config)

    assert defaults.include == ("**/*.md",)
    assert defaults.exclude == ("**/archive/**",)
    assert defaults.recursive is False
    assert defaults.max_files == 10
    assert defaults.max_chars == 1000
    assert defaults.section_separator == "\n--\n"
    assert defaults.label_sections is False
    assert defaults.order == ("a.md", "b.md")
    assert defaults.order_file == "order.txt"


def test_extract_directory_defaults_applies_overrides() -> None:
    config = {
        "critique": {
            "directory_input": {
                "include": ["**/*.md"],
            },
            "directory_input_overrides": {
                "default": {
                    "label_sections": False,
                    "section_separator": "\n~~\n",
                },
                "syncretic_catalyst": {
                    "order": ["outline.md"],
                    "order_file": "order_sequence.txt",
                },
            },
        }
    }

    defaults = extract_directory_defaults(config, override_key="syncretic_catalyst")

    assert defaults.label_sections is False
    assert defaults.section_separator == "\n~~\n"
    assert defaults.order == ("outline.md",)
    assert defaults.order_file == "order_sequence.txt"


def test_extract_directory_defaults_uses_section_override_when_missing_key() -> None:
    config = {
        "critique": {
            "directory_input": {},
            "directory_input_overrides": {
                "critique": {
                    "max_files": 5,
                    "enabled": False,
                }
            },
        }
    }

    defaults = extract_directory_defaults(config)

    assert defaults.max_files == 5
    assert defaults.enabled is False
