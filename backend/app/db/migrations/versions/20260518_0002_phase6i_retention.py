"""phase 6.I — retention policy for events

Revision ID: 0002_phase6i_retention
Revises: 0001_phase4_initial
Create Date: 2026-05-18

Adds a 365-day Timescale retention policy on the ``events`` hypertable.
Phase 4 already declared ``events`` as a hypertable (`create_hypertable`,
chunk 7 days) but left it without a retention policy because the
historical view depth was not yet decided. Phase 6.I §retention.md fixes
the policy at 365 days — long enough for a customer-side audit cycle,
short enough that the row count stays manageable on a single-node
deployment.

The migration is a no-op on non-Postgres dialects so the test suite on
``sqlite+aiosqlite`` keeps working unchanged.

Operator-command rows are intentionally **not** subject to a Timescale
retention policy: their retention is 7 years per the compliance table,
enforced by the application's erasure endpoint
(``POST /admin/forget``) rather than by chunk-dropping.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_phase6i_retention"
down_revision: str | None = "0001_phase4_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Retention window — kept in sync with docs/compliance/retention.md.
EVENTS_RETENTION_INTERVAL = "365 days"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "SELECT add_retention_policy('events', INTERVAL "
        f"'{EVENTS_RETENTION_INTERVAL}', if_not_exists => TRUE);"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("SELECT remove_retention_policy('events', if_exists => TRUE);")
