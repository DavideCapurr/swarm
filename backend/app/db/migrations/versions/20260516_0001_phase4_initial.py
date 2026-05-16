"""phase 4 — initial persistence schema

Revision ID: 0001_phase4_initial
Revises:
Create Date: 2026-05-16

Creates all Phase 4 tables. On Postgres, additionally:
  - declares `telemetry` and `events` as Timescale hypertables
  - sets a 30-day retention policy on `telemetry`

The Timescale-specific statements are skipped on non-Postgres dialects so
the same migration applies to the test sqlite engine.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_phase4_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False, server_default="vineyard-01"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sector_id", sa.String(length=64), nullable=True),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("mission_id", sa.String(length=64), nullable=True),
        sa.Column("anomaly_id", sa.String(length=64), nullable=True),
        sa.Column("dock_id", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_label", sa.String(length=64), nullable=True),
        # Composite PK: Timescale requires the partition column (`ts`) to be
        # part of every unique index, including the primary key.
        sa.PrimaryKeyConstraint("id", "ts"),
    )
    op.create_index("events_kind_idx", "events", ["kind"])
    op.create_index("events_ts_idx", "events", ["ts"])
    op.create_index("events_sector_id_idx", "events", ["sector_id"])
    op.create_index("events_agent_id_idx", "events", ["agent_id"])
    op.create_index("events_mission_id_idx", "events", ["mission_id"])
    op.create_index("events_kind_ts_idx", "events", ["kind", "ts"])
    op.create_index("events_sector_ts_idx", "events", ["sector_id", "ts"])

    op.create_table(
        "telemetry",
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("alt_m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("yaw_deg", sa.Float(), nullable=False, server_default="0"),
        sa.Column("velocity_mps", sa.Float(), nullable=False, server_default="0"),
        sa.Column("battery_pct", sa.Float(), nullable=False),
        sa.Column("link_quality", sa.Float(), nullable=False, server_default="1.0"),
        sa.PrimaryKeyConstraint("agent_id", "ts"),
    )

    op.create_table(
        "missions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("assigned_agent", sa.String(length=64), nullable=True),
        sa.Column("sector_id", sa.String(length=64), nullable=True),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("eta_s", sa.Float(), nullable=True),
        sa.Column("waypoints", sa.JSON(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("missions_assigned_agent_idx", "missions", ["assigned_agent"])
    op.create_index("missions_sector_id_idx", "missions", ["sector_id"])
    op.create_index("missions_ts_idx", "missions", ["ts"])

    op.create_table(
        "anomalies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("alt_m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sector_id", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("band", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_by", sa.String(length=64), nullable=True),
        sa.Column("verifying_agent", sa.String(length=64), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("anomalies_sector_id_idx", "anomalies", ["sector_id"])
    op.create_index("anomalies_state_idx", "anomalies", ["state"])
    op.create_index("anomalies_ts_idx", "anomalies", ["ts"])

    op.create_table(
        "operator_commands",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=False),
        sa.Column("operator_id", sa.String(length=64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_flight_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejected_reason", sa.String(length=32), nullable=True),
        sa.Column("mission_id", sa.String(length=64), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("operator_commands_operator_id_idx", "operator_commands", ["operator_id"])
    op.create_index("operator_commands_submitted_at_idx", "operator_commands", ["submitted_at"])
    op.create_index("operator_commands_mission_id_idx", "operator_commands", ["mission_id"])

    op.create_table(
        "sector_visits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sector_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("sector_visits_sector_id_idx", "sector_visits", ["sector_id"])
    op.create_index("sector_visits_agent_id_idx", "sector_visits", ["agent_id"])
    op.create_index("sector_visits_visited_at_idx", "sector_visits", ["visited_at"])
    op.create_index("sector_visits_sector_ts_idx", "sector_visits", ["sector_id", "visited_at"])

    # ── Postgres-only: Timescale hypertables + retention policy ──────────────
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # `create_hypertable` is idempotent with `if_not_exists`.
        op.execute(
            "SELECT create_hypertable('telemetry', 'ts', "
            "if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');"
        )
        op.execute(
            "SELECT create_hypertable('events', 'ts', "
            "if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');"
        )
        # 30-day retention on raw telemetry — operator_commands stays permanent.
        op.execute(
            "SELECT add_retention_policy('telemetry', INTERVAL '30 days', "
            "if_not_exists => TRUE);"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("SELECT remove_retention_policy('telemetry', if_exists => TRUE);")

    op.drop_index("sector_visits_sector_ts_idx", table_name="sector_visits")
    op.drop_index("sector_visits_visited_at_idx", table_name="sector_visits")
    op.drop_index("sector_visits_agent_id_idx", table_name="sector_visits")
    op.drop_index("sector_visits_sector_id_idx", table_name="sector_visits")
    op.drop_table("sector_visits")

    op.drop_index("operator_commands_mission_id_idx", table_name="operator_commands")
    op.drop_index("operator_commands_submitted_at_idx", table_name="operator_commands")
    op.drop_index("operator_commands_operator_id_idx", table_name="operator_commands")
    op.drop_table("operator_commands")

    op.drop_index("anomalies_ts_idx", table_name="anomalies")
    op.drop_index("anomalies_state_idx", table_name="anomalies")
    op.drop_index("anomalies_sector_id_idx", table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_index("missions_ts_idx", table_name="missions")
    op.drop_index("missions_sector_id_idx", table_name="missions")
    op.drop_index("missions_assigned_agent_idx", table_name="missions")
    op.drop_table("missions")

    op.drop_table("telemetry")

    op.drop_index("events_sector_ts_idx", table_name="events")
    op.drop_index("events_kind_ts_idx", table_name="events")
    op.drop_index("events_mission_id_idx", table_name="events")
    op.drop_index("events_agent_id_idx", table_name="events")
    op.drop_index("events_sector_id_idx", table_name="events")
    op.drop_index("events_ts_idx", table_name="events")
    op.drop_index("events_kind_idx", table_name="events")
    op.drop_table("events")

    op.drop_table("sessions")
