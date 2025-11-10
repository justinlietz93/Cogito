"""Command line entry point for the Cogito critique pipelines.

Purpose:
- Provide a unified CLI to run the critique council.
- Enforce INPUT-only ingestion with support for an arbitrary number of files.
- Optionally run preflight stages (point extraction and query planning).

External dependencies:
- CLI execution (argparse)
- Environment (.env) via python-dotenv
- Providers configured through config.json and user settings

Fallback semantics:
- If persisted user settings cannot be loaded, an in-memory fallback repository is used.
- If preflight configuration is incomplete, the preflight orchestrator is skipped.

Timeout strategy:
- This module performs local orchestration; HTTP timeouts are configured within gateway classes.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from dotenv import load_dotenv

# INPUT ingestion utilities (centralized)
from src.input_reader import (
    find_all_input_files,
    concatenate_inputs,
    materialize_concatenation_to_temp,
)

# Application and infrastructure imports
from src.application.critique.configuration import ModuleConfigBuilder
from src.application.critique.exceptions import ConfigurationError, MissingApiKeyError
from src.application.critique.services import CritiqueRunner
from src.application.preflight import ExtractionService, PreflightOrchestrator, QueryBuildingService
from src.application.user_settings.services import SettingsPersistenceError, UserSettingsService
from src.domain.user_settings.models import UserSettings
from src.infrastructure.critique.gateway import ModuleCritiqueGateway
from src.infrastructure.preflight import OpenAIPointExtractorGateway, OpenAIQueryBuilderGateway
from src.infrastructure.io.file_repository import FileSystemContentRepositoryFactory
from src.infrastructure.user_settings.file_repository import JsonFileSettingsRepository
from src.latex.cli import add_latex_arguments
from src.presentation.cli.app import CliApp, DirectoryInputDefaults
from src.presentation.cli.preflight import PreflightCliDefaults, load_preflight_defaults


class ConfigLoadError(Exception):
    """Raised when the configuration file cannot be loaded."""


def setup_logging() -> None:
    """Initialize module logging to logs/system.log."""
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
    """Create and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the Cogito critique council from the command line.",
        epilog=(
            "Directory usage example:\n"
            "  python run_critique.py --input-dir ./notes --include \"**/*.md\" \\"
            "\n    --exclude \"**/drafts/**\" --max-files 50 --max-chars 750000\n"
            "Configuration defaults live under critique.directory_input in config.json.\n\n"
            "Preflight example:\n"
            "  python run_critique.py ./report.md --preflight-extract --preflight-build-queries\\\n"
            "\n    --points-out artifacts/points.json --queries-out artifacts/queries.json"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # Note: We preserve these CLI options for compatibility, but main() enforces INPUT/ only.
    parser.add_argument("input_file", nargs="?", help="Path to the document to critique.")
    parser.add_argument("--input-dir", dest="input_dir", help="Directory containing documents to aggregate for critique.")
    parser.add_argument("--include", dest="include", help="Comma-separated globs to include.")
    parser.add_argument("--exclude", dest="exclude", help="Comma-separated globs to exclude.")
    parser.add_argument("--order", dest="order", help="Comma-separated list of relative paths defining explicit order.")
    parser.add_argument("--order-from", dest="order_from", help="Path to a text or JSON file describing explicit order.")
    parser.add_argument("--max-files", dest="max_files", type=int, help="Maximum number of files to aggregate.")
    parser.add_argument("--max-chars", dest="max_chars", type=int, help="Maximum total characters to read.")
    parser.add_argument("--section-separator", dest="section_separator", help="Separator inserted between aggregated sections.")
    parser.add_argument("--label-sections", dest="label_sections", action="store_true", help="Prefix each aggregated file with a heading label.")
    parser.add_argument("--no-label-sections", dest="label_sections", action="store_false", help="Disable automatic heading labels for aggregated files.")
    parser.add_argument("--recursive", dest="recursive", action="store_true", help="Traverse sub-directories when aggregating directory inputs.")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false", help="Disable sub-directory traversal.")
    parser.add_argument("--peer-review", "--PR", dest="peer_review", action="store_true", help="Enable peer review enhancements.")
    parser.add_argument("--no-peer-review", dest="peer_review", action="store_false", help="Disable peer review enhancements for this run.")
    parser.add_argument("--scientific", dest="scientific_mode", action="store_true", help="Use scientific methodology agents.")
    parser.add_argument("--no-scientific", dest="scientific_mode", action="store_false", help="Disable scientific methodology for this run.")
    parser.add_argument("--output-dir", dest="output_dir", help="Directory where critique reports should be stored.")
    parser.add_argument("--preflight-extract", dest="preflight_extract", action="store_true", help="Enable the preflight point extraction stage.")
    parser.add_argument("--no-preflight-extract", dest="preflight_extract", action="store_false", help="Disable preflight point extraction for this run.")
    parser.add_argument("--preflight-build-queries", dest="preflight_build_queries", action="store_true", help="Enable the preflight query-planning stage.")
    parser.add_argument("--no-preflight-build-queries", dest="preflight_build_queries", action="store_false", help="Disable preflight query planning for this run.")
    parser.add_argument("--points-out", dest="points_out", help="Path for writing extracted points JSON (relative to output dir if relative).")
    parser.add_argument("--queries-out", dest="queries_out", help="Path for writing query plan JSON (relative to output dir if relative).")
    parser.add_argument("--max-points", dest="max_points", type=int, help="Override maximum number of extracted points.")
    parser.add_argument("--max-queries", dest="max_queries", type=int, help="Override maximum number of generated queries.")
    parser.add_argument("--remember-output", action="store_true", help="Persist the provided output directory as the default.")

    interactive_group = parser.add_mutually_exclusive_group()
    interactive_group.add_argument("--interactive", dest="interactive_mode", action="store_true", help="Force the interactive navigation experience.")
    interactive_group.add_argument("--no-interactive", dest="interactive_mode", action="store_false", help="Run without interactive prompts.")

    parser.set_defaults(
        peer_review=None,
        scientific_mode=None,
        interactive_mode=None,
        label_sections=None,
        recursive=None,
        preflight_extract=None,
        preflight_build_queries=None,
        points_out=None,
        queries_out=None,
        max_points=None,
        max_queries=None,
    )

    # LaTeX-related arguments
    parser = add_latex_arguments(parser)
    return parser


def load_config(path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file."""
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
        raise ConfigLoadError(f"Configuration file '{path}' could not be read: {exc}") from exc


def extract_directory_defaults(
    config: Mapping[str, Any],
    *,
    section: str = "critique",
    override_key: Optional[str] = None,
) -> DirectoryInputDefaults:
    """Build directory input defaults from the loaded configuration mapping.

    Args:
        config: Parsed configuration dictionary loaded from config.json.
        section: Top-level configuration section.
        override_key: Optional identifier selecting entries within directory_input_overrides.

    Returns:
        DirectoryInputDefaults instance derived from config with any overrides applied.
    """
    section_mapping = config.get(section, {})
    if not isinstance(section_mapping, Mapping):
        return DirectoryInputDefaults()

    directory_section = section_mapping.get("directory_input", {})
    if isinstance(directory_section, Mapping):
        defaults = DirectoryInputDefaults.from_mapping(directory_section)
    else:
        defaults = DirectoryInputDefaults()

    overrides_container = section_mapping.get("directory_input_overrides", {})
    if not isinstance(overrides_container, Mapping):
        return defaults

    override_mappings: list[Mapping[str, Any]] = []

    default_override = overrides_container.get("default")
    if isinstance(default_override, Mapping):
        override_mappings.append(default_override)

    candidate_key = override_key or section
    specific_override = overrides_container.get(candidate_key)
    if isinstance(specific_override, Mapping):
        override_mappings.append(specific_override)

    for override_mapping in override_mappings:
        defaults = defaults.with_overrides(override_mapping)

    return defaults


def _compose_preflight_gateway_config(
    module_config: Mapping[str, Any],
    preflight_section: Mapping[str, Any],
    *,
    provider: str,
) -> Optional[Dict[str, Any]]:
    """Merge resolved provider credentials with preflight overrides for gateways."""
    provider_key = provider.lower()
    api_section = module_config.get("api", {})
    provider_config: Dict[str, Any] = {}
    if isinstance(api_section, Mapping):
        providers = api_section.get("providers", {})
        if isinstance(providers, Mapping):
            base_provider = providers.get(provider_key)
            if isinstance(base_provider, Mapping):
                provider_config.update(dict(base_provider))
        direct_entry = api_section.get(provider_key)
        if isinstance(direct_entry, Mapping):
            provider_config.update(dict(direct_entry))

    preflight_api = preflight_section.get("api", {}) if isinstance(preflight_section, Mapping) else {}
    if isinstance(preflight_api, Mapping):
        override_entry = preflight_api.get(provider_key)
        if isinstance(override_entry, Mapping):
            provider_config.update(dict(override_entry))

    if not provider_config:
        return None

    merged: Dict[str, Any] = {}
    if isinstance(preflight_section, Mapping):
        timeouts = preflight_section.get("timeouts")
        if isinstance(timeouts, Mapping):
            merged["timeouts"] = dict(timeouts)

    api_overrides: Dict[str, Any] = {}
    if isinstance(preflight_api, Mapping):
        for name, value in preflight_api.items():
            if name == provider_key:
                continue
            if isinstance(value, Mapping):
                api_overrides[name] = dict(value)
    api_overrides[provider_key] = provider_config
    merged["api"] = api_overrides
    return merged


def _initialise_preflight_orchestrator(
    base_config: Mapping[str, Any],
    config_builder: ModuleConfigBuilder,
    defaults: PreflightCliDefaults,
) -> Optional[PreflightOrchestrator]:
    """Construct the preflight orchestrator when configuration permits."""
    logger = logging.getLogger(__name__)
    preflight_section = base_config.get("preflight")
    if not isinstance(preflight_section, Mapping):
        return None

    try:
        module_config = config_builder.build()
    except (MissingApiKeyError, ConfigurationError) as exc:
        logger.debug("Preflight orchestrator unavailable: %s", exc)
        return None

    provider = defaults.provider.lower()
    if provider != "openai":
        logger.warning(
            "Preflight orchestrator currently supports only the OpenAI provider; requested '%s' was skipped.",
            defaults.provider,
        )
        return None

    gateway_config = _compose_preflight_gateway_config(
        module_config,
        preflight_section,
        provider=provider,
    )
    if gateway_config is None:
        logger.debug("Skipping preflight orchestrator setup: missing provider configuration for '%s'.", provider)
        return None

    try:
        extraction_gateway = OpenAIPointExtractorGateway(config=gateway_config)
        query_gateway = OpenAIQueryBuilderGateway(config=gateway_config)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to configure preflight gateways: %s", exc)
        return None

    extraction_service = ExtractionService(extraction_gateway, default_max_points=defaults.max_points)
    query_service = QueryBuildingService(query_gateway, default_max_queries=defaults.max_queries)
    return PreflightOrchestrator(extraction_service, query_service)


def determine_config_path(args: argparse.Namespace, settings_service: UserSettingsService) -> Path:
    """Resolve the JSON configuration path used for CLI execution.

    YAML paths are ignored to ensure compatibility with the JSON loader used by the CLI.
    """
    logger = logging.getLogger(__name__)

    def _normalise(candidate: Path | None) -> Path | None:
        if candidate is None:
            return None
        suffix = candidate.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            logger.info(
                "Configuration path '%s' uses YAML; defaulting to config.json for CLI preflight support.",
                candidate,
            )
            return None
        return candidate

    override = getattr(args, "config", None)
    if override:
        override_path = _normalise(Path(override).expanduser())
        if override_path is not None:
            return override_path
        return Path("config.json")

    stored = settings_service.get_settings().config_path
    stored_path = _normalise(Path(stored).expanduser() if stored else None)
    if stored_path is not None:
        return stored_path

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
    """Return True if the interactive experience should be used."""
    interactive_mode = getattr(args, "interactive_mode", None)
    if interactive_mode is True:
        return True
    if interactive_mode is False:
        return False
    # Non-interactive when a directory is provided via CLI, even if no input_file is given
    provided_file = getattr(args, "input_file", None)
    provided_dir = getattr(args, "input_dir", None)
    return provided_file is None and provided_dir is None


def _enforce_input_only_and_batch_if_needed(args: argparse.Namespace) -> None:
    """Enforce that ingestion only uses INPUT/ and supports arbitrary number of files.

    Behaviour:
    - If --input-dir is provided, it must equal the project INPUT/ directory.
    - If an input_file is provided, it must be located under INPUT/.
    - If neither is provided, batch-ingest everything under INPUT/ into a temp file,
      and set args.input_file to that generated path.
    """
    base_dir = Path.cwd()
    input_dir_path = (base_dir / "INPUT").resolve()

    def _under(p: Path) -> bool:
        try:
            rp = p.resolve()
            return (input_dir_path == rp) or (input_dir_path in rp.parents)
        except Exception:
            return False

    provided_dir = getattr(args, "input_dir", None)
    if provided_dir:
        provided_dir_path = Path(provided_dir).expanduser().resolve()
        if provided_dir_path != input_dir_path:
            print(f"Error: Pipelines ingest only from {input_dir_path}. Provided directory '{provided_dir_path}' is not allowed.")
            sys.exit(2)

    provided_file = getattr(args, "input_file", None)
    if provided_file:
        provided_file_path = Path(provided_file).expanduser().resolve()
        if not _under(provided_file_path):
            print(f"Error: Pipelines ingest only from {input_dir_path}. Provided file '{provided_file_path}' is not under INPUT/.")
            sys.exit(2)

    if not provided_dir and not provided_file:
        files = find_all_input_files(base_dir=str(base_dir), input_dir_name="INPUT", recursive=True)
        if not files:
            print(f"Error: No input files found under {input_dir_path}")
            sys.exit(2)
        combined = concatenate_inputs(files)
        temp_path = materialize_concatenation_to_temp(combined)
        setattr(args, "input_file", temp_path)


def main() -> None:
    """CLI entrypoint."""
    parser = build_argument_parser()
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)
    load_dotenv()

    # INPUT-only enforcement (supports arbitrary number of files via batch)
    _enforce_input_only_and_batch_if_needed(args)

    # Settings repository
    repository = JsonFileSettingsRepository()
    try:
        settings_service = UserSettingsService(repository)
    except SettingsPersistenceError as exc:
        logger.error("Failed to load persisted settings: %s", exc)
        print("Warning: could not load saved settings. Using in-memory defaults for this session.")
        settings_service = UserSettingsService(_EphemeralSettingsRepository())

    # Load configuration
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

    # Build orchestrators and services
    config_builder = ModuleConfigBuilder(base_config, settings_service, os.getenv)
    preflight_defaults = load_preflight_defaults(base_config)
    preflight_orchestrator = _initialise_preflight_orchestrator(
        base_config,
        config_builder,
        preflight_defaults,
    )

    repository_factory = FileSystemContentRepositoryFactory()
    critique_runner = CritiqueRunner(
        settings_service,
        config_builder,
        ModuleCritiqueGateway(),
        repository_factory,
        preflight_orchestrator=preflight_orchestrator,
    )

    directory_defaults = extract_directory_defaults(base_config)
    cli_app = CliApp(
        settings_service,
        critique_runner,
        directory_defaults=directory_defaults,
        preflight_defaults=preflight_defaults,
    )

    interactive = should_run_interactive(args)
    cli_app.run(args, interactive=interactive)


if __name__ == "__main__":
    main()
