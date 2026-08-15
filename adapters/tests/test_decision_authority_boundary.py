from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_DECISION_MODULES = (
    "swarm_core.allocator",
    "swarm_os",
    "orchestrator.swarm_orchestrator.service",
    "orchestrator.swarm_orchestrator.bus_fleet",
    "orchestrator.swarm_orchestrator.presence_bus",
)


def _production_adapter_paths() -> list[Path]:
    return sorted(
        path
        for path in (ROOT / "adapters").rglob("*.py")
        if "tests" not in path.parts
    )


def test_physical_agent_layer_cannot_import_decision_authority() -> None:
    adapter_paths = _production_adapter_paths()
    assert adapter_paths

    for path in adapter_paths:
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_DECISION_MODULES:
            assert f"from {module}" not in source
            assert f"import {module}" not in source


def test_physical_agent_layer_cannot_emit_bidding_as_execution_progress() -> None:
    adapter_paths = _production_adapter_paths()
    assert adapter_paths

    for path in adapter_paths:
        source = path.read_text(encoding="utf-8")
        assert 'phase="BIDDING"' not in source
        assert "phase='BIDDING'" not in source
