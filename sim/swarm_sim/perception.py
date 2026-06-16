"""Mock perception layer — injects anomalies on a schedule.

In commit 1 this is intentionally simple: at configured times the perception
emits a `SMOKE` anomaly at a random or pre-set geo. The interface
(`emit_anomaly`) is the same the future CV model will satisfy — when the
PyTorch detector in `ml/anomaly/` is ready, it replaces this implementation
without touching the orchestrator.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from swarm_core.messages import (
    Anomaly,
    AnomalyEvidence,
    AnomalyKind,
    AnomalySource,
    Geo,
    SensorKind,
)
from swarm_core.voice import evidence_headline

# Evidence-layer label per kind for the drone-CV provenance on the Mock path
# (the CV path uses the real YOLO label instead). Honest sim mapping.
_KIND_TO_CV_LABEL: dict[AnomalyKind, str] = {
    AnomalyKind.FIRE: "fire",
    AnomalyKind.SMOKE: "smoke",
    AnomalyKind.HEAT_SPOT: "person",
    AnomalyKind.INTRUSION: "person",
    AnomalyKind.UNKNOWN: "signal",
}


@dataclass
class EvidenceSignal:
    """The scripted triggering signal behind an anomaly (honest sim values).

    Runtime carrier mirroring the scenario YAML ``SignalCfg``. Lives here, not
    in ``scenario.py``, so ``perception`` owns its own runtime types and the
    ``scenario → perception`` import stays one-directional (no cycle).
    """

    metric: str
    value: float | None = None
    baseline: float | None = None
    unit: str | None = None


@dataclass
class IgnitionEvent:
    """A scripted "fire ignites here at t_s seconds" event for demos."""

    after_s: float
    geo: Geo
    kind: AnomalyKind = AnomalyKind.SMOKE
    confidence: float = 0.78
    # Evidence layer: where the signal came from + the triggering measurement.
    # Defaults to drone-CV so legacy ignitions stay valid.
    source: AnomalySource = AnomalySource.DRONE_CV
    signal: EvidenceSignal | None = None


def build_evidence(
    ev: IgnitionEvent,
    *,
    label: str | None = None,
    score: float | None = None,
) -> AnomalyEvidence:
    """Compose the honest ``AnomalyEvidence`` for a scripted ignition.

    Every value is sim-modelled (``simulated=True``). The CV path passes the
    real YOLO ``label`` + ``score``; the thermal / fire-detector path reads the
    scripted ``signal`` block. ``headline`` is built server-side by
    ``voice.evidence_headline`` so the Console renders truth, never composes it.
    """

    if ev.source == AnomalySource.DRONE_CV:
        evidence = AnomalyEvidence(
            source=AnomalySource.DRONE_CV,
            sensor=SensorKind.RGB,
            label=label if label is not None else _KIND_TO_CV_LABEL.get(ev.kind),
            metric="object_score",
            value=score if score is not None else ev.confidence,
            unit="score",
        )
    else:
        sig = ev.signal
        evidence = AnomalyEvidence(
            source=ev.source,
            sensor=SensorKind.THERMAL,
            metric=sig.metric if sig else None,
            value=sig.value if sig else None,
            baseline=sig.baseline if sig else None,
            unit=sig.unit if sig else None,
        )
    return evidence.model_copy(update={"headline": evidence_headline(evidence)})


@dataclass
class MockPerception:
    """Emits anomalies according to a schedule (or randomly)."""

    territory_center: Geo
    territory_radius_m: float = 600.0
    ignitions: list[IgnitionEvent] = field(default_factory=list)
    on_anomaly: Callable[[Anomaly], None] | None = None
    rng: random.Random = field(default_factory=random.Random)

    async def run(self) -> None:
        """Schedule the ignitions and emit anomalies as they fire."""
        if not self.ignitions:
            return
        # Sort by after_s and emit each on time.
        for ev in sorted(self.ignitions, key=lambda e: e.after_s):
            await asyncio.sleep(ev.after_s)
            self.emit_for_event(ev)

    def emit_for_event(self, ev: IgnitionEvent) -> Anomaly:
        """Emit an anomaly carrying its evidence (provenance + signal)."""
        a = Anomaly(
            kind=ev.kind,
            geo=ev.geo,
            confidence=ev.confidence,
            evidence=build_evidence(ev),
        )
        if self.on_anomaly:
            self.on_anomaly(a)
        return a

    def emit_anomaly(self, kind: AnomalyKind, geo: Geo, confidence: float) -> Anomaly:
        a = Anomaly(kind=kind, geo=geo, confidence=confidence)
        if self.on_anomaly:
            self.on_anomaly(a)
        return a

    def random_point_in_territory(self) -> Geo:
        """Pick a roughly uniform point in a disk around the territory center."""
        import math

        r = self.territory_radius_m * (self.rng.random() ** 0.5)
        theta = self.rng.uniform(0, 2 * math.pi)
        m_per_deg = 111_000.0
        dlat = (r * math.sin(theta)) / m_per_deg
        dlon = (r * math.cos(theta)) / m_per_deg
        return Geo(
            lat=self.territory_center.lat + dlat,
            lon=self.territory_center.lon + dlon,
        )
