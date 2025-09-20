from syncretic_catalyst.application.framework import build_breakthrough_steps


def test_build_breakthrough_steps_returns_ordered_framework() -> None:
    steps = build_breakthrough_steps()

    assert steps
    indices = [step.index for step in steps]
    assert indices == sorted(indices)
    assert steps[0].phase_name.startswith("1)")
    assert all(step.user_prompt_template for step in steps)
