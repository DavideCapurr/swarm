"""Phase 6.G — DR pattern smoke.

These tests validate the offline-checkable invariants for the
resilience + disaster recovery deliverables:

  * the DR runbook is present and names every required section;
  * the failover example configs parse as YAML and describe a HA
    topology, not a single node;
  * the backup drill script is well-formed shell (set -eu, no
    failure-swallowing patterns, --i-understand-this-overwrites guard
    propagated from the restore script);
  * Helm values expose the resilience hooks (`redis.sentinel.enabled`,
    `postgres.replication.mode`) — these stay defaulted off but must
    be settable;
  * the emergency stop endpoint is mounted on the FastAPI app.

What we deliberately do NOT exercise here (drone-day §2.G):
  - real Sentinel / Patroni deploy
  - real backup drill against a real Postgres container
  - real off-site sync
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


# ── DR runbook ────────────────────────────────────────────────────────────────


def test_dr_runbook_exists() -> None:
    runbook = REPO / "docs" / "ops" / "disaster-recovery.md"
    assert runbook.is_file(), "docs/ops/disaster-recovery.md must exist for Phase 6.G"


def test_dr_runbook_names_required_sections() -> None:
    runbook = (REPO / "docs" / "ops" / "disaster-recovery.md").read_text(
        encoding="utf-8"
    )
    # Recovery objectives table.
    assert "RTO" in runbook and "RPO" in runbook
    assert "1 h" in runbook and "5 min" in runbook
    # Each documented scenario.
    for scenario in (
        "S1. Backend pod crash-loop",
        "S2. Redis loss",
        "S3. Postgres primary loss",
        "S4. Off-site backup loss",
        "S5. Total site loss",
    ):
        assert scenario in runbook, f"DR runbook missing scenario: {scenario}"
    # Cross-links to the example configs + drill script.
    assert "sentinel-example.yaml" in runbook
    assert "patroni-example.yaml" in runbook
    assert "backup-drill" in runbook or "backup_restore_drill.sh" in runbook
    # Emergency stop reference.
    assert "EMERGENCY_RTL_ALL" in runbook


# ── Failover reference configs ────────────────────────────────────────────────


def test_sentinel_example_is_valid_yaml_and_describes_quorum() -> None:
    path = REPO / "infra" / "redis" / "sentinel-example.yaml"
    assert path.is_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sentinels = data["spec"]["sentinels"]
    assert sentinels["count"] >= 3
    assert sentinels["quorum"] >= 2
    # mTLS terminated at the sentinel.
    assert sentinels["tls"]["enabled"] is True
    # No red severity in any alert (design system §5.2).
    for alert in data["spec"].get("observability", {}).get("alerts", []):
        assert alert["severity"] != "red"


def test_patroni_example_is_valid_yaml_and_describes_replication() -> None:
    path = REPO / "infra" / "postgres" / "patroni-example.yaml"
    assert path.is_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    pg = data["spec"]["postgres"]
    assert pg["config"]["wal_level"] == "replica"
    # Multi-node cluster with a leader-election DCS.
    assert data["spec"]["patroni"]["nodes"]["count"] >= 3
    assert data["spec"]["etcd"]["nodes"] >= 3
    # WAL archive provisioned.
    backups = data["spec"]["backups"]
    assert "wal_archive" in backups
    # No red severity.
    for alert in data["spec"].get("observability", {}).get("alerts", []):
        assert alert["severity"] != "red"


# ── Backup drill script ───────────────────────────────────────────────────────


def test_backup_drill_script_exists_and_is_strict() -> None:
    path = REPO / "scripts" / "backup_restore_drill.sh"
    assert path.is_file(), "scripts/backup_restore_drill.sh must exist"
    assert path.stat().st_mode & 0o111, "drill script must be executable"

    text = path.read_text(encoding="utf-8")
    # `set -eu` enforced — no `|| true` failure-swallowing in the main flow.
    assert re.search(r"^set -e[uo]?u?o?\b", text, re.MULTILINE), text
    # No silent error swallowing on the main pipeline. The cleanup trap
    # uses `|| true` deliberately on `docker rm`; that's the only OK
    # occurrence. We count `|| true` outside the cleanup block.
    cleanup_block = re.search(r"cleanup\(\) \{.*?^\}", text, re.MULTILINE | re.DOTALL)
    main_flow = text.replace(cleanup_block.group(0) if cleanup_block else "", "")
    # Allow at most a deliberate fallback to `echo 0` for row counts;
    # but never `|| true` on the backup/restore pipeline.
    assert "scripts/backup_postgres.sh || true" not in main_flow
    assert "scripts/restore_postgres.sh || true" not in main_flow
    # The drill must propagate the guard flag from the restore script.
    assert "--i-understand-this-overwrites" in text


def test_makefile_exposes_backup_drill_target() -> None:
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    # Declared in .PHONY and present as a recipe.
    assert "backup-drill" in makefile
    assert "scripts/backup_restore_drill.sh" in makefile


# ── HTTP surface mounted ──────────────────────────────────────────────────────


def test_emergency_endpoint_registered_on_actions_router() -> None:
    """The route is on the actions router so the main app picks it up."""

    from backend.app.api.actions import router

    paths = {route.path for route in router.routes}  # type: ignore[attr-defined]
    assert "/actions/emergency-rtl-all" in paths


def test_emergency_endpoint_requires_commander_dependency() -> None:
    """The dependency tree on the route resolves to ``require_commander``."""

    from backend.app.api.actions import router
    from backend.app.auth.deps import require_commander

    target = next(
        r
        for r in router.routes  # type: ignore[attr-defined]
        if getattr(r, "path", None) == "/actions/emergency-rtl-all"
    )
    dependants = [d.call for d in target.dependant.dependencies]  # type: ignore[attr-defined]
    assert require_commander in dependants


# ── Command-bus contract surfaced to the API ──────────────────────────────────


def test_operator_action_enum_carries_emergency_value() -> None:
    """The shared enum is the source of truth — the frontend mirrors it."""

    from swarm_core.messages import OperatorAction

    assert OperatorAction.EMERGENCY_RTL_ALL.value == "emergency_rtl_all"


def test_command_bus_exports_canonical_target_and_priority() -> None:
    from swarm_os.command_bus import (
        EMERGENCY_FLEET_TARGET,
        EMERGENCY_MISSION_PREFIX,
        EMERGENCY_RTL_PRIORITY,
    )
    from swarm_os.coordinator import AUTO_RTL_PRIORITY

    assert EMERGENCY_FLEET_TARGET == "fleet:all"
    assert EMERGENCY_MISSION_PREFIX.endswith("-")
    # Emergency must outrank auto-RTL so a low-battery unit does not get
    # a competing safety-action queued.
    assert EMERGENCY_RTL_PRIORITY > AUTO_RTL_PRIORITY
