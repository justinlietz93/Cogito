from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_critique import build_argument_parser, should_run_interactive


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
