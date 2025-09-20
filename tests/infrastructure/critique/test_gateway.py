from src.infrastructure.critique.gateway import ModuleCritiqueGateway


def test_module_gateway_invokes_goal(monkeypatch) -> None:
    captured = {}

    def fake_goal(input_data, config, peer_review, scientific_mode):
        captured["args"] = (input_data, config, peer_review, scientific_mode)
        return "result"

    monkeypatch.setattr("src.infrastructure.critique.gateway.critique_goal_document", fake_goal)

    gateway = ModuleCritiqueGateway()
    outcome = gateway.run("data", {"option": True}, True, False)

    assert outcome == "result"
    assert captured["args"] == ("data", {"option": True}, True, False)
