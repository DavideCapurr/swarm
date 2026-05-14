"""Database layer — SQLAlchemy + asyncpg, TimescaleDB-aware.

Commit 1 only wires the engine and exposes a session dependency; tables are
created via `infra/postgres/init.sql` (with the TimescaleDB hypertable for
telemetry). Real ORM models land in a follow-up — adding them now would be
unused weight on the demo.
"""

from backend.app.db.session import engine, get_session

__all__ = ["engine", "get_session"]
