from __future__ import annotations

from typing import Dict, Any

import pytest

from src.latex.processors.content_processor import ContentProcessor
from src.latex.processors.jargon_processor import JargonProcessor


class DummyProcessor(ContentProcessor):
    def process(self, content: str, context: Dict[str, Any] | None = None) -> str:
        return content.upper()

    @property
    def name(self) -> str:  # pragma: no cover - simple alias
        return "dummy"


def test_content_processor_defaults() -> None:
    processor = DummyProcessor()
    assert processor.description == "Base content processor"
    assert processor.supports_content_type("anything") is True
    assert processor.process("abc") == "ABC"
    assert ContentProcessor.description.fget(processor) == "Base content processor"
    assert ContentProcessor.supports_content_type(processor, "ignored") is True
    assert super(DummyProcessor, processor).description == "Base content processor"
    assert super(DummyProcessor, processor).supports_content_type("ignored") is True
    assert ContentProcessor.process(processor, "content") is None
    assert super(DummyProcessor, processor).name is None


@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_jargon_processor_replacements(level: str) -> None:
    processor = JargonProcessor(objectivity_level=level)
    text = "Aristotelian perspective. I believe noumena exist."
    result = processor.process(text)
    assert "functional systems analysis" in result or level == "low"
    assert "noumena" not in result or level == "low"


def test_jargon_processor_respects_context_override() -> None:
    processor = JargonProcessor(objectivity_level="low")
    text = "I note that teleology is central."
    result = processor.process(text, context={"scientific_objectivity_level": "high"})
    assert "It is noteworthy" in result
    assert "functional outcome" in result


def test_jargon_processor_metadata_properties() -> None:
    processor = JargonProcessor()

    assert processor.name == "jargon_processor"
    assert processor.description == "Replaces philosophical jargon with scientific terminology"
