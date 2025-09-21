"""Integration tests verifying CLI preflight artefact persistence.

Purpose:
    Ensure the console application writes structured extraction and query plan
    artefacts when the corresponding preflight flags are enabled. The tests use
    real CLI wiring with stubbed gateways to validate schema compliance without
    invoking external providers.
External Dependencies:
    Relies on :mod:`pytest` and Python's standard library (``pathlib`` and
    ``types``). All application imports originate from the repository under
    test.
Fallback Semantics:
    Gateway and orchestrator stubs provide deterministic responses so the CLI
    behaviour can be exercised without retries or network fallbacks.
Timeout Strategy:
    Not applicable. The tests perform synchronous filesystem operations within
    pytest-managed temporary directories.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Tuple

import pytest

from src.application.critique.services import CritiqueRunner
from src.application.preflight.extraction_parser import ExtractionResponseParser
from src.application.preflight.orchestrator import PreflightOptions, PreflightRunResult
from src.application.preflight.query_parser import QueryPlanResponseParser
from src.domain.preflight import BuiltQuery, ExtractionResult, ExtractedPoint, QueryPlan
from src.domain.user_settings.models import UserSettings
from src.infrastructure.io.file_repository import FileSystemContentRepositoryFactory
from src.pipeline_input import PipelineInput
from src.presentation.cli.app import CliApp
from src.presentation.cli.preflight import PreflightCliDefaults

pytestmark = pytest.mark.integration


class _StubSettingsService:
    """In-memory settings service tailored for CLI integration scenarios."""

    def __init__(self) -> None:
        self._settings = UserSettings()
        self.recorded: List[str] = []
        self.saved_outputs: List[Optional[str]] = []

    def get_settings(self) -> UserSettings:
        """Return mutable user settings consumed by the CLI and runner."""

        return self._settings

    def record_recent_file(self, path: str) -> None:
        """Track recently accessed pipeline sources for assertions."""

        self.recorded.append(path)

    def set_default_output_dir(self, value: Optional[str]) -> None:
        """Store output directory preferences when the CLI requests persistence."""

        self.saved_outputs.append(value)
        self._settings.default_output_dir = value or None


class _StaticConfigBuilder:
    """Configuration builder that returns a static payload for tests."""

    def __init__(self, payload: Optional[dict[str, object]] = None) -> None:
        self._payload = payload or {"api": {"providers": {}}}

    def build(self) -> dict[str, object]:
        """Return a shallow copy of the configured payload."""

        return dict(self._payload)


class _StaticCritiqueGateway:
    """Gateway stub that records invocations and returns canned output."""

    def __init__(self) -> None:
        self.invocations: List[PipelineInput] = []

    def run(
        self,
        pipeline_input: PipelineInput,
        config: dict[str, object],
        peer_review: bool,
        scientific_mode: bool,
    ) -> str:
        """Record parameters and return a deterministic critique string."""

        self.invocations.append(pipeline_input)
        return "Rendered critique"


class _StubPreflightOrchestrator:
    """Deterministic orchestrator stub that emits predefined results."""

    def __init__(
        self,
        *,
        extraction: ExtractionResult | None = None,
        query_plan: QueryPlan | None = None,
    ) -> None:
        self._extraction = extraction
        self._query_plan = query_plan
        self.invocations: List[Tuple[PipelineInput, PreflightOptions]] = []

    def run(self, pipeline_input: PipelineInput, options: PreflightOptions) -> PreflightRunResult:
        """Return preconfigured artefacts while recording invocation metadata."""

        self.invocations.append((pipeline_input, options))
        artifact_paths: dict[str, str] = {}
        extraction = self._extraction if options.enable_extraction else None
        if extraction is not None and options.extraction_artifact_name:
            artifact_paths["extraction"] = options.extraction_artifact_name
        plan = self._query_plan if options.enable_query_building else None
        if plan is not None and options.query_artifact_name:
            artifact_paths["query_plan"] = options.query_artifact_name
        return PreflightRunResult(
            extraction=extraction,
            query_plan=plan,
            artifact_paths=artifact_paths,
        )


def _make_extraction_result() -> ExtractionResult:
    """Create a representative extraction result for CLI persistence tests."""

    point = ExtractedPoint(
        id="pt-001",
        title="Key observation",
        summary="Summarise the most critical insight discovered during review.",
        evidence_refs=("notes.md#L10",),
        confidence=0.9,
        tags=("research", "priority"),
    )
    return ExtractionResult(
        points=(point,),
        source_stats={"token_usage": 512},
        truncated=False,
    )


def _make_query_plan() -> QueryPlan:
    """Create a deterministic query plan payload for integration testing."""

    query = BuiltQuery(
        id="q-001",
        text="How will we extend coverage to related work?",
        purpose="Clarify the roadmap for subsequent critique stages.",
        priority=1,
        depends_on_ids=("pt-001",),
        target_audience="author",
        suggested_tooling=("search",),
    )
    return QueryPlan(
        queries=(query,),
        rationale="Ensure upcoming analysis addresses outstanding questions.",
        assumptions=("Up-to-date bibliography",),
        risks=("Scope creep",),
    )


def _build_cli_args(
    input_source: PipelineInput,
    output_dir: Path,
    *,
    enable_extraction: bool,
    enable_query_building: bool,
    points_path: Optional[str] = None,
    queries_path: Optional[str] = None,
    max_points: Optional[int] = None,
    max_queries: Optional[int] = None,
) -> SimpleNamespace:
    """Construct a CLI namespace mirroring parsed arguments for tests."""

    return SimpleNamespace(
        input_file=input_source,
        input_dir=None,
        include=None,
        exclude=None,
        order=None,
        order_from=None,
        recursive=None,
        label_sections=None,
        max_files=None,
        max_chars=None,
        section_separator=None,
        output_dir=str(output_dir),
        peer_review=None,
        scientific_mode=None,
        latex=False,
        latex_compile=False,
        latex_output_dir=None,
        latex_scientific_level="high",
        direct_latex=False,
        remember_output=False,
        preflight_extract=enable_extraction,
        preflight_build_queries=enable_query_building,
        points_out=points_path,
        queries_out=queries_path,
        max_points=max_points,
        max_queries=max_queries,
        interactive_mode=None,
    )


def test_cli_preflight_extract_writes_schema_compliant_points(tmp_path: Path) -> None:
    """Verify ``--preflight-extract`` persists JSON matching the extraction schema."""

    settings_service = _StubSettingsService()
    repository_factory = FileSystemContentRepositoryFactory()
    orchestrator = _StubPreflightOrchestrator(extraction=_make_extraction_result())
    gateway = _StaticCritiqueGateway()
    runner = CritiqueRunner(
        settings_service,
        _StaticConfigBuilder(),
        gateway,
        repository_factory,
        preflight_orchestrator=orchestrator,
    )
    defaults = PreflightCliDefaults(
        extract_enabled=False,
        query_enabled=False,
        points_artifact="points.json",
        queries_artifact="queries.json",
    )
    app = CliApp(
        settings_service,
        runner,
        preflight_defaults=defaults,
        output_func=lambda _: None,
    )
    pipeline_input = PipelineInput(content="Body", metadata={"source_path": "notes.md"})
    args = _build_cli_args(
        pipeline_input,
        tmp_path,
        enable_extraction=True,
        enable_query_building=False,
    )

    app.run(args, interactive=False)

    points_path = tmp_path / "points.json"
    assert points_path.exists(), "expected extraction artefact to be written"
    payload = points_path.read_text(encoding="utf-8")
    parser = ExtractionResponseParser()
    result = parser.parse(payload)
    assert not result.validation_errors
    assert result.model is not None
    assert result.model.points and result.model.points[0].title == "Key observation"
    assert orchestrator.invocations, "preflight orchestrator should be invoked"
    _invocation_input, options = orchestrator.invocations[0]
    assert options.enable_extraction is True
    assert options.enable_query_building is False
    assert "preflight_artifacts" in pipeline_input.metadata
    assert pipeline_input.metadata["preflight_artifacts"]["extraction"] == str(points_path)


def test_cli_preflight_query_writes_schema_compliant_plan(tmp_path: Path) -> None:
    """Verify ``--preflight-build-queries`` emits a query plan artefact."""

    settings_service = _StubSettingsService()
    repository_factory = FileSystemContentRepositoryFactory()
    orchestrator = _StubPreflightOrchestrator(
        extraction=_make_extraction_result(),
        query_plan=_make_query_plan(),
    )
    gateway = _StaticCritiqueGateway()
    runner = CritiqueRunner(
        settings_service,
        _StaticConfigBuilder(),
        gateway,
        repository_factory,
        preflight_orchestrator=orchestrator,
    )
    defaults = PreflightCliDefaults(
        extract_enabled=False,
        query_enabled=False,
        points_artifact="points.json",
        queries_artifact="queries.json",
    )
    app = CliApp(
        settings_service,
        runner,
        preflight_defaults=defaults,
        output_func=lambda _: None,
    )
    pipeline_input = PipelineInput(content="Body", metadata={"source_path": "notes.md"})
    args = _build_cli_args(
        pipeline_input,
        tmp_path,
        enable_extraction=True,
        enable_query_building=True,
        queries_path="custom_queries.json",
    )

    app.run(args, interactive=False)

    points_path = tmp_path / "points.json"
    assert points_path.exists(), "extraction artefact should accompany query planning"
    queries_path = tmp_path / "custom_queries.json"
    assert queries_path.exists(), "expected query plan artefact to be written"
    parser = QueryPlanResponseParser()
    plan_result = parser.parse(queries_path.read_text(encoding="utf-8"))
    assert not plan_result.validation_errors
    assert plan_result.model is not None
    assert plan_result.model.queries and plan_result.model.queries[0].text.startswith("How will we extend")
    assert orchestrator.invocations, "preflight orchestrator should record invocations"
    _invocation_input, options = orchestrator.invocations[0]
    assert options.enable_extraction is True
    assert options.enable_query_building is True
    metadata = pipeline_input.metadata.get("preflight_artifacts", {})
    assert metadata["extraction"] == str(points_path)
    assert metadata["query_plan"] == str(queries_path)
