import pytest

import syncretic_catalyst.ai_clients as ai_clients


@pytest.fixture(autouse=True)
def reset_primary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_clients, "PRIMARY_PROVIDER", "anthropic")


@pytest.mark.parametrize(
    "model_name, module_attr, function_name",
    [
        ("claude37sonnet", "anthropic_client", "run_anthropic_client"),
        ("deepseek", "deepseek_client", "run_deepseek_client"),
        ("openai", "openai_client", "run_openai_client"),
        ("gemini", "gemini_client", "run_gemini_client"),
    ],
)
def test_call_llm_routes_to_expected_provider(
    monkeypatch: pytest.MonkeyPatch,
    model_name: str,
    module_attr: str,
    function_name: str,
) -> None:
    module = getattr(ai_clients, module_attr)
    calls: list[dict[str, object]] = []

    def fake_run(*, messages, max_tokens, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"messages": messages, "max_tokens": max_tokens, "extra": kwargs})
        return f"{module_attr}-response"

    monkeypatch.setattr(module, function_name, fake_run)

    orchestrator = ai_clients.AIOrchestrator(model_name=model_name)
    result = orchestrator.call_llm("system", "user", max_tokens=321, step_number=7)

    assert result == f"{module_attr}-response"
    assert calls[0]["max_tokens"] == 321
    assert calls[0]["messages"][0]["content"] == "system"
    assert calls[0]["messages"][1]["content"] == "user"


def test_unknown_model_falls_back_to_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_clients, "PRIMARY_PROVIDER", "gemini")

    captured: list[dict[str, object]] = []

    def fake_run(*, messages, max_tokens, **kwargs):  # type: ignore[no-untyped-def]
        captured.append({"messages": messages, "max_tokens": max_tokens})
        return "gemini-response"

    monkeypatch.setattr(ai_clients.gemini_client, "run_gemini_client", fake_run)

    orchestrator = ai_clients.AIOrchestrator(model_name="mystery")
    assert orchestrator.provider == "gemini"

    result = orchestrator.call_llm("sys", "prompt", max_tokens=999, step_number=2)
    assert result == "gemini-response"
    assert captured and captured[0]["max_tokens"] == 999


def test_call_llm_returns_error_when_provider_unknown() -> None:
    orchestrator = ai_clients.AIOrchestrator(model_name="openai")
    orchestrator.provider = "unexpected"

    result = orchestrator.call_llm("sys", "prompt")

    assert result == "Unknown provider: unexpected"
