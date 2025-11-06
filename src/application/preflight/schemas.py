"""Utility helpers for loading preflight JSON Schemas from disk.

Purpose:
    Centralise loading of the JSON Schema documents used for preflight
    extraction and query planning so application services can embed them in
    prompts and validators without duplicating path logic.
External Dependencies:
    Python standard library only (``functools`` and ``json``).
Fallback Semantics:
    Schema loading is deterministic and raises ``FileNotFoundError`` if assets are
    missing. Callers may catch and handle these exceptions depending on their
    resiliency requirements.
Timeout Strategy:
    Not applicable because the module performs synchronous file reads on local
    assets.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Mapping
from copy import deepcopy


_SCHEMA_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "contexts" / "schemas"


def _load_schema(filename: str) -> Mapping[str, object]:
    """Load a JSON Schema document from the schema directory."""

    path = _SCHEMA_DIRECTORY / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=2)
def _load_cached_schema(filename: str) -> Mapping[str, object]:
    """Load and cache the schema contents for reuse across the process."""

    return _load_schema(filename)


def load_extraction_schema() -> Mapping[str, object]:
    """Return the schema for the :class:`~src.domain.preflight.ExtractionResult`.

    Returns:
        Copy of the JSON Schema mapping describing the extraction result
        structure.

    Raises:
        FileNotFoundError: If the schema asset cannot be located.
        json.JSONDecodeError: If the schema file cannot be parsed as JSON.

    Side Effects:
        Reads the schema file from disk.

    Timeout:
        Not applicable; file access is local and synchronous.
    """

    return deepcopy(_load_cached_schema("extraction.schema.json"))


def load_query_plan_schema() -> Mapping[str, object]:
    """Return the schema for the :class:`~src.domain.preflight.QueryPlan`.

    Returns:
        Copy of the JSON Schema mapping describing the query plan structure.

    Raises:
        FileNotFoundError: If the schema asset cannot be located.
        json.JSONDecodeError: If the schema file is not valid JSON.

    Side Effects:
        Reads the schema file from disk.

    Timeout:
        Not applicable; reading the local file is synchronous.
    """

    return deepcopy(_load_cached_schema("query_plan.schema.json"))


__all__ = ["load_extraction_schema", "load_query_plan_schema"]
