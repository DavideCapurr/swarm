from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_DECISION_MODULES = (
    "swarm_core.allocator",
    "swarm_os",
    "orchestrator.swarm_orchestrator.service",
    "orchestrator.swarm_orchestrator.bus_fleet",
    "orchestrator.swarm_orchestrator.presence_bus",
)


def _physical_execution_adapter_paths() -> list[Path]:
    return [
        ROOT / "adapters" / "base.py",
        *sorted((ROOT / "adapters").glob("*/adapter.py")),
    ]


def test_physical_execution_adapters_cannot_import_decision_authority() -> None:
    adapter_paths = _physical_execution_adapter_paths()
    assert len(adapter_paths) > 1

    for path in adapter_paths:
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_DECISION_MODULES:
            assert f"from {module}" not in source
            assert f"import {module}" not in source


def test_physical_execution_adapters_cannot_emit_bidding_as_progress() -> None:
    for path in _physical_execution_adapter_paths():
        source = path.read_text(encoding="utf-8")
        assert 'phase="BIDDING"' not in source
        assert "phase='BIDDING'" not in source
