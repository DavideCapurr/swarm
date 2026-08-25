"""mission-scoped authority grants and append-only decision audit

Revision ID: 0006_mission_authority
Revises: 0005_anomaly_evidence
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_mission_authority"
down_revision: str | None = "0005_anomaly_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mission_authority_grants",
        sa.Column("grant_id", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("objective_id", sa.String(length=64), nullable=False),
        sa.Column("holder_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("grant_id", "revision"),
    )
    op.create_index(
        "ix_mission_authority_grants_objective_id",
        "mission_authority_grants",
        ["objective_id"],
    )
    op.create_index(
        "ix_mission_authority_grants_holder_id",
        "mission_authority_grants",
        ["holder_id"],
    )
    op.create_table(
        "mission_decisions",
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("objective_id", sa.String(length=64), nullable=False),
        sa.Column("objective_revision", sa.Integer(), nullable=False),
        sa.Column("decision_kind", sa.String(length=40), nullable=False),
        sa.Column("authority_verdict", sa.String(length=24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index("ix_mission_decisions_objective_id", "mission_decisions", ["objective_id"])
    op.create_index("ix_mission_decisions_decision_kind", "mission_decisions", ["decision_kind"])
    op.create_index(
        "ix_mission_decisions_authority_verdict",
        "mission_decisions",
        ["authority_verdict"],
    )
    op.create_table(
        "mission_decision_reviews",
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("objective_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index(
        "ix_mission_decision_reviews_decision_id",
        "mission_decision_reviews",
        ["decision_id"],
    )
    op.create_index(
        "ix_mission_decision_reviews_objective_id",
        "mission_decision_reviews",
        ["objective_id"],
    )
    op.create_index("ix_mission_decision_reviews_action", "mission_decision_reviews", ["action"])
    op.create_index("ix_mission_decision_reviews_actor_id", "mission_decision_reviews", ["actor_id"])


def downgrade() -> None:
    op.drop_table("mission_decision_reviews")
    op.drop_table("mission_decisions")
    op.drop_table("mission_authority_grants")
