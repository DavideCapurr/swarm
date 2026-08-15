from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ROOT = ROOT / "adapters"

# Physical-agent adapters translate SWARM-issued commands and report state.
# Importing any of these modules would move mission-level decision authority
# across that boundary and violate ADR 0011.
FORBIDDEN_DECISION_MODULES = (
    "swarm_core.allocator",
    "swarm_os.autonomy",
    "swarm_os.command_bus",
    "swarm_os.scheduler",
    "orchestrator.swarm_orchestrator.service",
    "orchestrator.swarm_orchestrator.presence_bus",
)


def _adapter_implementations() -> list[Path]:
    return sorted(ADAPTER_ROOT.glob("*/adapter.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imported


def test_physical_agent_adapters_cannot_import_decision_authority() -> None:
    adapters = _adapter_implementations()
    assert adapters, "expected at least one physical-agent adapter implementation"

    violations: list[str] = []
    for path in adapters:
        for imported in _imports(path):
            if any(
                imported == forbidden or imported.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_DECISION_MODULES
            ):
                violations.append(
                    f"{path.relative_to(ROOT)} imports decision module {imported}"
                )

    assert not violations, (
        "Physical-agent adapters are thin executors. Mission allocation, "
        "autonomy, scheduling and peer coordination must remain in SwarmOS:\n"
        + "\n".join(violations)
    )
