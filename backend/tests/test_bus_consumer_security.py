"""Secure bus gate behavior for backend startup."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.bus_consumer import BusConsumer
from orchestrator.swarm_orchestrator.bus import (
    InsecureBusConfiguration,
    RedisBusSecurity,
    redis_url_from_env,
    secure_bus_required,
)


class _Hub:
    async def broadcast(self, _frame: object) -> None:
        return None


@pytest.mark.asyncio
async def test_bus_consumer_refuses_inmemory_fallback_when_secure_bus_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_REQUIRE_SECURE_BUS", "1")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)

    consumer = BusConsumer(_Hub())  # type: ignore[arg-type]
    with pytest.raises(InsecureBusConfiguration, match="REDIS_URL"):
        await consumer.start()


@pytest.mark.asyncio
async def test_bus_consumer_refuses_plaintext_redis_when_secure_bus_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_REQUIRE_SECURE_BUS", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("REDIS_HOST", raising=False)

    consumer = BusConsumer(_Hub())  # type: ignore[arg-type]
    with pytest.raises(InsecureBusConfiguration, match="rediss://"):
        await consumer.start()


def test_staging_requires_secure_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ENV", "staging")
    monkeypatch.delenv("SWARM_REQUIRE_SECURE_BUS", raising=False)
    assert secure_bus_required() is True


def test_discrete_redis_env_builds_encoded_rediss_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_ENV", "bench")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "0")
    monkeypatch.setenv("REDIS_PASSWORD", "pa:ss@word")

    url = redis_url_from_env()
    assert url == "rediss://:pa%3Ass%40word@redis:6379/0"


def test_rediss_with_mtls_files_is_accepted_when_secure_bus_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ca = tmp_path / "ca.crt"
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"
    for path in (ca, cert, key):
        path.write_text("test", encoding="utf-8")

    monkeypatch.setenv("SWARM_ENV", "staging")
    monkeypatch.setenv("REDIS_TLS_CA_CERTS", str(ca))
    monkeypatch.setenv("REDIS_TLS_CERTFILE", str(cert))
    monkeypatch.setenv("REDIS_TLS_KEYFILE", str(key))

    security = RedisBusSecurity.from_env("rediss://:secret@redis:6379/0")
    assert security.require_mtls is True
