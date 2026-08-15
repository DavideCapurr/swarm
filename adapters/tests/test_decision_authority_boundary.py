from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_ROOT = ROOT / "adapters"
FORBIDDEN_IMPORT_TOKENS = (
    "from swarm_core.allocator",
    "import swarm_core.allocator",
    "from swarm_os.autonomy",
    "import swarm_os.autonomy",
    "from swarm_os.command_bus",
    "import swarm_os.command_bus",
    "from swarm_os.scheduler",
    "import swarm_os.scheduler",
    "from orchestrator.swarm_orchestrator.service",
    "import orchestrator.swarm_orchestrator.service",
    "from orchestrator.swarm_orchestrator.presence_bus",
    "import orchestrator.swarm_orchestrator.presence_bus",
)


def test_physical_agent_adapters_cannot_import_decision_authority() -> None:
    adapter_paths = sorted(ADAPTER_ROOT.glob("*/adapter.py"))
    assert adapter_paths, "expected at least one physical-agent adapter implementation"

    violations = [
        f"{path.relative_to(ROOT)} contains {token!r}"
        for path in adapter_paths
        for token in FORBIDDEN_IMPORT_TOKENS
        if token in path.read_text(encoding="utf-8")
    ]

    assert not violations, (
        "Physical-agent adapters are thin executors. Mission allocation, "
        "autonomy, scheduling and peer coordination must remain in SwarmOS:\n"
        + "\n".join(violations)
    )
