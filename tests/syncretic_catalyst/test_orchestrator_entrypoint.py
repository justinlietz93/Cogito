from syncretic_catalyst import orchestrator
from syncretic_catalyst.presentation import cli


def test_orchestrator_reexports_cli_main() -> None:
    assert orchestrator.main is cli.main
