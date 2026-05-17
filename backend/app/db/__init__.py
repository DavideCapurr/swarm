"""Database layer — SQLAlchemy async + TimescaleDB for Phase 4.

Public surface:
  - `init_persistence()` / `shutdown_persistence()` — engine lifecycle.
  - `is_persistence_enabled()` — True iff `DATABASE_URL` is set.
  - `Repository` — async write + read API (no-op when disabled).
  - `REPOSITORY` — module-level singleton used by the bus consumer + actions.
  - `Base` + ORM rows — exposed for Alembic + tests.

When `DATABASE_URL` is unset the module is in "disabled" mode: writes are
no-ops, reads return `[]`, and the demo/tests run without a Postgres daemon.
"""

from backend.app.db.models import (
    AnomalyRow,
    Base,
    EventRow,
    MissionRow,
    OperatorCommandRow,
    SectorVisitRow,
    SessionRow,
    TelemetryRow,
)
from backend.app.db.repository import Repository, get_repository, set_repository
from backend.app.db.session import (
    get_session,
    get_sessionmaker,
    init_persistence,
    is_persistence_enabled,
    make_engine,
    shutdown_persistence,
)

__all__ = (
    "AnomalyRow",
    "Base",
    "EventRow",
    "MissionRow",
    "OperatorCommandRow",
    "Repository",
    "SectorVisitRow",
    "SessionRow",
    "TelemetryRow",
    "get_repository",
    "get_session",
    "get_sessionmaker",
    "init_persistence",
    "is_persistence_enabled",
    "make_engine",
    "set_repository",
    "shutdown_persistence",
)
