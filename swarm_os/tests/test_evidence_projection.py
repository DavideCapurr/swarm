"""Evidence layer — the coordinator projects `Anomaly.evidence` onto the view.

SwarmOS owns the projection; the Console only renders it. This pins that a raw
`Anomaly` carrying evidence keeps that evidence on the `AnomalyView` (and in the
snapshot frame) without the Console ever composing operational truth.
"""

from __future__ import annotations

import pytest
from swarm_core.messages import (
    Anomaly,
    AnomalyEvidence,
    AnomalyKind,
    AnomalySource,
    SensorKind,
)

from swarm_os.coordinator import SwarmCoordinator
from swarm_os.state import VINEYARD_CENTER, SwarmState


@pytest.mark.asyncio
async def test_apply_anomaly_projects_evidence_onto_view() -> None:
    state = SwarmState.vineyard()
    coordinator = SwarmCoordinator(state)

    evidence = AnomalyEvidence(
        source=AnomalySource.THERMAL_SAT,
        sensor=SensorKind.THERMAL,
        metric="temperature_c",
        value=47.0,
        baseline=18.0,
        unit="°C",
        headline="thermal · +29°C over baseline",
    )
    anomaly = Anomaly(
        kind=AnomalyKind.FIRE,
        geo=VINEYARD_CENTER,
        confidence=0.88,
        source_agent="sim-1",
        evidence=evidence,
    )
    await coordinator.apply_anomaly(anomaly)

    view = state.anomalies[anomaly.id]
    assert view.evidence is not None
    assert view.evidence.source == AnomalySource.THERMAL_SAT
    assert view.evidence.value == 47.0
    assert view.evidence.baseline == 18.0
    assert view.evidence.headline == "thermal · +29°C over baseline"
    assert view.evidence.simulated is True


@pytest.mark.asyncio
async def test_apply_anomaly_without_evidence_leaves_view_none() -> None:
    """Backward compatibility — an evidence-less anomaly projects evidence=None."""
    state = SwarmState.vineyard()
    coordinator = SwarmCoordinator(state)
    anomaly = Anomaly(kind=AnomalyKind.SMOKE, geo=VINEYARD_CENTER, confidence=0.5)
    await coordinator.apply_anomaly(anomaly)
    assert state.anomalies[anomaly.id].evidence is None
