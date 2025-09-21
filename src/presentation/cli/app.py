"""Presentation-layer orchestration for the Critique CLI.

Purpose:
    Translate parsed command-line arguments into application-layer requests,
    apply configuration defaults, and coordinate critique executions through the
    injected services while maintaining clean-architecture boundaries.
External Dependencies:
    Python standard library modules ``argparse``, ``logging``, and ``datetime``.
Fallback Semantics:
    CLI handlers fall back to configuration defaults and provide human-readable
    error messages. No implicit retries are performed at this layer.
Timeout Strategy:
    Not applicable. The CLI delegates long-running operations to injected
    services which should apply timeout management if required.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple, Union

from ...application.critique.exceptions import ConfigurationError, MissingApiKeyError
from ...application.critique.services import CritiqueRunner
from ...application.user_settings.services import (
    InvalidPreferenceError,
    SettingsPersistenceError,
    UserSettingsService,
)
from ...pipeline_input import (
    EmptyPipelineInputError,
    InvalidPipelineInputError,
    PipelineInput,
    ensure_pipeline_input,
)
from ...latex.cli import handle_latex_output
from ...scientific_review_formatter import format_scientific_peer_review
from ...application.critique.requests import (
    DirectoryInputRequest,
    FileInputRequest,
    LiteralTextInputRequest,
)
from .utils import derive_base_name, extract_latex_args, mask_key


@dataclass(frozen=True)
class DirectoryInputDefaults:
    """Configuration defaults applied when building directory requests.

    Args:
        include: Glob patterns identifying files to aggregate by default.
        exclude: Glob patterns that should be ignored unless explicitly
            requested otherwise.
        recursive: Whether directory traversal recurses into subdirectories.
        max_files: Maximum number of files processed before truncation. ``None``
            disables the cap.
        max_chars: Maximum number of characters consumed across all files.
        section_separator: Text inserted between aggregated file contents.
        label_sections: Whether repositories prepend section headings per file.
        enabled: Flag allowing configuration to disable directory ingestion.
    """

    include: Tuple[str, ...] = ("**/*.md", "**/*.txt")
    exclude: Tuple[str, ...] = ("**/.git/**", "**/node_modules/**")
    recursive: bool = True
    max_files: Optional[int] = 200
    max_chars: Optional[int] = 1_000_000
    section_separator: str = "\n\n---\n\n"
    label_sections: bool = True
    enabled: bool = True

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "DirectoryInputDefaults":
        """Construct defaults from a configuration mapping.

        Args:
            config: Configuration dictionary loaded from persistent settings.

        Returns:
            Instance populated with values pulled from ``config`` or class
            defaults when keys are absent.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable.
        """

        defaults = cls()
        include = cls._coerce_patterns(config.get("include"), defaults.include)
        exclude = cls._coerce_patterns(config.get("exclude"), defaults.exclude)
        recursive = cls._coerce_bool(config.get("recursive"), defaults.recursive)
        max_files = cls._coerce_optional_int(config.get("max_files"), defaults.max_files)
        max_chars = cls._coerce_optional_int(config.get("max_chars"), defaults.max_chars)
        section_separator = (
            str(config.get("section_separator"))
            if isinstance(config.get("section_separator"), str)
            else defaults.section_separator
        )
        label_sections = cls._coerce_bool(config.get("label_sections"), defaults.label_sections)
        enabled = cls._coerce_bool(config.get("enabled"), defaults.enabled)
        return cls(
            include=include,
            exclude=exclude,
            recursive=recursive,
            max_files=max_files,
            max_chars=max_chars,
            section_separator=section_separator,
            label_sections=label_sections,
            enabled=enabled,
        )

    @staticmethod
    def _coerce_patterns(value: Any, default: Tuple[str, ...]) -> Tuple[str, ...]:
        """Normalise pattern configuration into a tuple of strings."""

        if value is None:
            return default
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(parts or default)
        if isinstance(value, (list, tuple, set)):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return tuple(parts or default)
        return default

    @staticmethod
    def _coerce_optional_int(value: Any, default: Optional[int]) -> Optional[int]:
        """Convert configuration values to optional integers."""

        if value is None:
            return default
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return default
        return numeric

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        """Convert configuration values to booleans while preserving default."""

        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
            return default
        return bool(value)


class CliApp:
    """Presentation layer for the console experience."""

    def __init__(
        self,
        settings_service: UserSettingsService,
        critique_runner: CritiqueRunner,
        *,
        directory_defaults: DirectoryInputDefaults | None = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> None:
        self._settings_service = settings_service
        self._critique_runner = critique_runner
        self._input = input_func
        self._output = output_func
        self._logger = logging.getLogger(__name__)
        self._directory_defaults = directory_defaults or DirectoryInputDefaults()

    @property
    def directory_defaults(self) -> DirectoryInputDefaults:
        """Return the directory input defaults configured for the CLI app.

        Returns:
            The :class:`DirectoryInputDefaults` instance active for this CLI
            session.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable.
        """

        return self._directory_defaults

    # Public entry points --------------------------------------------------
    def run(self, args: argparse.Namespace, interactive: bool) -> None:
        if interactive:
            self._run_interactive()
            return

        descriptor, fallback_message = self._build_cli_input(args)
        if descriptor is None:
            if fallback_message:
                self._output(fallback_message)
            else:
                self._output("No input selected. Use --interactive for guided navigation.")
            return

        latex_args = extract_latex_args(args)
        output_dir = (
            args.output_dir
            or self._settings_service.get_settings().default_output_dir
            or "critiques"
        )
        self._execute_run(
            descriptor,
            output_dir,
            peer_review=args.peer_review,
            scientific_mode=args.scientific_mode,
            latex_args=latex_args,
            remember_output=args.remember_output,
            fallback_message=fallback_message,
        )

    def _build_cli_input(
        self, args: argparse.Namespace
    ) -> tuple[Optional[Union[PipelineInput, DirectoryInputRequest, FileInputRequest, LiteralTextInputRequest, Mapping[str, Any], str, Path]], Optional[str]]:
        directory_arg = getattr(args, "input_dir", None)
        if directory_arg:
            if not self._directory_defaults.enabled:
                message = (
                    "Directory input has been disabled via configuration. "
                    "Set critique.directory_input.enabled to true to re-enable directory aggregation."
                )
                self._logger.warning(
                    "Directory input requested but disabled via configuration."
                )
                return None, message
            return self._make_directory_request(directory_arg, args), None

        raw_input = getattr(args, "input_file", None)
        if raw_input is None:
            return None, None
        if isinstance(raw_input, (PipelineInput, DirectoryInputRequest, FileInputRequest, LiteralTextInputRequest)):
            return raw_input, None
        if isinstance(raw_input, Mapping):
            return raw_input, None
        if isinstance(raw_input, Path):
            return FileInputRequest(path=raw_input), None
        if isinstance(raw_input, str):
            candidate = Path(raw_input).expanduser()
            if candidate.exists():
                return FileInputRequest(path=candidate), None
            try:
                literal_request = LiteralTextInputRequest(text=raw_input)
            except ValueError as exc:
                return None, f"Invalid input: {exc}"
            return literal_request, "Input file not found; treating value as literal text."
        return raw_input, None

    def _make_directory_request(self, raw_root: Union[str, Path], args: argparse.Namespace) -> DirectoryInputRequest:
        include_patterns = self._parse_pattern_list(
            getattr(args, "include", None), self._directory_defaults.include
        )
        exclude_patterns = self._parse_pattern_list(
            getattr(args, "exclude", None), self._directory_defaults.exclude
        )
        order_values = self._parse_pattern_list(getattr(args, "order", None), ())
        order_file_raw = getattr(args, "order_from", None)
        order_file = Path(order_file_raw).expanduser() if order_file_raw else None
        recursive = self._resolve_flag(
            getattr(args, "recursive", None), default=self._directory_defaults.recursive
        )
        label_sections = self._resolve_flag(
            getattr(args, "label_sections", None), default=self._directory_defaults.label_sections
        )
        max_files = getattr(args, "max_files", None)
        if max_files is None:
            max_files = self._directory_defaults.max_files
        max_chars = getattr(args, "max_chars", None)
        if max_chars is None:
            max_chars = self._directory_defaults.max_chars
        section_separator = (
            getattr(args, "section_separator", None) or self._directory_defaults.section_separator
        )

        return DirectoryInputRequest(
            root=Path(raw_root).expanduser(),
            include=include_patterns,
            exclude=exclude_patterns,
            recursive=recursive,
            order=order_values if order_values else None,
            order_file=order_file,
            max_files=max_files,
            max_chars=max_chars,
            section_separator=section_separator,
            label_sections=label_sections,
        )

    @staticmethod
    def _parse_pattern_list(raw: Optional[Union[str, Sequence[str]]], default: Sequence[str]) -> Sequence[str]:
        """Return normalised glob patterns from CLI arguments or defaults."""

        if raw is None:
            return tuple(default)
        if isinstance(raw, str):
            values = [item.strip() for item in raw.split(",") if item.strip()]
        else:
            values = [str(item).strip() for item in raw if str(item).strip()]
        return tuple(values or default)

    @staticmethod
    def _resolve_flag(value: Optional[bool], *, default: bool) -> bool:
        """Return a boolean flag using CLI overrides when provided."""

        if value is None:
            return default
        return bool(value)

    def _prepare_input_descriptor(
        self,
        input_data: Union[
            PipelineInput,
            DirectoryInputRequest,
            FileInputRequest,
            LiteralTextInputRequest,
            Path,
            Mapping[str, Any],
            str,
        ],
    ) -> Union[
        PipelineInput,
        DirectoryInputRequest,
        FileInputRequest,
        LiteralTextInputRequest,
    ]:
        if isinstance(input_data, (PipelineInput, DirectoryInputRequest, FileInputRequest, LiteralTextInputRequest)):
            return input_data
        if isinstance(input_data, Mapping):
            return ensure_pipeline_input(input_data)
        if isinstance(input_data, Path):
            return FileInputRequest(path=input_data)
        if isinstance(input_data, str):
            return LiteralTextInputRequest(text=input_data)
        return ensure_pipeline_input(input_data)

    # Interactive navigation ----------------------------------------------
    def _run_interactive(self) -> None:
        self._output("\nWelcome to the Cogito Critique CLI")
        self._output("Navigate using the menu numbers or shortcuts in brackets.")

        while True:
            self._output("\nMain Menu")
            self._output("  [1] Run critique")
            self._output("  [2] Manage preferences")
            self._output("  [3] Manage API keys")
            self._output("  [4] View current settings")
            self._output("  [q] Quit")
            choice = self._input("Select an option: ").strip().lower()

            if choice in {"1", "run", "r"}:
                self._interactive_run_flow()
            elif choice in {"2", "prefs", "p"}:
                self._preferences_menu()
            elif choice in {"3", "keys", "k"}:
                self._api_keys_menu()
            elif choice in {"4", "view", "v"}:
                self._display_settings()
            elif choice in {"q", "quit", "exit"}:
                self._output("Goodbye!")
                return
            else:
                self._output("Unrecognised option. Please select a valid menu item.")

    def _interactive_run_flow(self) -> None:
        settings = self._settings_service.get_settings()
        input_path = self._prompt_for_input_path(settings)
        if not input_path:
            return

        output_directory = self._prompt_for_output_directory(settings)
        peer_review = self._prompt_bool("Enable peer review", settings.peer_review_default)
        scientific_mode = self._prompt_bool("Use scientific methodology", settings.scientific_mode_default)
        latex_args = self._prompt_latex_options(output_directory)

        self._execute_run(
            FileInputRequest(path=input_path),
            output_directory,
            peer_review=peer_review,
            scientific_mode=scientific_mode,
            latex_args=latex_args,
            remember_output=False,
        )

    # Execution helpers ----------------------------------------------------
    def _execute_run(
        self,
        input_data: Union[
            PipelineInput,
            DirectoryInputRequest,
            FileInputRequest,
            LiteralTextInputRequest,
            Path,
            Mapping[str, Any],
            str,
        ],
        output_dir: Union[Path, str],
        *,
        peer_review: Optional[bool],
        scientific_mode: Optional[bool],
        latex_args: Optional[argparse.Namespace],
        remember_output: bool,
        fallback_message: Optional[str] = None,
    ) -> None:
        output_path = Path(output_dir)

        try:
            descriptor = self._prepare_input_descriptor(input_data)
        except (InvalidPipelineInputError, EmptyPipelineInputError, ValueError) as exc:
            self._output(f"Invalid input: {exc}")
            return

        if fallback_message:
            self._output(fallback_message)

        try:
            result = self._critique_runner.run(
                descriptor,
                peer_review=peer_review,
                scientific_mode=scientific_mode,
            )
        except MissingApiKeyError as exc:
            self._output(f"Error: {exc}")
            return
        except ConfigurationError as exc:
            self._output(f"Configuration error: {exc}")
            return
        except FileNotFoundError as exc:
            self._output(f"Input file not found: {exc}")
            return
        except (UnicodeDecodeError, OSError) as exc:
            self._logger.exception("Failed to load input content")
            self._output(f"Failed to load input: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - surface meaningful failure to the user
            self._logger.exception("Critique execution failed")
            self._output(f"Critique failed: {exc}")
            return

        pipeline_input = result.pipeline_input
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._logger.exception("Failed to prepare output directory")
            self._output(f"Failed to prepare output directory '{output_path}': {exc}")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = derive_base_name(pipeline_input)

        critique_path = output_path / f"{base_name}_critique_{timestamp}.md"
        if self._write_file(critique_path, result.critique_report, "critique report"):
            self._output(f"\nCritique report saved to {critique_path}")

        original_content = pipeline_input.content
        peer_review_path = None
        scientific_review = None
        if result.peer_review_enabled:
            scientific_review = format_scientific_peer_review(
                original_content=original_content,
                critique_report=result.critique_report,
                config=result.module_config,
                scientific_mode=result.scientific_mode_enabled,
            )
            peer_review_path = output_path / f"{base_name}_peer_review_{timestamp}.md"
            if self._write_file(peer_review_path, scientific_review, "scientific peer review"):
                self._output(f"Scientific peer review saved to {peer_review_path}")

        if latex_args and getattr(latex_args, "latex", False):
            try:
                success, tex_path, pdf_path = handle_latex_output(
                    latex_args,
                    original_content,
                    result.critique_report,
                    scientific_review,
                    scientific_mode=result.scientific_mode_enabled,
                )
            except Exception as exc:  # noqa: BLE001 - surface recoverable LaTeX issues
                self._logger.exception("LaTeX generation failed")
                self._output(f"Warning: LaTeX generation failed ({exc}).")
            else:
                if success:
                    if tex_path:
                        self._output(f"LaTeX document saved to {tex_path}")
                    if pdf_path:
                        self._output(f"PDF document saved to {pdf_path}")
                else:
                    self._output("LaTeX generation failed. Check logs for details.")

        if remember_output:
            try:
                self._settings_service.set_default_output_dir(str(output_path))
            except SettingsPersistenceError as exc:
                self._output(f"Warning: Failed to remember output directory ({exc}).")

    def _write_file(self, path: Path, content: str, description: str) -> bool:
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            self._logger.exception("Failed to write %s", description)
            self._output(f"Warning: Could not write {description} to {path} ({exc}).")
            return False
        return True

    # Prompt helpers -------------------------------------------------------
    def _prompt_for_input_path(self, settings) -> Optional[Path]:
        recent = settings.recent_files
        if recent:
            self._output("\nRecent files:")
            for idx, path in enumerate(recent, start=1):
                self._output(f"  [{idx}] {path}")

        default_display = settings.default_input_path or "<none>"
        raw = self._input(
            f"Enter input file path or choose a recent entry [default: {default_display}]: "
        ).strip()

        candidate: Optional[str]
        if not raw:
            candidate = settings.default_input_path
        elif raw.isdigit() and 1 <= int(raw) <= len(recent):
            candidate = recent[int(raw) - 1]
        else:
            candidate = raw

        if not candidate:
            self._output("No input selected. Returning to menu.")
            return None

        resolved = Path(candidate).expanduser()
        if not resolved.exists():
            self._output(f"Input file not found: {resolved}")
            return None

        remember = self._prompt_bool("Remember this as default input", False)
        if remember:
            try:
                self._settings_service.set_default_input_path(str(resolved))
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self._output(f"Warning: Failed to store default input ({exc}).")

        return resolved

    def _prompt_for_output_directory(self, settings) -> Path:
        default_dir = settings.default_output_dir or "critiques"
        raw = self._input(f"Output directory [{default_dir}]: ").strip()
        chosen = raw or default_dir
        resolved = Path(chosen).expanduser()
        if resolved.exists() and not resolved.is_dir():
            self._output("Selected output path is not a directory. Using default 'critiques'.")
            resolved = Path("critiques").resolve()

        remember = self._prompt_bool("Remember this output directory", False)
        if remember:
            try:
                self._settings_service.set_default_output_dir(str(resolved))
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self._output(f"Warning: Failed to store default output directory ({exc}).")

        return resolved

    def _prompt_bool(self, message: str, default: bool) -> bool:
        suffix = "Y/n" if default else "y/N"
        while True:
            raw = self._input(f"{message}? [{suffix}]: ").strip().lower()
            if not raw:
                return default
            if raw in {"y", "yes"}:
                return True
            if raw in {"n", "no"}:
                return False
            self._output("Please respond with 'y' or 'n'.")

    def _prompt_latex_options(self, output_dir: Path) -> Optional[argparse.Namespace]:
        wants_latex = self._prompt_bool("Generate LaTeX output", False)
        if not wants_latex:
            return None

        compile_pdf = self._prompt_bool("Compile LaTeX to PDF", False)
        default_output = output_dir / "latex_output"
        latex_dir_raw = self._input(f"LaTeX output directory [{default_output}]: ").strip()
        latex_dir = Path(latex_dir_raw).expanduser() if latex_dir_raw else default_output

        level = "high"
        raw_level = self._input("Scientific objectivity level [low/medium/high] (default high): ").strip().lower()
        if raw_level in {"low", "medium", "high"}:
            level = raw_level

        direct = self._prompt_bool("Use direct LaTeX conversion", False)

        return SimpleNamespace(
            latex=True,
            latex_compile=compile_pdf,
            latex_output_dir=str(latex_dir),
            latex_scientific_level=level,
            direct_latex=direct,
        )

    # Settings management --------------------------------------------------
    def _preferences_menu(self) -> None:
        while True:
            settings = self._settings_service.get_settings()
            self._output("\nPreferences")
            self._output(f"  [1] Default input path: {settings.default_input_path or '<none>'}")
            self._output(f"  [2] Default output directory: {settings.default_output_dir or 'critiques'}")
            self._output(f"  [3] Preferred provider: {settings.preferred_provider or '<auto>'}")
            self._output(f"  [4] Peer review default: {'enabled' if settings.peer_review_default else 'disabled'}")
            self._output(
                f"  [5] Scientific mode default: {'enabled' if settings.scientific_mode_default else 'disabled'}"
            )
            self._output(f"  [6] Configuration file path: {settings.config_path or '<project config>'}")
            self._output("  [7] Clear recent files")
            self._output("  [b] Back")
            choice = self._input("Select an option: ").strip().lower()

            try:
                if choice == "1":
                    self._handle_set_default_input()
                elif choice == "2":
                    self._handle_set_default_output()
                elif choice == "3":
                    self._handle_set_provider()
                elif choice == "4":
                    self._settings_service.set_peer_review_default(
                        self._prompt_bool("Enable peer review by default", settings.peer_review_default)
                    )
                    self._output("Peer review default updated.")
                elif choice == "5":
                    self._settings_service.set_scientific_mode_default(
                        self._prompt_bool(
                            "Enable scientific methodology by default", settings.scientific_mode_default
                        )
                    )
                    self._output("Scientific mode default updated.")
                elif choice == "6":
                    self._handle_set_config_path()
                elif choice == "7":
                    self._settings_service.clear_recent_files()
                    self._output("Recent files cleared.")
                elif choice in {"b", "back"}:
                    return
                else:
                    self._output("Unrecognised option.")
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self._output(f"Failed to update preferences: {exc}")

    def _handle_set_default_input(self) -> None:
        raw = self._input("Enter default input path (leave blank to clear): ").strip()
        self._settings_service.set_default_input_path(raw or None)
        self._output("Default input path updated.")

    def _handle_set_default_output(self) -> None:
        raw = self._input("Enter default output directory (leave blank to clear): ").strip()
        if raw:
            resolved = Path(raw).expanduser()
            if resolved.exists() and not resolved.is_dir():
                raise InvalidPreferenceError("Provided path is not a directory.")
        self._settings_service.set_default_output_dir(raw or None)
        self._output("Default output directory updated.")

    def _handle_set_provider(self) -> None:
        raw = self._input("Enter preferred provider key (leave blank for auto): ").strip().lower()
        self._settings_service.set_preferred_provider(raw or None)
        if raw:
            self._output(f"Preferred provider set to '{raw}'.")
        else:
            self._output("Preferred provider cleared.")

    def _handle_set_config_path(self) -> None:
        raw = self._input("Enter path to configuration file (leave blank to use project default): ").strip()
        if raw:
            resolved = Path(raw).expanduser()
            if not resolved.exists():
                raise InvalidPreferenceError("Configuration file does not exist.")
        self._settings_service.set_config_path(raw or None)
        self._output("Configuration path updated.")

    def _api_keys_menu(self) -> None:
        while True:
            keys = self._settings_service.list_api_keys()
            self._output("\nStored API keys:")
            if keys:
                for provider, key in keys.items():
                    self._output(f"  {provider}: {mask_key(key)}")
            else:
                self._output("  <none>")
            self._output("\n  [1] Add or update API key")
            self._output("  [2] Remove API key")
            self._output("  [b] Back")
            choice = self._input("Select an option: ").strip().lower()

            try:
                if choice == "1":
                    provider = self._input("Provider name: ").strip()
                    api_key = self._input("API key: ").strip()
                    self._settings_service.set_api_key(provider, api_key)
                    self._output(f"Stored key for {provider.strip().lower()}.")
                elif choice == "2":
                    provider = self._input("Provider to remove: ").strip()
                    self._settings_service.remove_api_key(provider)
                    self._output(f"Removed key for {provider.strip().lower()}.")
                elif choice in {"b", "back"}:
                    return
                else:
                    self._output("Unrecognised option.")
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self._output(f"Failed to update API keys: {exc}")

    def _display_settings(self) -> None:
        settings = self._settings_service.get_settings()
        self._output("\nCurrent settings:")
        self._output(f"  Default input path: {settings.default_input_path or '<none>'}")
        self._output(f"  Default output directory: {settings.default_output_dir or 'critiques'}")
        self._output(f"  Preferred provider: {settings.preferred_provider or '<auto>'}")
        self._output(f"  Peer review default: {'enabled' if settings.peer_review_default else 'disabled'}")
        self._output(
            f"  Scientific mode default: {'enabled' if settings.scientific_mode_default else 'disabled'}"
        )
        self._output(f"  Configuration path: {settings.config_path or '<project config>'}")
        if settings.recent_files:
            self._output("  Recent files:")
            for entry in settings.recent_files:
                self._output(f"    - {entry}")
        else:
            self._output("  Recent files: <none>")
        if settings.api_keys:
            self._output("  Stored API keys:")
            for provider, key in settings.api_keys.items():
                self._output(f"    - {provider}: {mask_key(key)}")
        else:
            self._output("  Stored API keys: <none>")

__all__ = ["CliApp", "DirectoryInputDefaults"]
