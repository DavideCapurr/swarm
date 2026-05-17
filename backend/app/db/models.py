"""SQLAlchemy ORM models for Phase 4 persistence.

The schema mirrors the Console-facing aggregates in `core.swarm_core.messages`
(SwarmOS owns the projection; the DB stores the projection's audit trail).

Why a single `events` table and not one-per-kind:
  - the Console renders a unified timeline; events.kind is already the closed
    enum the API queries on
  - mission history is recovered by `WHERE mission_id = ?` over events
  - this matches the bus message shape and keeps the write path single-row

Compatibility notes:
  - This file uses **portable** SQLAlchemy types only. Postgres-specific
    behavior (Timescale hypertables, retention policies) lives in the
    Alembic migration. That lets the test suite run on `sqlite+aiosqlite`
    without a Postgres daemon, while production gets Timescale partitioning.
  - All timestamps are `DateTime(timezone=True)`. SQLite stores naive but
    SQLAlchemy normalizes the Python value to UTC-aware on read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    """Operational session — one per backend boot (or per operator handover)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(64), nullable=False, default="vineyard-01")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventRow(Base):
    """Timeline event — Console reads `/events` from here on cold start.

    PK is composite `(id, ts)`: Timescale requires the partitioning column to
    be part of every UNIQUE index, including the primary key, so a hypertable
    declared on `ts` cannot live with an `id`-only PK.
    """

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mission_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    anomaly_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dock_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("events_kind_ts_idx", "kind", "ts"),
        Index("events_sector_ts_idx", "sector_id", "ts"),
    )


class TelemetryRow(Base):
    """High-rate telemetry sample. Hypertable in Postgres; plain table in tests."""

    __tablename__ = "telemetry"

    # Composite PK (agent_id, ts). Timescale chunks by ts; the composite key
    # keeps idempotency if a tick gets replayed.
    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    alt_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    yaw_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    velocity_mps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    battery_pct: Mapped[float] = mapped_column(Float, nullable=False)
    link_quality: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)


class MissionRow(Base):
    """Latest mission view — one row per mission_id, upserted on phase change."""

    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_agent: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    eta_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    waypoints: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class AnomalyRow(Base):
    """Latest anomaly view — one row per anomaly_id, upserted on state change."""

    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    alt_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sector_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verifying_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class OperatorCommandRow(Base):
    """Audit log of every operator intent — retention permanent."""

    __tablename__ = "operator_commands"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[str] = mapped_column(String(128), nullable=False)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    in_flight_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rejected_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mission_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SectorVisitRow(Base):
    """Coverage history — one row per (sector_id, agent_id, visited_at)."""

    __tablename__ = "sector_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    __table_args__ = (
        Index("sector_visits_sector_ts_idx", "sector_id", "visited_at"),
    )


# ── Phase-4-aware health column: enum-like closure for `EventRow.kind` ───────
#
# The Console enum lives in `core.swarm_core.messages.EventKind`. We keep the
# DB column as a free `String(32)` rather than a Postgres ENUM so adding a new
# kind in a future phase doesn't require a `ALTER TYPE ... ADD VALUE`. The
# Pydantic validator on the read path is what guards the closed set.


__all__ = (
    "AnomalyRow",
    "Base",
    "EventRow",
    "MissionRow",
    "OperatorCommandRow",
    "SectorVisitRow",
    "SessionRow",
    "TelemetryRow",
)
