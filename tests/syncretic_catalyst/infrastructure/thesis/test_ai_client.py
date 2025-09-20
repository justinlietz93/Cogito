from syncretic_catalyst.infrastructure.thesis.ai_client import OrchestratorContentGenerator


class StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def call_llm(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "max_tokens": max_tokens,
            }
        )
        return f"{system_prompt}::{user_prompt}::{max_tokens}"


def test_generate_uses_override_tokens_when_provided() -> None:
    orchestrator = StubOrchestrator()
    generator = OrchestratorContentGenerator(orchestrator, default_max_tokens=8000)

    result = generator.generate(system_prompt="sys", user_prompt="usr", max_tokens=1234)

    assert orchestrator.calls == [
        {"system_prompt": "sys", "user_prompt": "usr", "max_tokens": 1234}
    ]
    assert result == "sys::usr::1234"


def test_generate_falls_back_to_default_when_zero_passed() -> None:
    orchestrator = StubOrchestrator()
    generator = OrchestratorContentGenerator(orchestrator, default_max_tokens=2048)

    generator.generate(system_prompt="system", user_prompt="prompt", max_tokens=0)

    assert orchestrator.calls[0]["max_tokens"] == 2048
