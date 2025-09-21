"""Command line entry point for the Cogito critique pipelines."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

from dotenv import load_dotenv

from src.application.critique.configuration import ModuleConfigBuilder
from src.application.critique.services import CritiqueRunner
from src.application.user_settings.services import SettingsPersistenceError, UserSettingsService
from src.domain.user_settings.models import UserSettings
from src.infrastructure.critique.gateway import ModuleCritiqueGateway
from src.infrastructure.io.content_repository import FileSystemContentRepositoryFactory
from src.infrastructure.user_settings.file_repository import JsonFileSettingsRepository
from src.latex.cli import add_latex_arguments
from src.presentation.cli.app import CliApp, DirectoryInputDefaults


class ConfigLoadError(Exception):
    """Raised when the configuration file cannot be loaded."""


def setup_logging() -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    system_log = logs_dir / "system.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        filename=system_log,
        filemode="w",
        encoding="utf-8",
    )
    logging.getLogger(__name__).info("Logging configured. Writing to %s", system_log)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Cogito critique council from the command line.",
        epilog=(
            "Directory usage example:\n"
            "  python run_critique.py --input-dir ./notes --include \"**/*.md\" \\"
            "\n    --exclude \"**/drafts/**\" --max-files 50 --max-chars 750000\n"
            "Configuration defaults live under critique.directory_input in config.json."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", nargs="?", help="Path to the document to critique.")
    parser.add_argument(
        "--input-dir",
        dest="input_dir",
        help="Directory containing documents to aggregate for critique.",
    )
    parser.add_argument(
        "--include",
        dest="include",
        help=(
            "Comma-separated glob patterns to include (default sourced from "
            "configuration critique.directory_input.include)."
        ),
    )
    parser.add_argument(
        "--exclude",
        dest="exclude",
        help=(
            "Comma-separated glob patterns to exclude (default sourced from "
            "configuration critique.directory_input.exclude)."
        ),
    )
    parser.add_argument(
        "--order",
        dest="order",
        help="Comma-separated list of relative paths defining explicit aggregation order.",
    )
    parser.add_argument(
        "--order-from",
        dest="order_from",
        help="Path to a text or JSON file describing the explicit file order.",
    )
    parser.add_argument(
        "--max-files",
        dest="max_files",
        type=int,
        help=(
            "Maximum number of files to aggregate (default from configuration "
            "critique.directory_input.max_files)."
        ),
    )
    parser.add_argument(
        "--max-chars",
        dest="max_chars",
        type=int,
        help=(
            "Maximum total characters to read across all files (default from "
            "configuration critique.directory_input.max_chars)."
        ),
    )
    parser.add_argument(
        "--section-separator",
        dest="section_separator",
        help=(
            "String inserted between aggregated sections (default from "
            "configuration critique.directory_input.section_separator)."
        ),
    )
    parser.add_argument(
        "--label-sections",
        dest="label_sections",
        action="store_true",
        help=(
            "Prefix each aggregated file with a heading label (default from "
            "configuration critique.directory_input.label_sections)."
        ),
    )
    parser.add_argument(
        "--no-label-sections",
        dest="label_sections",
        action="store_false",
        help="Disable automatic heading labels for aggregated files.",
    )
    parser.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        help=(
            "Traverse sub-directories when aggregating directory inputs (default "
            "from configuration critique.directory_input.recursive)."
        ),
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help=(
            "Disable sub-directory traversal when aggregating directory inputs."
        ),
    )
    parser.add_argument(
        "--peer-review",
        "--PR",
        dest="peer_review",
        action="store_true",
        help="Enable peer review enhancements.",
    )
    parser.add_argument(
        "--no-peer-review",
        dest="peer_review",
        action="store_false",
        help="Disable peer review enhancements for this run.",
    )
    parser.add_argument(
        "--scientific",
        dest="scientific_mode",
        action="store_true",
        help="Use scientific methodology agents.",
    )
    parser.add_argument(
        "--no-scientific",
        dest="scientific_mode",
        action="store_false",
        help="Disable scientific methodology for this run.",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        help="Directory where critique reports should be stored.",
    )
    parser.add_argument(
        "--remember-output",
        action="store_true",
        help="Persist the provided output directory as the default.",
    )
    parser.add_argument(
        "--config",
        dest="config",
        help="Path to the configuration JSON file to load.",
    )
    interactive_group = parser.add_mutually_exclusive_group()
    interactive_group.add_argument(
        "--interactive",
        dest="interactive_mode",
        action="store_true",
        help="Force the interactive navigation experience.",
    )
    interactive_group.add_argument(
        "--no-interactive",
        dest="interactive_mode",
        action="store_false",
        help="Run without interactive prompts.",
    )
    parser.set_defaults(
        peer_review=None,
        scientific_mode=None,
        interactive_mode=None,
        label_sections=None,
        recursive=None,
    )
    parser = add_latex_arguments(parser)
    return parser


def load_config(path: Path) -> Dict[str, Any]:
    logger = logging.getLogger(__name__)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        logger.error("Configuration file '%s' was not found.", path)
        raise ConfigLoadError(f"Configuration file '{path}' does not exist.") from exc
    except json.JSONDecodeError:
        raise
    except OSError as exc:
        logger.error("Failed to read configuration '%s': %s", path, exc)
        raise ConfigLoadError(
            f"Configuration file '{path}' could not be read: {exc}"
        ) from exc


def extract_directory_defaults(config: Mapping[str, Any]) -> DirectoryInputDefaults:
    """Build directory input defaults from the loaded configuration mapping.

    Args:
        config: Parsed configuration dictionary loaded from ``config.json`` or a
            compatible mapping structure.

    Returns:
        Instance of :class:`DirectoryInputDefaults` populated with values from
        ``config`` when present, otherwise falling back to baked-in defaults.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; computation is purely in-memory.
    """

    critique_section = config.get("critique", {})
    if not isinstance(critique_section, Mapping):
        return DirectoryInputDefaults()
    directory_section = critique_section.get("directory_input", {})
    if not isinstance(directory_section, Mapping):
        return DirectoryInputDefaults()
    return DirectoryInputDefaults.from_mapping(directory_section)


def determine_config_path(args: argparse.Namespace, settings_service: UserSettingsService) -> Path:
    if getattr(args, "config", None):
        return Path(args.config).expanduser()

    stored = settings_service.get_settings().config_path
    if stored:
        return Path(stored)

    return Path("config.json")


class _EphemeralSettingsRepository:
    """In-memory fallback repository used when persisted settings cannot be loaded."""

    def __init__(self) -> None:
        self._settings = UserSettings()

    def load(self) -> UserSettings:
        return self._settings

    def save(self, settings: UserSettings) -> None:
        self._settings = settings


def should_run_interactive(args: argparse.Namespace) -> bool:
    interactive_mode = getattr(args, "interactive_mode", None)
    if interactive_mode is True:
        return True
    if interactive_mode is False:
        return False
    return getattr(args, "input_file", None) is None


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)
    load_dotenv()

    repository = JsonFileSettingsRepository()
    try:
        settings_service = UserSettingsService(repository)
    except SettingsPersistenceError as exc:
        logger.error("Failed to load persisted settings: %s", exc)
        print("Warning: could not load saved settings. Using in-memory defaults for this session.")
        settings_service = UserSettingsService(_EphemeralSettingsRepository())

    config_path = determine_config_path(args, settings_service)
    try:
        base_config = load_config(config_path)
    except json.JSONDecodeError as exc:
        logger.error("Configuration file '%s' is not valid JSON: %s", config_path, exc)
        print(f"Error: configuration file '{config_path}' contains invalid JSON: {exc}")
        sys.exit(1)
    except ConfigLoadError as exc:
        logger.error("%s", exc)
        print(f"Error: {exc}")
        sys.exit(1)

    config_builder = ModuleConfigBuilder(base_config, settings_service, os.getenv)
    repository_factory = FileSystemContentRepositoryFactory()
    critique_runner = CritiqueRunner(
        settings_service,
        config_builder,
        ModuleCritiqueGateway(),
        repository_factory,
    )
    directory_defaults = extract_directory_defaults(base_config)
    cli_app = CliApp(
        settings_service,
        critique_runner,
        directory_defaults=directory_defaults,
    )

    interactive = should_run_interactive(args)
    cli_app.run(args, interactive=interactive)


if __name__ == "__main__":
    main()
