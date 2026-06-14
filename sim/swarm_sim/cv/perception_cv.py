"""Phase 7.D — CV-driven perception.

Drop-in replacement for `sim.swarm_sim.perception.MockPerception`. Same
`run()` + `on_anomaly` callback, same `IgnitionEvent` schedule, same
geo + kind from the YAML. The difference: `confidence` is the real
top-1 YOLOv8 score on a deterministically-picked fixture frame, not a
scripted number.

Determinism: we seed an RNG from `hash((scenario_id, after_s))` so a
given scenario YAML always picks the same fixture frame for a given
ignition. Combined with `torch.manual_seed(0)` in `YOLODetector`, the
end-to-end (`load_scenario → build_world → CVPerception.run`) pipeline
is reproducible — the precondition Phase 8.B-bis shadow mode depends
on.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from swarm_core.messages import Anomaly, AnomalyKind, Geo

from sim.swarm_sim.cv.detector import YOLODetector
from sim.swarm_sim.cv.weights import CVAssetError, list_fixtures
from sim.swarm_sim.perception import IgnitionEvent, build_evidence

logger = logging.getLogger("sim.cv.perception")

_KIND_TO_FIXTURE_DIR: dict[AnomalyKind, str] = {
    AnomalyKind.FIRE: "fire",
    AnomalyKind.SMOKE: "fire",
    AnomalyKind.HEAT_SPOT: "person_aerial",
    AnomalyKind.INTRUSION: "person_aerial",
    AnomalyKind.UNKNOWN: "fire",
}


class NoFixtureAvailable(CVAssetError):
    """A scheduled ignition has no committed fixture for its kind."""


@dataclass
class CVPerception:
    """Emit anomalies whose confidence comes from real YOLOv8 inference.

    The constructor matches the keyword arguments of `MockPerception`
    (territory_center, territory_radius_m, ignitions, on_anomaly, rng)
    plus a required `scenario_id` so the per-ignition fixture pick is
    stable across runs.
    """

    territory_center: Geo
    territory_radius_m: float = 600.0
    ignitions: list[IgnitionEvent] = field(default_factory=list)
    on_anomaly: Callable[[Anomaly], None] | None = None
    rng: random.Random = field(default_factory=random.Random)
    scenario_id: str = "unknown"
    detector: YOLODetector | None = None

    def _pick_fixture(self, kind: AnomalyKind, after_s: float) -> Path:
        bucket = _KIND_TO_FIXTURE_DIR.get(kind, "fire")
        files = list_fixtures(bucket)
        if not files:
            raise NoFixtureAvailable(
                f"no committed fixture frames for kind={kind.value} bucket={bucket!r}"
            )
        seed = hash((self.scenario_id, kind.value, round(after_s, 3)))
        return files[seed % len(files)]

    def _detector(self) -> YOLODetector:
        if self.detector is None:
            self.detector = YOLODetector()
        return self.detector

    async def run(self) -> None:
        """Schedule the ignitions and emit anomalies as they fire."""
        if not self.ignitions:
            return
        for ev in sorted(self.ignitions, key=lambda e: e.after_s):
            await asyncio.sleep(ev.after_s)
            self.detect_and_emit(ev)

    def detect_and_emit(self, ev: IgnitionEvent) -> Anomaly:
        """Run inference on the chosen fixture and emit an Anomaly.

        The geo + kind come from the scripted IgnitionEvent (sim has no
        geo-localized frames). Only `confidence` is the real model score.
        """

        frame = self._pick_fixture(ev.kind, ev.after_s)
        det = self._detector().predict(frame, ev.kind)
        logger.info(
            "cv: scenario=%s kind=%s frame=%s label=%r conf=%.3f",
            self.scenario_id, ev.kind.value, frame.name, det.label, det.confidence,
        )
        # Evidence carries the real YOLO label + score (object_score). The
        # geo + kind stay scripted; only confidence is the model output.
        evidence = build_evidence(ev, label=det.label, score=det.confidence)
        anomaly = Anomaly(
            kind=ev.kind,
            geo=ev.geo,
            confidence=det.confidence,
            evidence=evidence,
        )
        if self.on_anomaly:
            self.on_anomaly(anomaly)
        return anomaly

    # Structural compat with MockPerception — keeps the world.py union
    # honest if any caller wants the legacy emit_anomaly path. Returns
    # the same Anomaly as MockPerception with the scripted confidence.
    def emit_anomaly(self, kind: AnomalyKind, geo: Geo, confidence: float) -> Anomaly:
        a = Anomaly(kind=kind, geo=geo, confidence=confidence)
        if self.on_anomaly:
            self.on_anomaly(a)
        return a
