"""phase 7.C — add ``source`` to events and ``rule`` to operator_commands

Revision ID: 0004_phase7c_event_source
Revises: 0003_phase7b_command_source
Create Date: 2026-05-20

Surfaces the Phase 7.B autonomy baseline on the events table so an
offline auditor can spot autonomy decisions without joining against
``operator_commands``. The default ``operator`` backfills historical
rows correctly (every pre-7.C event was, by definition, operator-issued).

Also adds ``operator_commands.rule`` so the Console can render the rule
label (``R1`` / ``R2`` / ``R3``) on the AUTO eyebrow without parsing
free-form copy. Nullable, no backfill — every operator command keeps
``rule = NULL`` and any pre-7.C autonomy row also stays NULL.

Portable across PostgreSQL (Timescale) and SQLite (test path):

- ``events`` is a Timescale hypertable on ``ts``. Adding a new column
  is allowed in-place on a hypertable, and the composite PK ``(id, ts)``
  is unaffected by a non-key column add. The ``server_default`` keeps
  the migration safe against concurrent writes during the rollout.
- ``operator_commands`` is a plain table; ``op.add_column`` on a
  nullable column is constant-time on both dialects.

Downgrade drops the two columns; SQLite's batch mode rebuilds the
tables so the migration round-trip stays clean on aiosqlite (the
existing ``test_alembic_migration.py`` pattern).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase7c_event_source"
down_revision: str | None = "0003_phase7b_command_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="operator",
        ),
    )
    op.add_column(
        "operator_commands",
        sa.Column("rule", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("operator_commands") as batch_op:
        batch_op.drop_column("rule")
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_column("source")
