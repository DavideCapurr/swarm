# ruff: noqa: I001
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_DECISION_MODULES = (
    "swarm_core.allocator",
    "swarm_os.autonomy",
    "swarm_os.command_bus",
    "swarm_os.scheduler",
    "orchestrator.swarm_orchestrator.service",
    "orchestrator.swarm_orchestrator.presence_bus",
)


def test_physical_agent_adapters_cannot_import_decision_authority() -> None:
    adapter_paths = sorted((ROOT / "adapters").glob("*/adapter.py"))
    assert adapter_paths

    for path in adapter_paths:
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_DECISION_MODULES:
            assert f"from {module}" not in source
            assert f"import {module}" not in source
