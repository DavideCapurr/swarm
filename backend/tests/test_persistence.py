"""Phase 4 — persistence layer tests.

Goals:
  - write_* round-trips through list_* (and the data is unchanged)
  - the repository is a no-op when sessionmaker is None
  - dialect-aware upsert collapses duplicate ids (no row count blow-up)
  - SQL-injection-shaped filter values can't bypass parameterization
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from swarm_core.messages import (
    AnomalyKind,
    AnomalyState,
    AnomalyView,
    CommandStatus,
    ConfidenceBand,
    Event,
    EventKind,
    Geo,
    MissionPhase,
    MissionView,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
    Session,
    Telemetry,
)

from backend.app.db.repository import Repository, _dedupe_rows_for_upsert

pytestmark = pytest.mark.asyncio


# ── Repository disabled-mode ─────────────────────────────────────────────────


async def test_disabled_repository_is_noop(disabled_repository: Repository) -> None:
    """Every write is a no-op; every read is empty when sessionmaker is None."""
    assert disabled_repository.enabled is False
    await disabled_repository.write_session(
        Session(label="t", started_at=datetime.now(UTC))
    )
    await disabled_repository.write_events([_event()])
    assert await disabled_repository.list_events() == []
    assert await disabled_repository.list_operator_commands() == []


# ── Events: write + read + filter ────────────────────────────────────────────


async def test_event_round_trip(memory_repository: Repository) -> None:
    e = _event(kind=EventKind.ANOMALY, body="elevated anomaly")
    await memory_repository.write_events([e])
    rows = await memory_repository.list_events()
    assert len(rows) == 1
    assert rows[0].id == e.id
    assert rows[0].kind == EventKind.ANOMALY
    assert rows[0].body == "elevated anomaly"


async def test_event_upsert_deduplicates_by_id(memory_repository: Repository) -> None:
    """Re-persisting the same event id must not produce a duplicate row."""
    e = _event()
    await memory_repository.write_events([e, e])
    await memory_repository.write_events([e])
    rows = await memory_repository.list_events()
    assert len(rows) == 1


async def test_upsert_batch_dedupes_duplicate_composite_pk() -> None:
    """Postgres rejects duplicate conflict keys within one ON CONFLICT batch."""
    ts = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    rows = [
        {"id": "evt-1", "ts": ts, "body": "old"},
        {"id": "evt-2", "ts": ts, "body": "keep"},
        {"id": "evt-1", "ts": ts, "body": "new"},
    ]

    deduped = _dedupe_rows_for_upsert(rows, ("id", "ts"))

    assert deduped == [
        {"id": "evt-1", "ts": ts, "body": "new"},
        {"id": "evt-2", "ts": ts, "body": "keep"},
    ]


async def test_events_filter_by_kind_sector_agent(memory_repository: Repository) -> None:
    a = _event(kind=EventKind.ANOMALY, sector_id="s-1", agent_id="ag-1")
    p = _event(kind=EventKind.PATROL, sector_id="s-2", agent_id="ag-2")
    await memory_repository.write_events([a, p])

    assert {e.id for e in await memory_repository.list_events(kind=EventKind.ANOMALY)} == {a.id}
    assert {e.id for e in await memory_repository.list_events(sector_id="s-2")} == {p.id}
    assert {e.id for e in await memory_repository.list_events(agent_id="ag-1")} == {a.id}


async def test_events_filter_by_time_range(memory_repository: Repository) -> None:
    base = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    older = _event(ts=base - timedelta(hours=2))
    middle = _event(ts=base)
    newer = _event(ts=base + timedelta(hours=2))
    await memory_repository.write_events([older, middle, newer])

    middle_window = await memory_repository.list_events(
        from_ts=base - timedelta(minutes=30), to_ts=base + timedelta(minutes=30)
    )
    assert [e.id for e in middle_window] == [middle.id]


async def test_events_limit_clamped(memory_repository: Repository) -> None:
    """The limit ceiling protects against unbounded scans."""
    base = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    events = [_event(ts=base + timedelta(seconds=i)) for i in range(50)]
    await memory_repository.write_events(events)

    rows = await memory_repository.list_events(limit=10)
    assert len(rows) == 10


# ── Operator commands: audit log ────────────────────────────────────────────


async def test_operator_command_round_trip(memory_repository: Repository) -> None:
    cmd = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="anomaly:ab12",
        operator_id="op-alice01",
    )
    await memory_repository.write_operator_command(cmd)
    rows = await memory_repository.list_operator_commands()
    assert len(rows) == 1
    assert rows[0].id == cmd.id
    assert rows[0].operator_id == "op-alice01"
    assert rows[0].status == CommandStatus.SUBMITTED


async def test_operator_command_filter_by_operator(memory_repository: Repository) -> None:
    a = OperatorCommand(
        action=OperatorAction.VERIFY, target="anomaly:1", operator_id="op-alice01"
    )
    b = OperatorCommand(
        action=OperatorAction.DISMISS, target="anomaly:2", operator_id="op-bob02"
    )
    await memory_repository.write_operator_command(a)
    await memory_repository.write_operator_command(b)
    rows = await memory_repository.list_operator_commands(operator_id="op-alice01")
    assert {c.id for c in rows} == {a.id}


async def test_rejected_command_persists_rejected_reason(
    memory_repository: Repository,
) -> None:
    cmd = OperatorCommand(
        action=OperatorAction.HOLD_PATROL,
        target="*",
        operator_id="op-alice01",
        status=CommandStatus.REJECTED,
        rejected_reason=RejectedReason.RATE_LIMITED,
    )
    await memory_repository.write_operator_command(cmd)
    rows = await memory_repository.list_operator_commands(operator_id="op-alice01")
    assert rows[0].status == CommandStatus.REJECTED
    assert rows[0].rejected_reason == RejectedReason.RATE_LIMITED


# ── Anomalies + missions + telemetry ────────────────────────────────────────


async def test_write_anomaly_view(memory_repository: Repository) -> None:
    view = AnomalyView(
        id="anom-1",
        kind=AnomalyKind.SMOKE,
        geo=Geo(lat=44.7, lon=8.03, alt_m=0.0),
        sector_id="s-1",
        confidence=0.42,
        band=ConfidenceBand.LOW_CONFIDENCE,
        state=AnomalyState.PENDING,
    )
    await memory_repository.write_anomaly(view)
    # Re-write with new state — upsert should update in place.
    updated = view.model_copy(update={"state": AnomalyState.VERIFIED, "confidence": 0.88})
    await memory_repository.write_anomaly(updated)


async def test_write_mission_view(memory_repository: Repository) -> None:
    mission = MissionView(
        id="m-1",
        kind="VERIFY",
        assigned_agent="ag-1",
        sector_id="s-1",
        phase=MissionPhase.EN_ROUTE,
        progress_pct=42.0,
    )
    await memory_repository.write_mission(mission)


async def test_write_telemetry(memory_repository: Repository) -> None:
    t = Telemetry(
        agent_id="ag-1",
        geo=Geo(lat=44.7, lon=8.03, alt_m=10.0),
        battery_pct=92.0,
    )
    await memory_repository.write_telemetry(t)
    # Second write at same (agent, ts) must be an upsert, not a PK violation.
    await memory_repository.write_telemetry(t)


# ── Mission history: events filtered by mission_id ─────────────────────────


async def test_mission_history_returns_only_mission_events(
    memory_repository: Repository,
) -> None:
    keep = _event(kind=EventKind.MISSION, mission_id="m-42")
    skip = _event(kind=EventKind.PATROL, mission_id="m-99")
    await memory_repository.write_events([keep, skip])

    rows = await memory_repository.mission_history("m-42")
    assert {e.id for e in rows} == {keep.id}


# ── SQL injection sanity ────────────────────────────────────────────────────


async def test_sql_injection_filter_does_not_drop_table(
    memory_repository: Repository,
) -> None:
    """A classic injection payload as a filter must not drop the events table.

    SQLAlchemy parameterizes queries so the payload is treated as a literal
    string — but we verify behavioral safety here, not just trust the lib.
    """
    e = _event()
    await memory_repository.write_events([e])
    payload = "'; DROP TABLE events;--"

    # Both sector and agent filters take string input — exercise both.
    assert await memory_repository.list_events(sector_id=payload) == []
    assert await memory_repository.list_events(agent_id=payload) == []
    assert await memory_repository.list_operator_commands(operator_id=payload) == []

    # The events table must still be intact.
    sm = memory_repository._sm
    assert sm is not None
    async with sm() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM events"))
        assert result.scalar_one() == 1


# ── Helpers ─────────────────────────────────────────────────────────────────


def _event(
    *,
    kind: EventKind = EventKind.SYSTEM,
    sector_id: str | None = None,
    agent_id: str | None = None,
    mission_id: str | None = None,
    body: str = "test",
    ts: datetime | None = None,
) -> Event:
    return Event(
        kind=kind,
        sector_id=sector_id,
        agent_id=agent_id,
        mission_id=mission_id,
        body=body,
        ts=ts or datetime.now(UTC),
    )
