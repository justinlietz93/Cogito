"""Interactive command-line flows for the critique CLI.

Purpose:
    Provide interactive menu handling for the console interface while
    delegating actual critique execution to the core CLI app.
External Dependencies:
    Python standard library only.
Fallback Semantics:
    User prompts repeat until valid input is supplied; no implicit retries
    occur for critique execution errors.
Timeout Strategy:
    Not applicable; user-driven interactions block until completion.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

from ...application.critique.requests import FileInputRequest
from ...application.user_settings.services import (
    InvalidPreferenceError,
    SettingsPersistenceError,
    UserSettingsService,
)
from .utils import mask_key

ExecuteRunCallable = Callable[..., None]

__all__ = ["InteractiveCli"]


@dataclass
class InteractiveCli:
    """Manage interactive console workflows for the CLI."""

    settings_service: UserSettingsService
    execute_run: ExecuteRunCallable
    input_func: Callable[[str], str]
    output_func: Callable[[str], None]

    def run(self) -> None:
        """Present the main interactive menu until the user exits."""

        self.output_func("\nWelcome to the Cogito Critique CLI")
        self.output_func("Navigate using the menu numbers or shortcuts in brackets.")

        while True:
            self.output_func("\nMain Menu")
            self.output_func("  [1] Run critique")
            self.output_func("  [2] Manage preferences")
            self.output_func("  [3] Manage API keys")
            self.output_func("  [4] View current settings")
            self.output_func("  [q] Quit")
            choice = self.input_func("Select an option: ").strip().lower()

            if choice in {"1", "run", "r"}:
                self._interactive_run_flow()
            elif choice in {"2", "prefs", "p"}:
                self._preferences_menu()
            elif choice in {"3", "keys", "k"}:
                self._api_keys_menu()
            elif choice in {"4", "view", "v"}:
                self._display_settings()
            elif choice in {"q", "quit", "exit"}:
                self.output_func("Goodbye!")
                return
            else:
                self.output_func("Unrecognised option. Please select a valid menu item.")

    def _interactive_run_flow(self) -> None:
        """Guide the user through selecting files and executing a critique."""

        settings = self.settings_service.get_settings()
        input_path = self._prompt_for_input_path(settings)
        if not input_path:
            return

        output_directory = self._prompt_for_output_directory(settings)
        peer_review = self._prompt_bool("Enable peer review", settings.peer_review_default)
        scientific_mode = self._prompt_bool("Use scientific methodology", settings.scientific_mode_default)
        latex_args = self._prompt_latex_options(output_directory)

        self.execute_run(
            FileInputRequest(path=input_path),
            output_directory,
            peer_review=peer_review,
            scientific_mode=scientific_mode,
            latex_args=latex_args,
            remember_output=False,
        )

    def _prompt_for_input_path(self, settings) -> Optional[Path]:
        """Ask the user to choose an input path or reuse a recent file."""

        recent = settings.recent_files
        if recent:
            self.output_func("\nRecent files:")
            for idx, path in enumerate(recent, start=1):
                self.output_func(f"  [{idx}] {path}")

        default_display = settings.default_input_path or "<none>"
        raw = self.input_func(
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
            self.output_func("No input selected. Returning to menu.")
            return None

        resolved = Path(candidate).expanduser()
        if not resolved.exists():
            self.output_func(f"Input file not found: {resolved}")
            return None

        remember = self._prompt_bool("Remember this as default input", False)
        if remember:
            try:
                self.settings_service.set_default_input_path(str(resolved))
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self.output_func(f"Warning: Failed to store default input ({exc}).")

        return resolved

    def _prompt_for_output_directory(self, settings) -> Path:
        """Prompt the user for an output directory."""

        default_dir = settings.default_output_dir or "critiques"
        raw = self.input_func(f"Output directory [{default_dir}]: ").strip()
        chosen = raw or default_dir
        resolved = Path(chosen).expanduser()
        if resolved.exists() and not resolved.is_dir():
            self.output_func("Selected output path is not a directory. Using default 'critiques'.")
            resolved = Path("critiques").resolve()

        remember = self._prompt_bool("Remember this output directory", False)
        if remember:
            try:
                self.settings_service.set_default_output_dir(str(resolved))
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self.output_func(f"Warning: Failed to store default output directory ({exc}).")

        return resolved

    def _prompt_bool(self, message: str, default: bool) -> bool:
        """Prompt the user for a yes/no value."""

        suffix = "Y/n" if default else "y/N"
        while True:
            raw = self.input_func(f"{message}? [{suffix}]: ").strip().lower()
            if not raw:
                return default
            if raw in {"y", "yes"}:
                return True
            if raw in {"n", "no"}:
                return False
            self.output_func("Please respond with 'y' or 'n'.")

    def _prompt_latex_options(self, output_dir: Path) -> Optional[argparse.Namespace]:
        """Collect LaTeX export preferences from the user."""

        wants_latex = self._prompt_bool("Generate LaTeX output", False)
        if not wants_latex:
            return None

        compile_pdf = self._prompt_bool("Compile LaTeX to PDF", False)
        default_output = output_dir / "latex_output"
        latex_dir_raw = self.input_func(f"LaTeX output directory [{default_output}]: ").strip()
        latex_dir = Path(latex_dir_raw).expanduser() if latex_dir_raw else default_output

        level = "high"
        raw_level = self.input_func("Scientific objectivity level [low/medium/high] (default high): ").strip().lower()
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

    def _preferences_menu(self) -> None:
        """Display the preferences management menu."""

        while True:
            settings = self.settings_service.get_settings()
            self.output_func("\nPreferences")
            self.output_func(f"  [1] Default input path: {settings.default_input_path or '<none>'}")
            self.output_func(f"  [2] Default output directory: {settings.default_output_dir or 'critiques'}")
            self.output_func(f"  [3] Preferred provider: {settings.preferred_provider or '<auto>'}")
            self.output_func(f"  [4] Peer review default: {'enabled' if settings.peer_review_default else 'disabled'}")
            self.output_func(
                f"  [5] Scientific mode default: {'enabled' if settings.scientific_mode_default else 'disabled'}"
            )
            self.output_func(f"  [6] Configuration file path: {settings.config_path or '<project config>'}")
            self.output_func("  [7] Clear recent files")
            self.output_func("  [b] Back")
            choice = self.input_func("Select an option: ").strip().lower()

            try:
                if choice == "1":
                    self._handle_set_default_input()
                elif choice == "2":
                    self._handle_set_default_output()
                elif choice == "3":
                    self._handle_set_provider()
                elif choice == "4":
                    self.settings_service.set_peer_review_default(
                        self._prompt_bool("Enable peer review by default", settings.peer_review_default)
                    )
                    self.output_func("Peer review default updated.")
                elif choice == "5":
                    self.settings_service.set_scientific_mode_default(
                        self._prompt_bool(
                            "Enable scientific methodology by default", settings.scientific_mode_default
                        )
                    )
                    self.output_func("Scientific mode default updated.")
                elif choice == "6":
                    self._handle_set_config_path()
                elif choice == "7":
                    self.settings_service.clear_recent_files()
                    self.output_func("Recent files cleared.")
                elif choice in {"b", "back"}:
                    return
                else:
                    self.output_func("Unrecognised option.")
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self.output_func(f"Failed to update preferences: {exc}")

    def _handle_set_default_input(self) -> None:
        """Update the stored default input path."""

        raw = self.input_func("Enter default input path (leave blank to clear): ").strip()
        self.settings_service.set_default_input_path(raw or None)
        self.output_func("Default input path updated.")

    def _handle_set_default_output(self) -> None:
        """Update the stored default output directory."""

        raw = self.input_func("Enter default output directory (leave blank to clear): ").strip()
        if raw:
            resolved = Path(raw).expanduser()
            if resolved.exists() and not resolved.is_dir():
                raise InvalidPreferenceError("Provided path is not a directory.")
        self.settings_service.set_default_output_dir(raw or None)
        self.output_func("Default output directory updated.")

    def _handle_set_provider(self) -> None:
        """Update the preferred provider selection."""

        raw = self.input_func("Enter preferred provider key (leave blank for auto): ").strip().lower()
        self.settings_service.set_preferred_provider(raw or None)
        if raw:
            self.output_func(f"Preferred provider set to '{raw}'.")
        else:
            self.output_func("Preferred provider cleared.")

    def _handle_set_config_path(self) -> None:
        """Persist a custom configuration path."""

        raw = self.input_func("Enter path to configuration file (leave blank to use project default): ").strip()
        if raw:
            resolved = Path(raw).expanduser()
            if not resolved.exists():
                raise InvalidPreferenceError("Configuration file does not exist.")
        self.settings_service.set_config_path(raw or None)
        self.output_func("Configuration path updated.")

    def _api_keys_menu(self) -> None:
        """Show menu for managing stored API keys."""

        while True:
            keys = self.settings_service.list_api_keys()
            self.output_func("\nStored API keys:")
            if keys:
                for provider, key in keys.items():
                    self.output_func(f"  {provider}: {mask_key(key)}")
            else:
                self.output_func("  <none>")
            self.output_func("\n  [1] Add or update API key")
            self.output_func("  [2] Remove API key")
            self.output_func("  [b] Back")
            choice = self.input_func("Select an option: ").strip().lower()

            try:
                if choice == "1":
                    provider = self.input_func("Provider name: ").strip()
                    api_key = self.input_func("API key: ").strip()
                    self.settings_service.set_api_key(provider, api_key)
                    self.output_func(f"Stored key for {provider.strip().lower()}.")
                elif choice == "2":
                    provider = self.input_func("Provider to remove: ").strip()
                    self.settings_service.remove_api_key(provider)
                    self.output_func(f"Removed key for {provider.strip().lower()}.")
                elif choice in {"b", "back"}:
                    return
                else:
                    self.output_func("Unrecognised option.")
            except (InvalidPreferenceError, SettingsPersistenceError) as exc:
                self.output_func(f"Failed to update API keys: {exc}")

    def _display_settings(self) -> None:
        """Render a summary of the stored preferences."""

        settings = self.settings_service.get_settings()
        self.output_func("\nCurrent settings:")
        self.output_func(f"  Default input path: {settings.default_input_path or '<none>'}")
        self.output_func(f"  Default output directory: {settings.default_output_dir or 'critiques'}")
        self.output_func(f"  Preferred provider: {settings.preferred_provider or '<auto>'}")
        self.output_func(f"  Peer review default: {'enabled' if settings.peer_review_default else 'disabled'}")
        self.output_func(
            f"  Scientific mode default: {'enabled' if settings.scientific_mode_default else 'disabled'}"
        )
        self.output_func(f"  Configuration path: {settings.config_path or '<project config>'}")
        if settings.recent_files:
            self.output_func("  Recent files:")
            for entry in settings.recent_files:
                self.output_func(f"    - {entry}")
        else:
            self.output_func("  Recent files: <none>")
        if settings.api_keys:
            self.output_func("  Stored API keys:")
            for provider, key in settings.api_keys.items():
                self.output_func(f"    - {provider}: {mask_key(key)}")
        else:
            self.output_func("  Stored API keys: <none>")
