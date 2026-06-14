"""evidence layer — add ``evidence`` JSON column to anomalies

Revision ID: 0005_anomaly_evidence
Revises: 0004_phase7c_event_source
Create Date: 2026-06-14

Additive evidence layer (Phase-7 extension): every anomaly can now carry its
provenance (``source``) + triggering signal (``metric`` / ``value`` /
``baseline`` / ``unit``) + the server-built ``headline``, persisted as a JSON
blob alongside the projected anomaly view.

Portable across PostgreSQL and SQLite (test path):

- ``anomalies`` is a plain table (not a Timescale hypertable), so there is no
  partition-column-in-unique-index rule to satisfy and ``op.add_column`` is a
  constant-time metadata change on both dialects.
- The column is nullable with no ``server_default``; every historical anomaly
  row stays ``evidence = NULL`` (it predates the evidence layer).

Downgrade drops the column; SQLite's batch mode rebuilds the table so the
round-trip stays clean on aiosqlite (the existing migration test pattern).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_anomaly_evidence"
down_revision: str | None = "0004_phase7c_event_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "anomalies",
        sa.Column("evidence", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("anomalies") as batch_op:
        batch_op.drop_column("evidence")
