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

import os
import re
import subprocess
import sys
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
