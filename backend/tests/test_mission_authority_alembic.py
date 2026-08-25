"""Mission-authority migration round-trip smoke test."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

_TABLES = {
    "mission_authority_grants",
    "mission_decisions",
    "mission_decision_reviews",
}


def _tables(db_path: Path) -> set[str]:
    db = sqlite3.connect(db_path)
    try:
        rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in rows.fetchall()}
    finally:
        db.close()


def test_mission_authority_migration_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mission-authority.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("SWARM_ENV", "dev")

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(root / "backend" / "app" / "db" / "migrations")
    )

    command.upgrade(cfg, "head")
    assert _TABLES.issubset(_tables(db_path))

    command.downgrade(cfg, "0005_anomaly_evidence")
    assert _TABLES.isdisjoint(_tables(db_path))

    command.upgrade(cfg, "head")
    assert _TABLES.issubset(_tables(db_path))
