"""Helpers for locating LaTeX engines on Windows installations."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from typing import Iterable, Optional


def find_latex_engine_in_common_locations(
    engine: str,
    custom_path: str,
    additional_search_paths: Iterable[str],
    logger: logging.Logger,
) -> Optional[str]:
    """Return the first usable engine path discovered on a Windows host."""

    if platform.system() != 'Windows':
        return None

    username = os.environ.get('USERNAME', '')

    if custom_path:
        logger.info("Checking custom MiKTeX path: %s", custom_path)
        path = _engine_path(custom_path, engine)
        if path:
            return path
        logger.warning("Custom MiKTeX path doesn't exist: %s", custom_path)

    common_paths = [
        f"C:\\Users\\{username}\\AppData\\Local\\Programs\\MiKTeX 25.3\\miktex\\bin\\x64",
        f"C:\\Program Files\\MiKTeX 25.3\\miktex\\bin\\x64",
        f"C:\\Users\\{username}\\AppData\\Local\\Programs\\MiKTeX\\miktex\\bin\\x64",
        f"C:\\Users\\{username}\\AppData\\Local\\MiKTeX\\miktex\\bin\\x64",
        f"C:\\Program Files\\MiKTeX\\miktex\\bin\\x64",
        f"C:\\Program Files (x86)\\MiKTeX\\miktex\\bin",
        "C:\\texlive\\2023\\bin\\win32",
        "C:\\texlive\\2024\\bin\\win32",
        "C:\\texlive\\2023\\bin\\x64",
        "C:\\texlive\\2024\\bin\\x64",
    ]

    additional = list(additional_search_paths or [])
    if additional:
        logger.info("Adding %s additional search paths from config", len(additional))
        common_paths.extend(additional)

    for base_path in common_paths:
        path = _engine_path(base_path, engine)
        if path:
            return path

    return None


def _engine_path(base_path: str, engine: str) -> Optional[str]:
    engine_path = os.path.join(base_path, f"{engine}.exe")
    if not os.path.exists(engine_path) or not os.path.isfile(engine_path):
        return None

    print(f"Found LaTeX engine '{engine}' at {engine_path}")

    try:
        startupinfo = _windows_startupinfo()
        result = subprocess.run(
            [engine_path, '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            version_info = result.stdout.strip().split('\n')[0] if result.stdout else "Unknown version"
            print(f"Successfully tested LaTeX engine: {version_info}")
            return engine_path
    except Exception as exc:  # pragma: no cover - defensive: subprocess failures reported via print
        print(f"Error testing LaTeX engine at {engine_path}: {exc}")
    return None


def _windows_startupinfo() -> Optional[subprocess.STARTUPINFO]:  # type: ignore[name-defined]
    if hasattr(subprocess, 'STARTUPINFO'):
        startupinfo = subprocess.STARTUPINFO()
        if hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None
