"""Async repository — write the projected SwarmOS view to the DB; query history.

Design:
  - Single class so the bus consumer holds one handle.
  - Every write is best-effort: a DB failure logs and continues so the live
    Console isn't taken down by a transient Postgres hiccup.
  - Reads return Pydantic models (the same types the REST API serializes) so
    the API layer can pass results straight through without re-conversion.
  - When `sessionmaker` is None, every method is a no-op for writes and an
    empty list for reads — that's the "persistence disabled" mode.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from swarm_core.messages import (
    AnomalyView,
    Event,
    EventKind,
    MissionView,
    OperatorCommand,
    Telemetry,
)
from swarm_core.messages import (
    Session as SessionMsg,
)

from backend.app.db.models import (
    AnomalyRow,
    EventRow,
    MissionRow,
    OperatorCommandRow,
    SectorVisitRow,
    SessionRow,
    TelemetryRow,
)

logger = logging.getLogger("backend.db.repo")

# Hard upper bound for any history query — defense against unbounded scans.
MAX_QUERY_LIMIT = 1000


class Repository:
    """Persistence operations. Safe to instantiate with `sessionmaker=None`."""

    def __init__(
        self, sessionmaker_: async_sessionmaker[AsyncSession] | None
    ) -> None:
        self._sm = sessionmaker_

    @property
    def enabled(self) -> bool:
        return self._sm is not None

    # ── Internals ────────────────────────────────────────────────────────────

    def _session(self) -> AsyncSession:
        if self._sm is None:
            raise RuntimeError("repository persistence is disabled")
        return self._sm()

    # ── Writes ───────────────────────────────────────────────────────────────

    async def write_session(self, session: SessionMsg) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as db:
                await self._upsert(
                    db,
                    SessionRow,
                    [
                        {
                            "id": session.id,
                            "label": session.label,
                            "site_id": session.site_id,
                            "started_at": session.started_at,
                            "ts": session.ts,
                        }
                    ],
                    pk_cols=("id",),
                )
                await db.commit()
        except Exception:  # pragma: no cover — defensive
            logger.exception("write_session failed")

    async def write_telemetry(self, telemetry: Telemetry) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as db:
                row = {
                    "agent_id": telemetry.agent_id,
                    "ts": telemetry.ts,
                    "lat": telemetry.geo.lat,
                    "lon": telemetry.geo.lon,
                    "alt_m": telemetry.geo.alt_m,
                    "yaw_deg": telemetry.attitude.yaw_deg,
                    "velocity_mps": telemetry.velocity_mps,
                    "battery_pct": telemetry.battery_pct,
                    "link_quality": telemetry.link_quality,
                }
                await self._upsert(db, TelemetryRow, [row], pk_cols=("agent_id", "ts"))
                await db.commit()
        except Exception:  # pragma: no cover
            logger.exception("write_telemetry failed")

    async def write_anomaly(self, anomaly: AnomalyView) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as db:
                row = {
                    "id": anomaly.id,
                    "kind": anomaly.kind.value,
                    "lat": anomaly.geo.lat,
                    "lon": anomaly.geo.lon,
                    "alt_m": anomaly.geo.alt_m,
                    "sector_id": anomaly.sector_id,
                    "confidence": anomaly.confidence,
                    "band": anomaly.band.value,
                    "state": anomaly.state.value,
                    "detected_at": anomaly.detected_at,
                    "detected_by": anomaly.detected_by,
                    "verifying_agent": anomaly.verifying_agent,
                    "ts": anomaly.ts,
                }
                await self._upsert(db, AnomalyRow, [row], pk_cols=("id",))
                await db.commit()
        except Exception:  # pragma: no cover
            logger.exception("write_anomaly failed")

    async def write_mission(self, mission: MissionView) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as db:
                row = {
                    "id": mission.id,
                    "kind": mission.kind,
                    "assigned_agent": mission.assigned_agent,
                    "sector_id": mission.sector_id,
                    "phase": mission.phase.value,
                    "progress_pct": mission.progress_pct,
                    "eta_s": mission.eta_s,
                    "waypoints": [wp.model_dump(mode="json") for wp in mission.waypoints],
                    "ts": mission.ts,
                }
                await self._upsert(db, MissionRow, [row], pk_cols=("id",))
                await db.commit()
        except Exception:  # pragma: no cover
            logger.exception("write_mission failed")

    async def write_operator_command(self, command: OperatorCommand) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as db:
                row = {
                    "id": command.id,
                    "action": command.action.value,
                    "target": command.target,
                    "operator_id": command.operator_id,
                    "submitted_at": command.submitted_at,
                    "accepted_at": command.accepted_at,
                    "in_flight_at": command.in_flight_at,
                    "completed_at": command.completed_at,
                    "status": command.status.value,
                    "rejected_reason": (
                        command.rejected_reason.value
                        if command.rejected_reason is not None
                        else None
                    ),
                    "mission_id": command.mission_id,
                    "ts": command.ts,
                }
                await self._upsert(db, OperatorCommandRow, [row], pk_cols=("id",))
                await db.commit()
        except Exception:  # pragma: no cover
            logger.exception("write_operator_command failed")

    async def write_events(self, events: Iterable[Event]) -> None:
        if not self.enabled:
            return
        rows = [
            {
                "id": e.id,
                "kind": e.kind.value,
                "ts": e.ts,
                "sector_id": e.sector_id,
                "agent_id": e.agent_id,
                "mission_id": e.mission_id,
                "anomaly_id": e.anomaly_id,
                "dock_id": e.dock_id,
                "confidence": e.confidence,
                "body": e.body,
                "action_label": e.action_label,
            }
            for e in events
        ]
        if not rows:
            return
        try:
            async with self._session() as db:
                await self._upsert(db, EventRow, rows, pk_cols=("id",))
                await db.commit()
        except Exception:  # pragma: no cover
            logger.exception("write_events failed")

    async def write_sector_visit(
        self, sector_id: str, agent_id: str, visited_at: datetime, confidence: float
    ) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as db:
                db.add(
                    SectorVisitRow(
                        sector_id=sector_id,
                        agent_id=agent_id,
                        visited_at=visited_at,
                        confidence=confidence,
                    )
                )
                await db.commit()
        except Exception:  # pragma: no cover
            logger.exception("write_sector_visit failed")

    # ── Reads ────────────────────────────────────────────────────────────────

    async def list_events(
        self,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        kind: EventKind | None = None,
        sector_id: str | None = None,
        agent_id: str | None = None,
        mission_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        if not self.enabled:
            return []
        limit = min(max(1, limit), MAX_QUERY_LIMIT)
        try:
            async with self._session() as db:
                stmt = select(EventRow).order_by(EventRow.ts.desc()).limit(limit)
                if from_ts is not None:
                    stmt = stmt.where(EventRow.ts >= from_ts)
                if to_ts is not None:
                    stmt = stmt.where(EventRow.ts <= to_ts)
                if kind is not None:
                    stmt = stmt.where(EventRow.kind == kind.value)
                if sector_id is not None:
                    stmt = stmt.where(EventRow.sector_id == sector_id)
                if agent_id is not None:
                    stmt = stmt.where(EventRow.agent_id == agent_id)
                if mission_id is not None:
                    stmt = stmt.where(EventRow.mission_id == mission_id)
                result = await db.execute(stmt)
                rows = result.scalars().all()
                # Reverse to chronological order — matches the in-memory deque.
                return [_row_to_event(r) for r in reversed(rows)]
        except Exception:  # pragma: no cover
            logger.exception("list_events failed")
            return []

    async def list_operator_commands(
        self,
        *,
        operator_id: str | None = None,
        limit: int = 100,
    ) -> list[OperatorCommand]:
        if not self.enabled:
            return []
        limit = min(max(1, limit), MAX_QUERY_LIMIT)
        try:
            async with self._session() as db:
                stmt = (
                    select(OperatorCommandRow)
                    .order_by(OperatorCommandRow.submitted_at.desc())
                    .limit(limit)
                )
                if operator_id is not None:
                    stmt = stmt.where(OperatorCommandRow.operator_id == operator_id)
                result = await db.execute(stmt)
                rows = result.scalars().all()
                return [_row_to_command(r) for r in reversed(rows)]
        except Exception:  # pragma: no cover
            logger.exception("list_operator_commands failed")
            return []

    async def mission_history(self, mission_id: str, limit: int = 200) -> list[Event]:
        """Return the chronological event timeline for one mission."""
        return await self.list_events(mission_id=mission_id, limit=limit)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    async def _upsert(
        db: AsyncSession,
        model: type[Any],
        rows: Sequence[dict[str, Any]],
        *,
        pk_cols: tuple[str, ...],
    ) -> None:
        """Dialect-aware upsert — Postgres `ON CONFLICT`, SQLite `INSERT OR REPLACE`.

        Why we use both dialects: the test suite runs on sqlite+aiosqlite to
        keep CI hermetic; production runs Postgres. SQLAlchemy core's generic
        `insert` does not emit ON CONFLICT semantics on its own.
        """
        if not rows:
            return
        bind = db.get_bind()
        dialect = bind.dialect.name
        if dialect == "postgresql":
            pg_stmt = pg_insert(model).values(rows)
            pg_updates = {
                c.name: pg_stmt.excluded[c.name]
                for c in model.__table__.columns
                if c.name not in pk_cols
            }
            await db.execute(
                pg_stmt.on_conflict_do_update(
                    index_elements=list(pk_cols), set_=pg_updates
                )
            )
        elif dialect == "sqlite":
            sl_stmt = sqlite_insert(model).values(rows)
            sl_updates = {
                c.name: sl_stmt.excluded[c.name]
                for c in model.__table__.columns
                if c.name not in pk_cols
            }
            await db.execute(
                sl_stmt.on_conflict_do_update(
                    index_elements=list(pk_cols), set_=sl_updates
                )
            )
        else:  # pragma: no cover — only sqlite/postgres expected
            # Fallback: best-effort merge per row.
            for row in rows:
                pk = {k: row[k] for k in pk_cols}
                existing = await db.get(model, tuple(pk.values()))
                if existing is None:
                    db.add(model(**row))
                else:
                    for k, v in row.items():
                        setattr(existing, k, v)


def _row_to_event(r: EventRow) -> Event:
    return Event(
        id=r.id,
        kind=EventKind(r.kind),
        ts=r.ts,
        sector_id=r.sector_id,
        agent_id=r.agent_id,
        mission_id=r.mission_id,
        anomaly_id=r.anomaly_id,
        dock_id=r.dock_id,
        confidence=r.confidence,
        body=r.body,
        action_label=r.action_label,
    )


def _row_to_command(r: OperatorCommandRow) -> OperatorCommand:
    from swarm_core.messages import CommandStatus, OperatorAction, RejectedReason

    return OperatorCommand(
        id=r.id,
        action=OperatorAction(r.action),
        target=r.target,
        operator_id=r.operator_id,
        submitted_at=r.submitted_at,
        accepted_at=r.accepted_at,
        in_flight_at=r.in_flight_at,
        completed_at=r.completed_at,
        status=CommandStatus(r.status),
        rejected_reason=(
            RejectedReason(r.rejected_reason) if r.rejected_reason else None
        ),
        mission_id=r.mission_id,
        ts=r.ts,
    )


# ── Module-level singleton (set by `init_persistence` in main lifespan) ──────
#
# Modules that need to write (bus_consumer, actions, routes) call
# `get_repository()` so a test fixture's `set_repository` swap is picked up.
# Binding via `from backend.app.db import REPOSITORY` would snapshot the
# pre-init no-op instance.

_REPOSITORY: Repository = Repository(None)


def get_repository() -> Repository:
    return _REPOSITORY


def set_repository(repo: Repository) -> None:
    """Replace the module-level repository (called from FastAPI lifespan)."""
    global _REPOSITORY
    _REPOSITORY = repo


# Re-export so callers don't need to import sqlalchemy bits.
__all__ = (
    "MAX_QUERY_LIMIT",
    "Repository",
    "delete",
    "get_repository",
    "set_repository",
)
