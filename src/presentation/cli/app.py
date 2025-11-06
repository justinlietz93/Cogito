"""Presentation-layer orchestration for the Cogito CLI.

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
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Union

from ...application.critique.exceptions import ConfigurationError, MissingApiKeyError
from ...application.critique.requests import (
    DirectoryInputRequest,
    FileInputRequest,
    LiteralTextInputRequest,
)
from ...application.critique.services import CritiqueRunner
from ...application.preflight.orchestrator import PreflightOptions
from ...application.user_settings.services import (
    SettingsPersistenceError,
    UserSettingsService,
)
from ...latex.cli import handle_latex_output
from ...pipeline_input import (
    EmptyPipelineInputError,
    InvalidPipelineInputError,
    PipelineInput,
    PipelineInputError,
    ensure_pipeline_input,
)
from ...scientific_review_formatter import format_scientific_peer_review
from .directory_defaults import DirectoryInputDefaults
from .interactive import InteractiveCli
from .preflight import (
    PreflightCliDefaults,
    PreflightCliOverrides,
    build_preflight_options,
    update_preflight_metadata,
)
from .utils import derive_base_name, extract_latex_args

InputArgument = Union[
    PipelineInput,
    DirectoryInputRequest,
    FileInputRequest,
    LiteralTextInputRequest,
    Path,
    Mapping[str, Any],
    str,
]

__all__ = ["CliApp", "DirectoryInputDefaults"]


class CliApp:
    """Presentation layer for the console experience."""

    def __init__(
        self,
        settings_service: UserSettingsService,
        critique_runner: CritiqueRunner,
        *,
        directory_defaults: DirectoryInputDefaults | None = None,
        preflight_defaults: PreflightCliDefaults | None = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> None:
        self._settings_service = settings_service
        self._critique_runner = critique_runner
        self._input = input_func
        self._output = output_func
        self._logger = logging.getLogger(__name__)
        self._directory_defaults = directory_defaults or DirectoryInputDefaults()
        self._preflight_defaults = preflight_defaults
        self._interactive = InteractiveCli(
            settings_service=self._settings_service,
            execute_run=self._execute_run,
            input_func=self._input,
            output_func=self._output,
        )

    @property
    def directory_defaults(self) -> DirectoryInputDefaults:
        """Return the directory input defaults configured for the CLI app."""

        return self._directory_defaults

    # Public entry points --------------------------------------------------
    def run(self, args: argparse.Namespace, interactive: bool) -> None:
        """Execute CLI workflows based on parsed arguments."""

        if interactive:
            self._interactive.run()
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
            cli_args=args,
        )

    def _run_interactive(self) -> None:
        """Backward-compatible wrapper for interactive execution."""

        self._interactive.run()

    def _interactive_run_flow(self) -> None:
        """Delegate interactive critique flow to the controller."""

        self._interactive._interactive_run_flow()

    def _prompt_for_input_path(self, settings):
        """Proxy to the interactive controller for input selection."""

        return self._interactive._prompt_for_input_path(settings)

    def _prompt_for_output_directory(self, settings):
        """Proxy to the interactive controller for output directory selection."""

        return self._interactive._prompt_for_output_directory(settings)

    def _prompt_bool(self, message: str, default: bool) -> bool:
        """Delegate boolean prompting to the controller."""

        return self._interactive._prompt_bool(message, default)

    def _prompt_latex_options(self, output_dir: Path):
        """Delegate LaTeX configuration prompts to the controller."""

        return self._interactive._prompt_latex_options(output_dir)

    def _preferences_menu(self) -> None:
        """Run the preferences management menu via the controller."""

        self._interactive._preferences_menu()

    def _handle_set_default_input(self) -> None:
        """Delegate default input update to the controller."""

        self._interactive._handle_set_default_input()

    def _handle_set_default_output(self) -> None:
        """Delegate default output update to the controller."""

        self._interactive._handle_set_default_output()

    def _handle_set_provider(self) -> None:
        """Delegate provider preference updates to the controller."""

        self._interactive._handle_set_provider()

    def _handle_set_config_path(self) -> None:
        """Delegate configuration path updates to the controller."""

        self._interactive._handle_set_config_path()

    def _api_keys_menu(self) -> None:
        """Run the API key management menu via the controller."""

        self._interactive._api_keys_menu()

    def _display_settings(self) -> None:
        """Display stored settings via the controller."""

        self._interactive._display_settings()

    def _build_cli_input(
        self, args: argparse.Namespace
    ) -> tuple[Optional[InputArgument], Optional[str]]:
        """Construct an input descriptor from parsed arguments."""

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

    def _make_directory_request(
        self, raw_root: Union[str, Path], args: argparse.Namespace
    ) -> DirectoryInputRequest:
        """Translate CLI arguments into a directory ingestion request."""

        include_patterns = self._parse_pattern_list(
            getattr(args, "include", None), self._directory_defaults.include
        )
        exclude_patterns = self._parse_pattern_list(
            getattr(args, "exclude", None), self._directory_defaults.exclude
        )
        order_arg = getattr(args, "order", None)
        if order_arg is None and self._directory_defaults.order:
            order_values = tuple(self._directory_defaults.order)
        else:
            order_values = self._parse_pattern_list(order_arg, ())

        order_file_arg = getattr(args, "order_from", None)
        if order_file_arg:
            order_file = Path(order_file_arg).expanduser()
        elif not order_values and self._directory_defaults.order_file:
            order_file = Path(self._directory_defaults.order_file).expanduser()
        else:
            order_file = None
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
    def _parse_pattern_list(
        raw: Optional[Union[str, Sequence[str]]], default: Sequence[str]
    ) -> Sequence[str]:
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
        self, input_data: InputArgument
    ) -> Union[PipelineInput, DirectoryInputRequest, FileInputRequest, LiteralTextInputRequest]:
        """Coerce arbitrary CLI input into pipeline-ready descriptors."""

        if isinstance(input_data, (PipelineInput, DirectoryInputRequest, FileInputRequest, LiteralTextInputRequest)):
            return input_data
        if isinstance(input_data, Mapping):
            return ensure_pipeline_input(input_data)
        if isinstance(input_data, Path):
            return FileInputRequest(path=input_data)
        if isinstance(input_data, str):
            return LiteralTextInputRequest(text=input_data)
        return ensure_pipeline_input(input_data)

    # Execution helpers ----------------------------------------------------
    def _execute_run(
        self,
        input_data: InputArgument,
        output_dir: Union[Path, str],
        *,
        peer_review: Optional[bool],
        scientific_mode: Optional[bool],
        latex_args: Optional[argparse.Namespace],
        remember_output: bool,
        fallback_message: Optional[str] = None,
        cli_args: argparse.Namespace | None = None,
    ) -> None:
        """Execute a critique run and persist artefacts to disk.

        Args:
            input_data: Source descriptor resolved from CLI arguments.
            output_dir: Target directory for run artefacts.
            peer_review: Optional override for the peer review flag.
            scientific_mode: Optional override for scientific mode.
            latex_args: Parsed LaTeX configuration namespace.
            remember_output: Whether to persist ``output_dir`` as default.
            fallback_message: Optional message displayed before execution when
                the CLI had to fall back to a default input description.
            cli_args: Full CLI namespace used to derive preflight overrides.

        Returns:
            None.

        Raises:
            None. All errors are handled and surfaced via user-facing messages.

        Side Effects:
            Writes critique, peer review, and optional preflight artefacts to
            disk and updates persisted settings when requested.

        Timeout:
            Not enforced at this layer; blocking operations rely on downstream
            services to honour configured timeouts.
        """

        output_path = Path(output_dir)

        try:
            descriptor = self._prepare_input_descriptor(input_data)
        except (InvalidPipelineInputError, EmptyPipelineInputError, ValueError) as exc:
            self._output(f"Invalid input: {exc}")
            return

        if fallback_message:
            self._output(fallback_message)

        overrides = PreflightCliOverrides.from_namespace(cli_args)
        preflight_options = build_preflight_options(self._preflight_defaults, overrides)

        try:
            result = self._critique_runner.run(
                descriptor,
                peer_review=peer_review,
                scientific_mode=scientific_mode,
                preflight_options=preflight_options,
            )
        except PipelineInputError as exc:
            self._logger.exception('Repository failed to aggregate input')
            self._output(f"Failed to load input: {exc}")
            return
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

        defaults = self._preflight_defaults or PreflightCliDefaults()
        update_preflight_metadata(
            result,
            output_path,
            defaults,
            logger=self._logger,
            notify=self._output,
        )

    def _write_file(self, path: Path, content: str, description: str) -> bool:
        """Persist text content to disk, logging failures."""

        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            self._logger.exception("Failed to write %s", description)
            self._output(f"Warning: Could not write {description} to {path} ({exc}).")
            return False
        return True
