#!/usr/bin/env python3
"""CV live — real-score evidence bench (three-month plan, Track B).

Runs the **real** CV perception path end-to-end over the three owner-land
scenarios and reports the YOLOv8 scores that flow onto the bus as
``Anomaly.confidence`` — the milestone deliverable: *CV produces real
scores that feed anomalies, not scripted values*.

For each scenario this drives the production code, not a stub:

    sim/scenarios/<name>.yaml
      → load_scenario(...).build_world()
      → CVPerception.detect_and_emit(ignition)        (cv_enabled: true)
          → YOLODetector.predict(fixture, kind)       (ultralytics + torch)
          → Anomaly(confidence = real top-1 score, evidence.label = COCO class)

`intrusion` + `search` are `cv_enabled: true` and produce real `person`
scores on the committed CC0 fixtures. `wildfire` is `cv_enabled: false`
on purpose (fire/smoke-CV deferred to drone-day — COCO has no fire class),
so it is reported as scripted, never run through YOLO.

This is the counterpart to `scripts/shadow_divergence.py`: that bench
*models* the CV variance with seeded jitter so it can run without the
`[cv]` extra; this one produces the *actual* model scores. Requires
`make setup-cv` (or an ephemeral env) — the default `make test` path never
imports it.

Usage::

    make cv-live                       # writes docs/bench/artifacts/cv-live-*.json
    python scripts/cv_live_report.py --min-score 0.25
    python scripts/cv_live_report.py --json

Exit code is non-zero when a `cv_enabled` scenario's anomaly score falls
below ``--min-score`` — a real regression gate (e.g. a fixture silently
degraded to a 0.0 zero-pixel frame), never a failure-swallowing ``|| true``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "sim" / "scenarios"
ARTIFACT_DIR = ROOT / "docs" / "bench" / "artifacts"
SCENARIOS = ("wildfire_owner_land", "intrusion_owner_land", "search_owner_land")

# Floor below which a cv_enabled scenario is treated as a regression: the
# committed CC0 fixtures all score > 0.80 (see fixtures/LICENSES.md), so a
# detection under this floor means the fixture or the model path broke.
DEFAULT_MIN_SCORE = 0.25


@dataclass
class Detection:
    kind: str
    after_s: float
    source: str
    cv: bool
    confidence: float
    label: str | None = None
    fixture: str | None = None
    lat: float = 0.0
    lon: float = 0.0


@dataclass
class ScenarioReport:
    scenario_id: str
    cv_enabled: bool
    detections: list[Detection] = field(default_factory=list)

    @property
    def min_cv_score(self) -> float | None:
        cv_scores = [d.confidence for d in self.detections if d.cv]
        return min(cv_scores) if cv_scores else None


def _run_scenario(name: str) -> ScenarioReport:
    # Imported lazily so the default (no-[cv]) test path never pays the
    # ultralytics/torch import. The loader raises an actionable error when
    # the extra is missing (`make setup-cv`).
    from sim.swarm_sim.cv.perception_cv import CVPerception
    from sim.swarm_sim.scenario import load_scenario

    scenario = load_scenario(SCENARIO_DIR / f"{name}.yaml")
    world = scenario.build_world()
    perception = world.perception
    assert perception is not None
    report = ScenarioReport(scenario_id=scenario.id, cv_enabled=scenario.perception.cv_enabled)

    for ev in perception.ignitions:
        if isinstance(perception, CVPerception):
            fixture = perception._pick_fixture(ev.kind, ev.after_s)
            anomaly = perception.detect_and_emit(ev)
            label = anomaly.evidence.label if anomaly.evidence else None
            report.detections.append(
                Detection(
                    kind=ev.kind.value,
                    after_s=ev.after_s,
                    source=ev.source.value,
                    cv=True,
                    confidence=round(anomaly.confidence, 4),
                    label=label,
                    fixture=fixture.name,
                    lat=anomaly.geo.lat,
                    lon=anomaly.geo.lon,
                )
            )
        else:
            anomaly = perception.emit_for_event(ev)
            report.detections.append(
                Detection(
                    kind=ev.kind.value,
                    after_s=ev.after_s,
                    source=ev.source.value,
                    cv=False,
                    confidence=round(anomaly.confidence, 4),
                    lat=anomaly.geo.lat,
                    lon=anomaly.geo.lon,
                )
            )
    return report


def _to_payload(reports: list[ScenarioReport], min_score: float, passed: bool) -> dict[str, Any]:
    return {
        "tool": "cv_live_report",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "min_score_gate": min_score,
        "gate_passed": passed,
        "scenarios": [
            {
                "scenario_id": r.scenario_id,
                "cv_enabled": r.cv_enabled,
                "min_cv_score": r.min_cv_score,
                "detections": [vars(d) for d in r.detections],
            }
            for r in reports
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help="regression floor for cv_enabled anomaly scores (default %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="print the full artifact to stdout")
    parser.add_argument(
        "--no-write", action="store_true", help="do not write the artifact file"
    )
    args = parser.parse_args()

    try:
        reports = [_run_scenario(name) for name in SCENARIOS]
    except ImportError as exc:  # pragma: no cover - env guard
        print(
            f"cv-live: FAIL: CV runtime unavailable ({exc}). "
            "Run `make setup-cv` (opt-in [cv] extra) first.",
            file=sys.stderr,
        )
        return 2

    # Gate: every cv_enabled detection must clear the floor.
    offenders = [
        (r.scenario_id, d.kind, d.confidence)
        for r in reports
        for d in r.detections
        if d.cv and d.confidence < args.min_score
    ]
    passed = not offenders

    payload = _to_payload(reports, args.min_score, passed)

    if not args.no_write:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = ARTIFACT_DIR / f"cv-live-{stamp}.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"cv-live: artifact → {out.relative_to(ROOT)}")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for r in reports:
            for d in r.detections:
                if d.cv:
                    print(
                        f"cv-live: {r.scenario_id:<22} {d.kind:<10} "
                        f"cv label={d.label!r:<10} score={d.confidence:.3f} "
                        f"fixture={d.fixture}"
                    )
                else:
                    print(
                        f"cv-live: {r.scenario_id:<22} {d.kind:<10} "
                        f"scripted={d.confidence:.3f} source={d.source} (cv deferred)"
                    )

    if not passed:
        print(
            "cv-live: FAIL: cv_enabled anomalies below floor "
            f"{args.min_score}: {offenders}",
            file=sys.stderr,
        )
        return 1
    print(f"cv-live: PASS (all cv_enabled scores ≥ {args.min_score})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
