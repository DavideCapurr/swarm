from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORT_PREFIXES = (
    "swarm_core.allocator",
    "swarm_os",
    "orchestrator",
)


def test_physical_agent_layer_cannot_import_decision_authority() -> None:
    adapter_paths = sorted(
        path
        for path in (ROOT / "adapters").rglob("*.py")
        if "tests" not in path.parts
    )
    assert adapter_paths

    for path in adapter_paths:
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_IMPORT_PREFIXES:
            assert f"from {module}" not in source
            assert f"import {module}" not in source
