"""Awareness score calculator."""

from __future__ import annotations

from datetime import datetime

from swarm_core.messages import (
    AgentState,
    AnomalyState,
    AnomalyView,
    AwarenessBreakdown,
    RiskState,
    Sector,
    SectorState,
    UnitState,
)


def calculate_awareness(
    *,
    sectors: dict[str, Sector],
    units: dict[str, UnitState],
    anomalies: dict[str, AnomalyView],
    now: datetime,
) -> AwarenessBreakdown:
    """Compute a bounded score from sector coverage, fleet health, and anomalies."""

    sector_values = list(sectors.values())
    if sector_values:
        sector_score = sum(float(s.confidence) for s in sector_values) / len(sector_values) * 100.0
    else:
        sector_score = 0.0

    if units:
        health_values = [
            ((unit.battery_pct / 100.0) * 0.55 + unit.link_quality * 0.45) * 100.0
            for unit in units.values()
            if unit.fsm_state != AgentState.OFFLINE
        ]
        fleet_score = sum(health_values) / len(health_values) if health_values else 0.0
    else:
        fleet_score = 0.0

    active_anomalies = [
        a
        for a in anomalies.values()
        if a.state in {AnomalyState.PENDING, AnomalyState.VERIFYING, AnomalyState.VERIFIED}
    ]
    anomaly_penalty = min(35.0, sum(a.confidence for a in active_anomalies) * 18.0)
    score = max(0.0, min(100.0, sector_score * 0.55 + fleet_score * 0.45 - anomaly_penalty))

    blind = [s.id for s in sector_values if s.state == SectorState.BLIND]
    stale = [s.id for s in sector_values if s.state == SectorState.STALE]
    if any(a.state == AnomalyState.VERIFIED for a in active_anomalies) or score < 45.0:
        risk_state = RiskState.ELEVATED
    elif active_anomalies or score < 75.0:
        risk_state = RiskState.AWARE
    else:
        risk_state = RiskState.REST

    return AwarenessBreakdown(
        score=round(score, 2),
        factors={
            "sector_confidence": round(sector_score, 2),
            "fleet_health": round(fleet_score, 2),
            "anomaly_penalty": round(anomaly_penalty, 2),
        },
        blind_spot_sectors=blind,
        stale_sectors=stale,
        risk_state=risk_state,
        ts=now,
    )
