"""Phase 7.E smoke tests for the `make demo-*` targets.

These tests don't boot Docker / sim / backend / frontend — they validate
the shape of the wiring that makes the three scenarios reproducible in
one command:

  * Makefile carries the three new targets and they invoke the
    parameterised scripts/demo_scenario.sh with the right YAML;
  * scripts/demo_scenario.sh is executable, fails-closed (set -euo
    pipefail, no `|| true` / `|| echo "continuing"` masks per
    CLAUDE.md §readiness check #3);
  * scripts/demo_wildfire.sh is the back-compat thin wrapper for
    `make demo`;
  * each referenced scenario YAML exists, parses, and opts into the
    autonomy baseline so the Phase 7 gate ("every autonomous decision
    is logged") fires;
  * scripts/scenario_metrics.py imports cleanly and exposes the
    expected CLI surface.

Real end-to-end validation is the manual gate in
`docs/plan/phase-7e.md` §Verifica.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
MAKEFILE = REPO_ROOT / "Makefile"

SCENARIOS = {
    "wildfire": REPO_ROOT / "sim" / "scenarios" / "wildfire_owner_land.yaml",
    "intrusion": REPO_ROOT / "sim" / "scenarios" / "intrusion_owner_land.yaml",
    "search": REPO_ROOT / "sim" / "scenarios" / "search_owner_land.yaml",
}


# ── Makefile wiring ─────────────────────────────────────────────────────────

def test_makefile_has_three_demo_targets() -> None:
    text = MAKEFILE.read_text()
    for tgt in ("demo-wildfire-sim", "demo-intrusion-sim", "demo-search-sim"):
        assert re.search(rf"^{re.escape(tgt)}:", text, re.MULTILINE), (
            f"Makefile missing target {tgt}"
        )


def test_makefile_demo_targets_point_to_correct_yamls() -> None:
    text = MAKEFILE.read_text()
    assert "demo_scenario.sh sim/scenarios/wildfire_owner_land.yaml" in text
    assert "demo_scenario.sh sim/scenarios/intrusion_owner_land.yaml" in text
    assert "demo_scenario.sh sim/scenarios/search_owner_land.yaml" in text


def test_makefile_phony_lists_new_targets() -> None:
    """If a `make demo-*` target shadows a real file (which it won't, but
    .PHONY still keeps make from skipping it on rare filesystems), the
    target won't run. Explicitly list each in .PHONY."""
    phony_line = MAKEFILE.read_text().splitlines()[0]
    assert phony_line.startswith(".PHONY:"), "first line of Makefile is not .PHONY"
    for tgt in ("demo-wildfire-sim", "demo-intrusion-sim", "demo-search-sim"):
        assert tgt in phony_line, f".PHONY missing {tgt}"


def test_demo_target_still_delegates_to_wildfire() -> None:
    """`make demo` is preserved as a quickstart hook in README — assert
    it still calls the back-compat wrapper."""
    text = MAKEFILE.read_text()
    # The `demo:` recipe sits between `.PHONY` and the next blank-line-
    # separated target; match the recipe body conservatively.
    m = re.search(r"^demo:\s*\n\t@?\./scripts/demo_wildfire\.sh", text, re.MULTILINE)
    assert m is not None, "`make demo` no longer calls scripts/demo_wildfire.sh"


# ── scripts/demo_scenario.sh ────────────────────────────────────────────────

def test_demo_scenario_script_executable() -> None:
    path = SCRIPTS / "demo_scenario.sh"
    assert path.exists(), "scripts/demo_scenario.sh missing"
    assert os.access(path, os.X_OK), "scripts/demo_scenario.sh is not executable"


def test_demo_scenario_script_fail_fast() -> None:
    text = (SCRIPTS / "demo_scenario.sh").read_text()
    assert text.startswith("#!/usr/bin/env bash"), "missing bash shebang"
    assert "set -euo pipefail" in text, "missing `set -euo pipefail`"
    # Anti-overreach: CLAUDE.md §readiness check #3 — failure-swallowing
    # patterns are blockers in dev scripts.
    forbidden = ("|| true", "|| echo \"continuing\"", "|| echo continuing", "--no-verify")
    for needle in forbidden:
        assert needle not in text, f"demo_scenario.sh contains forbidden pattern: {needle}"


def test_demo_scenario_script_dispatches_to_dev_up() -> None:
    text = (SCRIPTS / "demo_scenario.sh").read_text()
    assert "SIM_SCENARIO" in text, "SIM_SCENARIO must be exported for the runner"
    assert "scripts/dev_up.sh" in text, "must delegate boot to dev_up.sh"


def test_demo_scenario_metrics_optin_calls_collector() -> None:
    text = (SCRIPTS / "demo_scenario.sh").read_text()
    assert "--metrics" in text
    assert "scripts/scenario_metrics.py" in text


# ── scripts/demo_wildfire.sh (back-compat) ──────────────────────────────────

def test_demo_wildfire_is_thin_wrapper() -> None:
    path = SCRIPTS / "demo_wildfire.sh"
    assert path.exists(), "scripts/demo_wildfire.sh missing"
    assert os.access(path, os.X_OK), "scripts/demo_wildfire.sh is not executable"
    text = path.read_text()
    assert "demo_scenario.sh" in text
    assert "wildfire_owner_land.yaml" in text


# ── Scenario YAMLs ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("scenario_name,scenario_path", list(SCENARIOS.items()))
def test_scenario_yaml_exists_and_parses(scenario_name: str, scenario_path: Path) -> None:
    assert scenario_path.exists(), f"missing scenario YAML for {scenario_name}"
    payload = yaml.safe_load(scenario_path.read_text())
    assert isinstance(payload, dict), f"{scenario_path.name} did not parse to dict"


@pytest.mark.parametrize("scenario_name,scenario_path", list(SCENARIOS.items()))
def test_scenario_opts_into_autonomy_baseline(
    scenario_name: str, scenario_path: Path
) -> None:
    """The Phase 7 gate requires every autonomous decision to land in
    the audit log. That hinges on `autonomy_baseline: true` in the YAML
    (sim runner reads this and flips state.autonomy_enabled)."""
    payload = yaml.safe_load(scenario_path.read_text())
    assert payload.get("autonomy_baseline") is True, (
        f"{scenario_path.name} must set autonomy_baseline: true for the "
        f"`make demo-{scenario_name}-sim` gate"
    )


# ── scripts/scenario_metrics.py ─────────────────────────────────────────────

def test_scenario_metrics_script_executable() -> None:
    path = SCRIPTS / "scenario_metrics.py"
    assert path.exists(), "scripts/scenario_metrics.py missing"
    assert os.access(path, os.X_OK), "scripts/scenario_metrics.py is not executable"


def test_scenario_metrics_cli_smoke() -> None:
    """`--help` must exit 0 without requiring a running backend. This
    catches argparse / import-time regressions."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "scenario_metrics.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}: {result.stderr[:200]}"
    )
    out = result.stdout
    for flag in ("--scenario", "--duration", "--backend"):
        assert flag in out, f"--help output missing flag {flag}"


def test_scenario_metrics_artifact_path_isolated_to_docs_bench() -> None:
    """The collector writes under docs/bench/artifacts/ only; assert the
    path constant in the module to keep that contract explicit."""
    text = (SCRIPTS / "scenario_metrics.py").read_text()
    assert 'ARTIFACT_DIR = REPO_ROOT / "docs" / "bench" / "artifacts"' in text


# ── Latency metrics (YC playbook §12.2) ─────────────────────────────────────

def _load_collector_module():
    """Import scripts/scenario_metrics.py without requiring a `scripts`
    package marker — matches how `make demo-*` invokes it (direct file)."""

    spec = importlib.util.spec_from_file_location(
        "scenario_metrics", SCRIPTS / "scenario_metrics.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_percentiles_empty_samples() -> None:
    sm = _load_collector_module()
    assert sm._percentiles([]) == {"p50_ms": None, "p95_ms": None, "n": 0}


def test_percentiles_single_sample() -> None:
    sm = _load_collector_module()
    out = sm._percentiles([123.4])
    assert out["n"] == 1
    assert out["p50_ms"] == 123.4
    assert out["p95_ms"] == 123.4


def test_percentiles_sorts_input() -> None:
    sm = _load_collector_module()
    out = sm._percentiles([300.0, 100.0, 200.0, 400.0])
    assert out["n"] == 4
    # nearest-rank: p50 → index ceil(0.5*4)=2 → 200.0; p95 → index 4 → 400.0.
    assert out["p50_ms"] == 200.0
    assert out["p95_ms"] == 400.0


def test_parse_ts_handles_z_and_invalid() -> None:
    sm = _load_collector_module()
    parsed = sm._parse_ts("2026-05-25T10:30:00Z")
    assert parsed is not None and parsed.tzinfo is not None
    assert sm._parse_ts("not-a-date") is None
    assert sm._parse_ts(None) is None


def test_latency_samples_correlates_anomaly_to_decision() -> None:
    """End-to-end correlation: an anomaly event and its autonomy command
    (target='anomaly:<id>') produce one detection-to-decision sample,
    and if the command flipped to in_flight, one decision-to-dispatch
    sample."""

    sm = _load_collector_module()
    t0 = datetime(2026, 5, 25, 10, 0, 0, tzinfo=UTC)
    events = [
        {
            "kind": "anomaly",
            "anomaly_id": "anom-1",
            "ts": t0.isoformat(),
            "source": "operator",
        },
    ]
    commands = [
        {
            "source": "autonomy",
            "target": "anomaly:anom-1",
            "submitted_at": (t0 + timedelta(milliseconds=150)).isoformat(),
            "in_flight_at": (t0 + timedelta(milliseconds=400)).isoformat(),
        },
    ]
    out = sm._latency_samples(events, commands)
    assert out["anomaly_to_autonomy_decision_ms"] == [150.0]
    assert out["autonomy_decision_to_mission_dispatch_ms"] == [250.0]


def test_latency_samples_skips_operator_commands() -> None:
    """Operator-issued commands must not show up in autonomy latency."""

    sm = _load_collector_module()
    t0 = datetime(2026, 5, 25, 10, 0, 0, tzinfo=UTC)
    events = [{"kind": "anomaly", "anomaly_id": "a", "ts": t0.isoformat()}]
    commands = [
        {
            "source": "operator",
            "target": "anomaly:a",
            "submitted_at": (t0 + timedelta(milliseconds=200)).isoformat(),
            "in_flight_at": (t0 + timedelta(milliseconds=300)).isoformat(),
        }
    ]
    out = sm._latency_samples(events, commands)
    assert out["anomaly_to_autonomy_decision_ms"] == []
    assert out["autonomy_decision_to_mission_dispatch_ms"] == []


def test_latency_samples_dismiss_has_no_dispatch_sample() -> None:
    """R3 DISMISS doesn't spawn a mission, so in_flight_at is null."""

    sm = _load_collector_module()
    t0 = datetime(2026, 5, 25, 10, 0, 0, tzinfo=UTC)
    events = [{"kind": "anomaly", "anomaly_id": "a", "ts": t0.isoformat()}]
    commands = [
        {
            "source": "autonomy",
            "rule": "R3",
            "target": "anomaly:a",
            "submitted_at": (t0 + timedelta(milliseconds=120)).isoformat(),
            "in_flight_at": None,
        }
    ]
    out = sm._latency_samples(events, commands)
    assert out["anomaly_to_autonomy_decision_ms"] == [120.0]
    assert out["autonomy_decision_to_mission_dispatch_ms"] == []


def test_latency_samples_uses_earliest_anomaly_when_duplicated() -> None:
    """Wildfire scenario emits SMOKE then FIRE with the same anomaly_id
    only when the detector re-fires on a re-classified anomaly. The
    collector must anchor on the earliest detection so the latency
    isn't artificially shrunk to zero."""

    sm = _load_collector_module()
    t0 = datetime(2026, 5, 25, 10, 0, 0, tzinfo=UTC)
    events = [
        {"kind": "anomaly", "anomaly_id": "a", "ts": (t0 + timedelta(seconds=5)).isoformat()},
        {"kind": "anomaly", "anomaly_id": "a", "ts": t0.isoformat()},
    ]
    commands = [
        {
            "source": "autonomy",
            "target": "anomaly:a",
            "submitted_at": (t0 + timedelta(milliseconds=200)).isoformat(),
        }
    ]
    out = sm._latency_samples(events, commands)
    assert out["anomaly_to_autonomy_decision_ms"] == [200.0]


def test_collect_includes_latencies_in_artifact_shape() -> None:
    """The artifact JSON contract carries `latencies_ms` with both
    well-known buckets — the YC demo line-item depends on this key
    being present even on empty windows."""

    sm = _load_collector_module()
    samples = sm._latency_samples([], [])
    assert "anomaly_to_autonomy_decision_ms" in samples
    assert "autonomy_decision_to_mission_dispatch_ms" in samples


def test_scenario_metrics_module_exports_latency_keys_in_source() -> None:
    """Guard against accidentally removing the artifact contract."""

    text = (SCRIPTS / "scenario_metrics.py").read_text()
    assert '"latencies_ms": latencies' in text
    assert '"anomaly_to_autonomy_decision"' in text
    assert '"autonomy_decision_to_mission_dispatch"' in text
