"""Phase 7.C — Alembic upgrade/downgrade round-trip for migration 0004.

`make audit`'s aiosqlite path runs the whole migration chain; this
specific test pins the round-trip for 0004 so a future schema breakage
surfaces locally without needing a Postgres + Timescale container.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def test_phase7c_migration_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "phase7c.sqlite"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SWARM_ENV", "dev")

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(root / "backend" / "app" / "db" / "migrations")
    )

    # Bring the schema up to head — through migration 0004.
    command.upgrade(cfg, "head")

    db = sqlite3.connect(db_path)
    try:
        events_columns = {
            row[1] for row in db.execute("PRAGMA table_info(events)").fetchall()
        }
        ops_columns = {
            row[1]
            for row in db.execute("PRAGMA table_info(operator_commands)").fetchall()
        }
    finally:
        db.close()
    assert "source" in events_columns, "events.source missing after upgrade"
    assert "rule" in ops_columns, "operator_commands.rule missing after upgrade"

    # Step back one migration; both new columns should disappear.
    command.downgrade(cfg, "-1")
    db = sqlite3.connect(db_path)
    try:
        events_columns = {
            row[1] for row in db.execute("PRAGMA table_info(events)").fetchall()
        }
        ops_columns = {
            row[1]
            for row in db.execute("PRAGMA table_info(operator_commands)").fetchall()
        }
    finally:
        db.close()
    assert "source" not in events_columns, "events.source survived downgrade"
    assert "rule" not in ops_columns, "operator_commands.rule survived downgrade"

    # Re-upgrade to prove the migration is replayable.
    command.upgrade(cfg, "head")
