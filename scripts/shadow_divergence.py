#!/usr/bin/env python3
"""Phase 8.B-bis — shadow-mode divergence bench for the Phase 8 gate.

Runs the **real** Phase 8.B deterministic decider (`autonomy.decide_all`,
with the committed `infra/config/autonomy.yaml`) in shadow against the
**real** human-baseline oracle (`BaselineOracle`, with the committed
`infra/config/autonomy_baseline.yaml`) over the three owner-land scenarios,
and reports the divergence rate against the ``< 5%`` Phase 8 gate.

This is the Gate-8 evidence tool, parallel to `scripts/scenario_metrics.py`.
It exercises the production *decision function* (not the full dispatch loop,
which `test_phase7b_integration.py` covers) at each scenario decision point:

  * PENDING (settled past the engine's debounce/stale windows) — the
    verify/dismiss decision.
  * VERIFIED (settled past the idle window) — the escalate decision, but
    only when the engine actually verified the anomaly, so the lifecycle is
    driven by the engine's own verdict rather than fabricated.

Determinism + the "100+ runs" requirement:
  Wildfire confidence is scripted (`cv_enabled: false`) and identical every
  run. Intrusion and search run real CV (`cv_enabled: true`), whose
  confidence jitters run-to-run; ``--jitter-sigma`` models that variance
  with seeded Gaussian noise so the bench can produce the 100+-run
  distribution without the ~2 GB ``[cv]`` stack. ``--jitter-sigma 0`` (the
  default) is fully deterministic and reproducible — the committed-evidence
  mode. A future ``--cv`` mode would feed real model scores here.

Usage::

    python scripts/shadow_divergence.py --runs 100 --jitter-sigma 0.05
    python scripts/shadow_divergence.py --runs 100            # deterministic

Exit code is non-zero if the overall divergence is not within the gate —
this is a real gate, never a failure-swallowing ``|| true``.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from swarm_core.messages import AnomalyKind, AnomalyState, AnomalyView, Geo
from swarm_core.voice import band as confidence_band

from sim.swarm_sim.scenario import Scenario, ScriptedAnomalyCfg, load_scenario
from swarm_os.autonomy import AutonomyVerdict
from swarm_os.autonomy_config import load_autonomy_config
from swarm_os.shadow import (
    GATE_DIVERGENCE,
    ShadowDecisionLog,
    ShadowEntry,
    engine_decider,
    oracle_decider,
    shadow_step,
)
from swarm_os.shadow_oracle import load_oracle_config
from swarm_os.state import SwarmState

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = REPO_ROOT / "sim" / "scenarios"
ARTIFACT_DIR = REPO_ROOT / "docs" / "bench" / "artifacts"

# A fixed decision instant + a large settle age so every engine timing
# window (debounce / stale / idle) is cleared — the bench compares settled
# dispositions, not transients.
_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
_SETTLE_AGE_S = 1_000_000.0


def _anomaly_view(
    *, kind: AnomalyKind, confidence: float, geo: Geo, state: AnomalyState
) -> AnomalyView:
    return AnomalyView(
        id="bench-anomaly",
        kind=kind,
        geo=geo,
        confidence=confidence,
        band=confidence_band(confidence),
        state=state,
        detected_at=_NOW - timedelta(seconds=_SETTLE_AGE_S),
        ts=_NOW - timedelta(seconds=_SETTLE_AGE_S),
    )


def _state_with(anomaly: AnomalyView) -> SwarmState:
    state = SwarmState.vineyard()
    state.anomalies[anomaly.id] = anomaly
    return state


def _evaluate_anomaly(
    scenario: Scenario,
    anomaly_cfg: ScriptedAnomalyCfg,
    confidence: float,
    *,
    candidate: Any,
    baseline: Any,
) -> list[ShadowEntry]:
    """Shadow-compare one scripted anomaly at its decision points."""

    geo = scenario.resolve_geo(anomaly_cfg.position)
    entries: list[ShadowEntry] = []

    pending = _state_with(
        _anomaly_view(
            kind=anomaly_cfg.kind,
            confidence=confidence,
            geo=geo,
            state=AnomalyState.PENDING,
        )
    )
    pending_entries = shadow_step(pending, _NOW, candidate=candidate, baseline=baseline)
    entries.extend(pending_entries)

    # Drive the VERIFIED decision point only when the engine actually
    # verified — the engine's verdict, not a script, drives the lifecycle.
    engine_verified = any(
        e.candidate is AutonomyVerdict.VERIFY for e in pending_entries
    )
    if engine_verified:
        verified = _state_with(
            _anomaly_view(
                kind=anomaly_cfg.kind,
                confidence=confidence,
                geo=geo,
                state=AnomalyState.VERIFIED,
            )
        )
        entries.extend(
            shadow_step(verified, _NOW, candidate=candidate, baseline=baseline)
        )
    return entries


def _jittered_confidence(
    base: float, *, rng: random.Random, sigma: float
) -> float:
    if sigma <= 0.0:
        return base
    return min(1.0, max(0.0, base + rng.gauss(0.0, sigma)))


def _scenario_paths() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("*.yaml"))


def run_shadow_bench(
    *,
    runs: int = 100,
    jitter_sigma: float = 0.0,
    seed: int = 0,
    scenario_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the shadow bench and return the artifact payload.

    Importable so tests can assert the gate on the real scenarios without
    spawning a process.
    """

    autonomy_cfg = load_autonomy_config()
    oracle_cfg = load_oracle_config()
    candidate = engine_decider(autonomy_cfg)
    baseline = oracle_decider(oracle_cfg)

    paths = (
        sorted((scenario_dir or SCENARIO_DIR).glob("*.yaml"))
        if scenario_dir is not None
        else _scenario_paths()
    )

    overall = ShadowDecisionLog(gate=GATE_DIVERGENCE)
    by_scenario: dict[str, dict[str, Any]] = {}
    scenario_ids: list[str] = []

    for path in paths:
        scenario = load_scenario(path)
        if not scenario.autonomy_baseline:
            continue  # only the autonomy scenarios carry a decision to shadow
        scenario_ids.append(scenario.id)
        per_scenario = ShadowDecisionLog(gate=GATE_DIVERGENCE)
        jitter_on = scenario.perception.cv_enabled

        for run_idx in range(runs):
            rng = random.Random(f"{seed}:{scenario.id}:{run_idx}")
            for anomaly_cfg in scenario.anomalies:
                conf = (
                    _jittered_confidence(
                        anomaly_cfg.confidence, rng=rng, sigma=jitter_sigma
                    )
                    if jitter_on
                    else anomaly_cfg.confidence
                )
                entries = _evaluate_anomaly(
                    scenario,
                    anomaly_cfg,
                    conf,
                    candidate=candidate,
                    baseline=baseline,
                )
                per_scenario.extend(entries)
                overall.extend(entries)

        by_scenario[scenario.id] = {
            "cv_jitter": jitter_on and jitter_sigma > 0.0,
            **per_scenario.report().summary(),
        }

    return {
        "milestone": "8.B-bis",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runs_per_scenario": runs,
        "jitter_sigma": jitter_sigma,
        "seed": seed,
        "gate": GATE_DIVERGENCE,
        "scenarios": scenario_ids,
        "overall": overall.report().summary(),
        "by_scenario": by_scenario,
    }


def write_artifact(payload: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = ARTIFACT_DIR / f"phase-8bbis-shadow-{ts}.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 8.B-bis shadow-mode divergence bench"
    )
    parser.add_argument(
        "--runs", type=int, default=100, help="runs per scenario (default 100)"
    )
    parser.add_argument(
        "--jitter-sigma",
        type=float,
        default=0.0,
        help="Gaussian sigma modelling CV confidence variance on cv_enabled "
        "scenarios (default 0.0 = deterministic)",
    )
    parser.add_argument("--seed", type=int, default=0, help="RNG seed (default 0)")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="print the report but do not write an artifact",
    )
    args = parser.parse_args(argv)

    payload = run_shadow_bench(
        runs=args.runs, jitter_sigma=args.jitter_sigma, seed=args.seed
    )
    overall = payload["overall"]

    if not args.no_write:
        out_path = write_artifact(payload)
        print(f"[shadow_divergence] wrote {out_path}", flush=True)

    print(
        f"[shadow_divergence] scenarios={payload['scenarios']} "
        f"runs={args.runs} jitter_sigma={args.jitter_sigma}",
        flush=True,
    )
    for sid, rep in payload["by_scenario"].items():
        print(
            f"[shadow_divergence]   {sid}: divergence={rep['divergence_rate']:.4f} "
            f"({rep['diverged']}/{rep['total']}) within_gate={rep['within_gate']}",
            flush=True,
        )
    print(
        f"[shadow_divergence] OVERALL divergence={overall['divergence_rate']:.4f} "
        f"({overall['diverged']}/{overall['total']}) gate={overall['gate']} "
        f"within_gate={overall['within_gate']}",
        flush=True,
    )
    if overall["by_transition"]:
        print(
            f"[shadow_divergence] divergence breakdown: {overall['by_transition']}",
            flush=True,
        )
    return 0 if overall["within_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
