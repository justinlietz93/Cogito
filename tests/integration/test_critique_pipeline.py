"""High-level integration tests for the critique pipeline entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.main import critique_goal_document
from src.pipeline_input import PipelineInput


def test_pipeline_handles_mapping_inputs_and_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mappings should convert into pipeline inputs and respect execution flags."""

    captured: Dict[str, Any] = {}

    def fake_run_council(pipeline_input: PipelineInput, *, config: Dict[str, Any], peer_review: bool, scientific_mode: bool):
        captured["pipeline_input"] = pipeline_input
        captured["config"] = config
        captured["flags"] = (peer_review, scientific_mode)
        return {"final_assessment": "ok"}

    def fake_format(result: Dict[str, Any], original_content: str, config: Dict[str, Any], *, peer_review: bool) -> str:
        captured["format_args"] = (result, original_content, config, peer_review)
        return "formatted"

    monkeypatch.setattr("src.main.run_critique_council", fake_run_council)
    monkeypatch.setattr("src.main.format_critique_output", fake_format)

    config = {"cli": {"theme": "dark"}}
    result = critique_goal_document(
        {"content": "Hello world", "source": "user", "extra": "metadata"},
        config=config,
        peer_review=True,
        scientific_mode=True,
    )

    assert result == "formatted"
    pipeline_input = captured["pipeline_input"]
    assert isinstance(pipeline_input, PipelineInput)
    assert pipeline_input.content == "Hello world"
    assert pipeline_input.source == "user"
    assert pipeline_input.metadata["extra"] == "metadata"
    assert captured["flags"] == (True, True)
    assert captured["config"] == config
    formatted_result, original_content, formatted_config, formatted_peer_review = captured["format_args"]
    assert formatted_result == {"final_assessment": "ok"}
    assert original_content == "Hello world"
    assert formatted_config == config
    assert formatted_peer_review is True


def test_pipeline_accepts_pipeline_input_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supplying a PipelineInput instance should avoid unnecessary re-wrapping."""

    provided = PipelineInput(content="Direct", source="memory", metadata={"origin": "prebuilt"})
    captured: Dict[str, Any] = {}

    def fake_run_council(pipeline_input: PipelineInput, *, config: Dict[str, Any], peer_review: bool, scientific_mode: bool):
        captured["pipeline_input"] = pipeline_input
        return {"final_assessment": "ok"}

    monkeypatch.setattr("src.main.run_critique_council", fake_run_council)
    monkeypatch.setattr("src.main.format_critique_output", lambda *args, **__: "formatted")

    critique_goal_document(provided)

    assert captured["pipeline_input"] is provided


def test_pipeline_does_not_mutate_external_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Downstream mutations should not leak back into the caller's configuration."""

    config: Dict[str, Any] = {"api": {"providers": {}}, "tracking": {}}

    def fake_run_council(pipeline_input: PipelineInput, *, config: Dict[str, Any], peer_review: bool, scientific_mode: bool):
        config["injected"] = True
        return {"final_assessment": "ok"}

    monkeypatch.setattr("src.main.run_critique_council", fake_run_council)
    monkeypatch.setattr("src.main.format_critique_output", lambda *args, **__: "formatted")

    critique_goal_document({"content": "Data"}, config=config)

    assert "injected" not in config
