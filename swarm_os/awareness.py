"""Awareness score calculator.

Phase 3: the breakdown now carries the operating mode and the active verifier
agent so the Console has a single truth frame for top-level state. Mode is
passed in by the coordinator (it sequences mode → awareness → frame).
"""

from __future__ import annotations

from datetime import datetime

from swarm_core.messages import (
    AgentState,
    AnomalyState,
    AnomalyView,
    AwarenessBreakdown,
    OperatingMode,
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
    mode: OperatingMode = OperatingMode.REST,
    verifying_agent: str | None = None,
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
        link_values = [
            unit.link_quality * 100.0
            for unit in units.values()
            if unit.fsm_state != AgentState.OFFLINE
        ]
        link_score = sum(link_values) / len(link_values) if link_values else 0.0
    else:
        fleet_score = 0.0
        link_score = 0.0

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
            "link_aggregate": round(link_score, 2),
            "anomaly_penalty": round(anomaly_penalty, 2),
        },
        blind_spot_sectors=blind,
        stale_sectors=stale,
        risk_state=risk_state,
        mode=mode,
        verifying_agent=verifying_agent,
        ts=now,
    )
