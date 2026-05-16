"""Phase 4 — Alembic migration smoke test.

Verifies the initial migration applies cleanly on a fresh sqlite database.
This catches schema-level breakage in CI without needing Postgres+Timescale.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def test_initial_migration_applies_on_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "phase4.sqlite"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SWARM_ENV", "dev")

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "backend" / "app" / "db" / "migrations"))

    # upgrade to head
    command.upgrade(cfg, "head")

    # If we got here, every CREATE TABLE / CREATE INDEX statement ran.
    # Inspect the resulting schema for the seven Phase 4 tables.
    import sqlite3

    db = sqlite3.connect(db_path)
    try:
        cur = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
    finally:
        db.close()
    for required in {
        "sessions",
        "events",
        "telemetry",
        "missions",
        "anomalies",
        "operator_commands",
        "sector_visits",
    }:
        assert required in tables, f"missing table after upgrade: {required}"

    # downgrade then upgrade again, to prove both directions work.
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
