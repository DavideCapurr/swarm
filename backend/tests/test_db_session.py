"""Phase 4 — engine configuration sanity.

We don't open a real connection here; we only inspect the kwargs that the
session module derives from `DATABASE_URL` + `SWARM_ENV`. The aim is to
prove SSL is enforced outside dev.
"""

from __future__ import annotations

import pytest

from backend.app.db.session import _engine_kwargs, _is_dev, is_persistence_enabled


def test_dev_mode_skips_ssl_for_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ENV", "dev")
    assert _is_dev()
    kw = _engine_kwargs("postgresql+asyncpg://swarm:swarm@localhost:5432/swarm")
    assert "connect_args" not in kw


def test_prod_mode_enforces_ssl_for_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ENV", "prod")
    assert not _is_dev()
    kw = _engine_kwargs("postgresql+asyncpg://swarm:secret@db.example.com:5432/swarm")
    assert kw.get("connect_args") == {"ssl": "require"}


def test_prod_mode_honors_explicit_ssl_in_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the URL already declares ssl behavior, don't double-set it."""
    monkeypatch.setenv("SWARM_ENV", "prod")
    kw = _engine_kwargs("postgresql+asyncpg://u:p@h/db?ssl=disable")
    assert "connect_args" not in kw


def test_sqlite_url_skips_ssl_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ENV", "prod")
    kw = _engine_kwargs("sqlite+aiosqlite:///:memory:")
    assert "connect_args" not in kw
    # SQLite doesn't pool — pre_ping is irrelevant.
    assert "pool_pre_ping" not in kw


def test_persistence_disabled_when_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert is_persistence_enabled() is False


def test_persistence_enabled_when_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    assert is_persistence_enabled() is True
