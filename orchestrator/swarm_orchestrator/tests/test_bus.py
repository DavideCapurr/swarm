from __future__ import annotations

import asyncio
import ssl
from pathlib import Path

import pytest

from orchestrator.swarm_orchestrator.bus import (
    InMemoryBus,
    InsecureBusConfiguration,
    RedisBusSecurity,
    secure_bus_required,
)


@pytest.mark.asyncio
async def test_inmemory_pub_sub_round_trip() -> None:
    bus = InMemoryBus()
    await bus.connect()
    received: list[tuple[str, str]] = []

    async def consume() -> None:
        async for topic, payload in bus.subscribe("swarm:test:*"):
            received.append((topic, payload))
            if len(received) >= 2:
                return

    consumer = asyncio.create_task(consume())
    # Allow the subscription to register before publishing.
    await asyncio.sleep(0.01)
    await bus.publish("swarm:test:a", "1")
    await bus.publish("swarm:test:b", "2")
    await asyncio.wait_for(consumer, timeout=1.0)
    await bus.close()

    assert received == [("swarm:test:a", "1"), ("swarm:test:b", "2")]


@pytest.mark.asyncio
async def test_inmemory_does_not_deliver_unmatched_topics() -> None:
    bus = InMemoryBus()
    await bus.connect()
    received: list[tuple[str, str]] = []

    async def consume() -> None:
        async for topic, payload in bus.subscribe("swarm:foo:*"):
            received.append((topic, payload))

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.publish("swarm:bar:1", "should not be seen")
    await asyncio.sleep(0.05)
    await bus.close()
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer

    assert received == []


def test_secure_bus_not_required_in_dev_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWARM_ENV", raising=False)
    monkeypatch.delenv("SWARM_REQUIRE_SECURE_BUS", raising=False)
    monkeypatch.delenv("REDIS_TLS_CA_CERTS", raising=False)
    monkeypatch.delenv("REDIS_TLS_CERTFILE", raising=False)
    monkeypatch.delenv("REDIS_TLS_KEYFILE", raising=False)

    assert secure_bus_required() is False
    security = RedisBusSecurity.from_env("redis://localhost:6379/0")
    assert security.redis_kwargs() == {}


def test_secure_bus_required_in_prod_rejects_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_ENV", "prod")

    assert secure_bus_required() is True
    with pytest.raises(InsecureBusConfiguration, match="rediss://"):
        RedisBusSecurity.from_env("redis://localhost:6379/0")


def test_secure_bus_requires_mtls_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_REQUIRE_SECURE_BUS", "1")
    monkeypatch.delenv("REDIS_TLS_CA_CERTS", raising=False)
    monkeypatch.delenv("REDIS_TLS_CERTFILE", raising=False)
    monkeypatch.delenv("REDIS_TLS_KEYFILE", raising=False)

    with pytest.raises(InsecureBusConfiguration, match="missing mTLS"):
        RedisBusSecurity.from_env("rediss://redis.example.com:6379/0")


def test_secure_bus_accepts_rediss_mtls_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cert_dir = tmp_path / "redis-mtls"
    cert_dir.mkdir()
    ca = cert_dir / "ca.pem"
    cert = cert_dir / "client.pem"
    key = cert_dir / "client.key"
    for path in (ca, cert, key):
        path.write_text("fixture\n", encoding="utf-8")

    monkeypatch.setenv("SWARM_REQUIRE_SECURE_BUS", "1")
    monkeypatch.setenv("REDIS_TLS_CA_CERTS", str(ca))
    monkeypatch.setenv("REDIS_TLS_CERTFILE", str(cert))
    monkeypatch.setenv("REDIS_TLS_KEYFILE", str(key))

    security = RedisBusSecurity.from_env("rediss://redis.example.com:6379/0")
    kwargs = security.redis_kwargs()
    assert kwargs["ssl_ca_certs"] == str(ca)
    assert kwargs["ssl_certfile"] == str(cert)
    assert kwargs["ssl_keyfile"] == str(key)
    assert kwargs["ssl_cert_reqs"] == ssl.CERT_REQUIRED


def test_tls_cert_and_key_must_be_configured_together(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cert_dir = tmp_path / "redis-partial"
    cert_dir.mkdir()
    cert = cert_dir / "client.pem"
    cert.write_text("fixture\n", encoding="utf-8")
    monkeypatch.setenv("REDIS_TLS_CERTFILE", str(cert))
    monkeypatch.delenv("REDIS_TLS_KEYFILE", raising=False)

    with pytest.raises(InsecureBusConfiguration, match="configured together"):
        RedisBusSecurity.from_env("rediss://redis.example.com:6379/0")


def test_tls_env_requires_rediss_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ca = tmp_path / "ca.pem"
    ca.write_text("fixture\n", encoding="utf-8")
    monkeypatch.setenv("REDIS_TLS_CA_CERTS", str(ca))

    with pytest.raises(InsecureBusConfiguration, match="rediss://"):
        RedisBusSecurity.from_env("redis://localhost:6379/0")
