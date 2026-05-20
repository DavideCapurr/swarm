"""phase 7.B — add `source` column to operator_commands

Revision ID: 0003_phase7b_command_source
Revises: 0002_phase6i_retention
Create Date: 2026-05-20

Adds the ``source`` column to ``operator_commands`` so Phase 7.B autonomy
decisions can land in the same audit log as operator intents but stay
distinguishable. Default ``operator`` backfills historical rows
correctly (every existing row was, by definition, operator-issued).

Portable across PostgreSQL (Timescale) and SQLite (test path):
``op.add_column`` issues a plain ``ALTER TABLE ... ADD COLUMN`` on both
dialects, and ``server_default`` makes the migration safe against
concurrent writes during the rollout.

Downgrade drops the column; SQLite's batch mode rebuilds the table so
the migration round-trip stays clean on aiosqlite (the existing
``test_alembic_migration.py`` pattern).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase7b_command_source"
down_revision: str | None = "0002_phase6i_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "operator_commands",
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="operator",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("operator_commands") as batch_op:
        batch_op.drop_column("source")
