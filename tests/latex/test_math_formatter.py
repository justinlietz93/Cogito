from __future__ import annotations

import pytest

from src.latex.converters import math_formatter as math_module
from src.latex.converters.math_formatter import MathFormatter


def test_format_preserves_environments_and_converts_symbols() -> None:
    formatter = MathFormatter()
    source = (
        "\\begin{equation}E = mc^2\\end{equation}\n"
        "$a/b$ and $x^10$"
    )

    result = formatter.format(source)

    assert "\\begin{equation}" in result  # preserved
    assert "\\frac{a}{b}" in result
    assert "x^{10}" in result


def test_format_applies_notation_with_parenthetical_markers() -> None:
    formatter = MathFormatter()
    source = "√ and ∑"

    formatted = formatter.format(source)
    assert formatted == source


def test_format_continues_when_helpers_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    formatter = MathFormatter()

    def _raise(*_: object, **__: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(formatter, "_replace_in_math", _raise)
    monkeypatch.setattr(formatter, "_replace_in_math_regex", _raise)

    output = formatter.format("Text without math")
    assert output == "Text without math"


def test_format_logs_when_regex_replacement_fails(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    formatter = MathFormatter()
    call_count = {"value": 0}
    original_sub = math_module.re.sub

    def flaky_sub(pattern, repl, string, *args, **kwargs):  # type: ignore[override]
        if call_count["value"] == 0:
            call_count["value"] += 1
            raise RuntimeError("bad pattern")
        return original_sub(pattern, repl, string, *args, **kwargs)

    monkeypatch.setattr(math_module.re, "sub", flaky_sub)

    formatter.format("$x$")
    out, _ = capsys.readouterr()
    assert "Error in math pattern replacement" in out

    monkeypatch.setattr(math_module.re, "sub", original_sub)


def test_replace_in_math_regex_handles_environments() -> None:
    formatter = MathFormatter()
    content = "\\begin{equation}a/b\\end{equation}"

    replaced = formatter._replace_in_math_regex(content, r"(a)/(b)", r"\\frac{\\1}{\\2}")

    assert "\\frac" in replaced


def test_replace_in_math_handles_display_blocks() -> None:
    formatter = MathFormatter()
    content = "Start $$a+b$$ end"

    replaced = formatter._replace_in_math(content, "+", "×")

    assert "Start " in replaced
    assert "$$a×b$$" in replaced


def test_replace_in_math_regex_handles_display_blocks() -> None:
    formatter = MathFormatter()
    content = "$$a<=b$$"

    replaced = formatter._replace_in_math_regex(content, r"<=", r"\\leq")

    assert "\\leq" in replaced
    assert replaced.startswith("$$") and replaced.endswith("$$")


def test_replace_in_math_only_updates_math_blocks() -> None:
    formatter = MathFormatter()
    content = "Value ≤ threshold and $x ≤ y$"

    replaced = formatter._replace_in_math(content, "≤", "\\leq")

    assert "Value ≤ threshold" in replaced
    assert "$x \\le" in replaced


def test_format_returns_original_on_critical_error(monkeypatch: pytest.MonkeyPatch) -> None:
    formatter = MathFormatter()

    monkeypatch.setattr(formatter, "_preserve_existing_environments", lambda _content: (_ for _ in ()).throw(RuntimeError("boom")))

    result = formatter.format("Plain text")
    assert result == "Plain text"
