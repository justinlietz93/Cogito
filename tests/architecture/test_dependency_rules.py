"""Static dependency checks enforcing clean architecture boundaries.

Purpose:
    Validate import statements to ensure inner layers remain free of outer-layer dependencies.
External Dependencies:
    Python standard library only.
Fallback Semantics:
    None; tests fail immediately when violations are detected.
Timeout Strategy:
    Not applicable.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def _collect_forbidden_imports(directory: Path, prefixes: Tuple[str, ...]) -> list[tuple[Path, str]]:
    """Return imports within ``directory`` that target forbidden prefixes."""

    violations: list[tuple[Path, str]] = []
    for path in directory.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(prefixes):
                        violations.append((path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(prefixes):
                    violations.append((path, module))
    return violations


def test_application_layer_does_not_depend_on_outer_layers() -> None:
    """Ensure application modules avoid importing presentation or infrastructure."""

    application_dir = SRC_ROOT / "application"
    forbidden = ("src.presentation", "src.infrastructure")
    violations = _collect_forbidden_imports(application_dir, forbidden)

    assert not violations, f"Application layer has forbidden imports: {violations}"


def test_domain_layer_remains_isolated() -> None:
    """Ensure domain modules do not import application, infrastructure, or presentation."""

    domain_dir = SRC_ROOT / "domain"
    forbidden = ("src.application", "src.infrastructure", "src.presentation")
    violations = _collect_forbidden_imports(domain_dir, forbidden)

    assert not violations, f"Domain layer has forbidden imports: {violations}"
