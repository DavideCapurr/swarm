"""Evidence layer — Alembic upgrade/downgrade round-trip for migration 0005.

Pins the `anomalies.evidence` JSON column add/drop on aiosqlite so a future
schema breakage surfaces locally without a Postgres + Timescale container.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def test_evidence_migration_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "evidence.sqlite"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SWARM_ENV", "dev")

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(root / "backend" / "app" / "db" / "migrations")
    )

    def _anomaly_columns() -> set[str]:
        db = sqlite3.connect(db_path)
        try:
            return {
                row[1] for row in db.execute("PRAGMA table_info(anomalies)").fetchall()
            }
        finally:
            db.close()

    command.upgrade(cfg, "head")
    assert "evidence" in _anomaly_columns(), "anomalies.evidence missing after upgrade"

    command.downgrade(cfg, "0004_phase7c_event_source")
    assert "evidence" not in _anomaly_columns(), "anomalies.evidence survived downgrade"

    # Replayable — back up to head.
    command.upgrade(cfg, "head")
    assert "evidence" in _anomaly_columns()
