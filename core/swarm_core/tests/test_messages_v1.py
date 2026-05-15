"""Tests for the Phase 0+ Console-facing aggregate models."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from swarm_core.messages import (
    AgentState,
    AnomalyKind,
    AnomalyState,
    AnomalyView,
    AwarenessBreakdown,
    CommandStatus,
    ConfidenceBand,
    DockState,
    DockStatus,
    Event,
    EventKind,
    Geo,
    MissionPhase,
    MissionView,
    OperatingMode,
    OperatorAction,
    OperatorCommand,
    PowerStatus,
    RejectedReason,
    RiskBand,
    RiskState,
    Sector,
    SectorState,
    Session,
    UnitState,
)


def _g(lat: float = 44.7, lon: float = 8.0) -> Geo:
    return Geo(lat=lat, lon=lon)


def test_session_defaults() -> None:
    s = Session(label="session 014")
    assert s.id
    assert s.site_id == "vineyard-01"
    assert isinstance(s.started_at, datetime)
    assert s.started_at.tzinfo is UTC


def test_session_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        Session.model_validate({"label": "x", "rogue": True})


def test_unit_state_roundtrip() -> None:
    u = UnitState(
        agent_id="d-003",
        vendor="simulator",
        model="sim-v1",
        fsm_state=AgentState.ON_STATION,
        battery_pct=72.0,
        geo=_g(),
        current_mission_id="m-1",
        current_sector_id="s-NORTH-A",
        link_quality=0.97,
        heading_deg=42.0,
        altitude_agl_m=120.0,
        dock_id="dock-1",
    )
    raw = u.model_dump_json()
    decoded = UnitState.model_validate(json.loads(raw))
    assert decoded == u


def test_unit_state_rejects_out_of_range_battery() -> None:
    with pytest.raises(ValidationError):
        UnitState(
            agent_id="d-003",
            vendor="x",
            model="y",
            fsm_state=AgentState.DOCKED,
            battery_pct=120.0,
            geo=_g(),
        )


def test_dock_state_minimal() -> None:
    d = DockState(dock_id="dock-1", status=DockStatus.ONLINE)
    assert d.weather_lock is False
    assert d.power_status == PowerStatus.ONLINE
    assert d.units_total == 0


def test_sector_requires_min_three_vertices() -> None:
    poly = [_g(44.0, 8.0), _g(44.0, 8.01), _g(44.01, 8.01)]
    s = Sector(id="s1", label="north-a", polygon=poly, centroid=_g(44.005, 8.005))
    assert s.state == SectorState.IDLE
    assert s.risk_band == RiskBand.LOW
    assert s.confidence == 1.0

    with pytest.raises(ValidationError):
        Sector(
            id="s1",
            label="bad",
            polygon=[_g(0, 0), _g(0, 1)],  # 2 points only
            centroid=_g(0, 0.5),
        )


def test_awareness_breakdown_bounds() -> None:
    a = AwarenessBreakdown(score=84.0, risk_state=RiskState.AWARE)
    assert a.factors == {}
    assert a.blind_spot_sectors == []
    with pytest.raises(ValidationError):
        AwarenessBreakdown(score=110.0)


def test_mission_view_progress_clamp() -> None:
    m = MissionView(id="m-1", kind="PATROL", phase=MissionPhase.EN_ROUTE, progress_pct=42.0)
    assert m.eta_s is None
    with pytest.raises(ValidationError):
        MissionView(id="m-2", kind="PATROL", progress_pct=101.0)


def test_anomaly_view_band_explicit() -> None:
    a = AnomalyView(
        id="a-1",
        kind=AnomalyKind.SMOKE,
        geo=_g(),
        confidence=0.42,
        band=ConfidenceBand.LOW_CONFIDENCE,
    )
    assert a.state == AnomalyState.PENDING
    assert a.detected_by is None


def test_event_emits_typed_kind() -> None:
    e = Event(kind=EventKind.ANOMALY, body="low-confidence anomaly · confidence 042%")
    assert e.id
    assert e.kind == EventKind.ANOMALY


def test_event_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        Event.model_validate({"kind": "rogue", "body": ""})


def test_operator_command_defaults() -> None:
    c = OperatorCommand(action=OperatorAction.VERIFY, target="sector:north-a", operator_id="op-davide")
    assert c.status == CommandStatus.SUBMITTED
    assert c.rejected_reason is None
    assert c.completed_at is None


def test_operator_command_rejected_reason_is_closed_enum() -> None:
    """The audit log must never echo user-supplied free-text into the reason."""
    with pytest.raises(ValidationError):
        OperatorCommand.model_validate(
            {
                "action": "verify",
                "target": "sector:x",
                "operator_id": "op-x",
                "rejected_reason": "drop table operator_commands;",
            }
        )
    # Closed-enum values do parse:
    OperatorCommand.model_validate(
        {
            "action": "verify",
            "target": "sector:x",
            "operator_id": "op-x",
            "rejected_reason": RejectedReason.TARGET_NOT_FOUND.value,
        }
    )


def test_operating_mode_values_match_pdf() -> None:
    assert OperatingMode.REST.value == "rest"
    assert OperatingMode.PATROL.value == "patrol"
    assert OperatingMode.VERIFICATION.value == "verification"
    assert OperatingMode.ESCALATION.value == "escalation"
    assert OperatingMode.MAINTENANCE.value == "maintenance"
