"""Phase 6.D — `/metrics` endpoint tests.

Verifies the RBAC gate, the optional IP-allowlist exemption, and the
shape of the exposition body.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.observability.metrics import reset_for_tests
from backend.app.observability.routes import router as obs_router


@pytest.fixture(autouse=True)
def _fresh_metrics() -> None:
    reset_for_tests()


def _client(client_addr: tuple[str, int] = ("testclient", 50000)) -> TestClient:
    app = FastAPI()
    app.include_router(obs_router)
    return TestClient(app, client=client_addr)


def test_metrics_requires_auth_when_no_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWARM_METRICS_IP_ALLOWLIST", raising=False)
    client = _client()
    resp = client.get("/metrics")
    assert resp.status_code == 401


def test_metrics_rejects_viewer(
    monkeypatch: pytest.MonkeyPatch, viewer_headers: dict[str, str]
) -> None:
    monkeypatch.delenv("SWARM_METRICS_IP_ALLOWLIST", raising=False)
    client = _client()
    resp = client.get("/metrics", headers=viewer_headers)
    assert resp.status_code == 403


def test_metrics_rejects_operator(
    monkeypatch: pytest.MonkeyPatch, operator_headers: dict[str, str]
) -> None:
    monkeypatch.delenv("SWARM_METRICS_IP_ALLOWLIST", raising=False)
    client = _client()
    resp = client.get("/metrics", headers=operator_headers)
    assert resp.status_code == 403


def test_metrics_rejects_commander_without_mfa(
    monkeypatch: pytest.MonkeyPatch,
    commander_headers_no_mfa: dict[str, str],
) -> None:
    """The route is gated by ``require_commander`` which enforces MFA."""
    monkeypatch.delenv("SWARM_METRICS_IP_ALLOWLIST", raising=False)
    client = _client()
    resp = client.get("/metrics", headers=commander_headers_no_mfa)
    assert resp.status_code == 403


def test_metrics_accepts_commander_with_mfa(
    monkeypatch: pytest.MonkeyPatch,
    commander_headers: dict[str, str],
) -> None:
    monkeypatch.delenv("SWARM_METRICS_IP_ALLOWLIST", raising=False)
    client = _client()
    resp = client.get("/metrics", headers=commander_headers)
    assert resp.status_code == 200
    body = resp.text
    # The minimum metric names from the roadmap §6.D bullet list.
    assert "swarm_units_online" in body
    assert "swarm_anomalies_pending" in body
    assert "swarm_actions_total" in body
    assert "swarm_ws_clients" in body
    assert "swarm_mission_duration_seconds" in body
    # The HTTP latency histogram is wired by the middleware, but its
    # metadata HELP/TYPE lines are present even without any observations.
    assert "swarm_http_request_duration_seconds" in body
    # Content-Type must be Prometheus exposition format.
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("text/plain")


def test_metrics_ip_allowlist_grants_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A request from an allowlisted CIDR bypasses the JWT gate."""

    monkeypatch.setenv("SWARM_METRICS_IP_ALLOWLIST", "127.0.0.0/8,10.0.0.0/8")
    client = _client(client_addr=("127.0.0.1", 12345))
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "swarm_units_online" in resp.text


def test_metrics_ip_allowlist_with_non_matching_cidr_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-matching CIDR falls through to the JWT path → 401 without token."""

    monkeypatch.setenv("SWARM_METRICS_IP_ALLOWLIST", "10.0.0.0/8")
    client = _client(client_addr=("192.0.2.1", 12345))
    resp = client.get("/metrics")
    assert resp.status_code == 401


def test_metrics_invalid_allowlist_entry_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed CIDR is logged and skipped; the rest still works."""

    monkeypatch.setenv(
        "SWARM_METRICS_IP_ALLOWLIST", "not-a-cidr,127.0.0.0/8"
    )
    client = _client(client_addr=("127.0.0.1", 12345))
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_metrics_actions_counter_increments(
    monkeypatch: pytest.MonkeyPatch,
    commander_headers: dict[str, str],
) -> None:
    """A direct nudge to the counter shows up in the exposition."""

    from backend.app.observability.metrics import get_metrics

    monkeypatch.delenv("SWARM_METRICS_IP_ALLOWLIST", raising=False)
    get_metrics().actions_total.labels(action="verify", outcome="accepted").inc()
    client = _client()
    resp = client.get("/metrics", headers=commander_headers)
    assert resp.status_code == 200
    assert 'swarm_actions_total{action="verify",outcome="accepted"} 1.0' in resp.text


def test_db_failure_records_metric() -> None:
    """A swallowed repository failure must surface on the counter —
    the audit trail dropping rows can't stay invisible to ops."""

    from backend.app.db.repository import _record_failure
    from backend.app.observability.metrics import get_metrics

    _record_failure("write_events")
    value = get_metrics().registry.get_sample_value(
        "swarm_db_failures_total", {"operation": "write_events"}
    )
    assert value == 1.0


def test_mission_duration_histogram_observes_on_terminal_phase() -> None:
    """A mission seen first as non-terminal then DONE feeds the histogram.

    Guards against the regression where ``swarm_mission_duration_seconds``
    was declared in the registry but never observed anywhere in the
    codebase — leaving an always-empty histogram and a misleading panel.
    """

    from swarm_core.messages import MissionPhase, MissionView

    from backend.app.bus_consumer import BusConsumer
    from backend.app.observability.metrics import get_metrics

    class _Hub:
        async def broadcast(self, _frame: object) -> None:
            return None

    consumer = BusConsumer(_Hub())  # type: ignore[arg-type]
    metric = get_metrics().mission_duration_seconds
    base_count = metric._sum.get()  # type: ignore[attr-defined]

    in_flight = MissionView(id="m-1", kind="PATROL", phase=MissionPhase.EN_ROUTE)
    consumer._observe_mission_duration(in_flight)
    assert "m-1" in consumer._mission_started_at

    done = MissionView(id="m-1", kind="PATROL", phase=MissionPhase.DONE)
    consumer._observe_mission_duration(done)
    assert "m-1" not in consumer._mission_started_at
    assert metric._sum.get() > base_count  # type: ignore[attr-defined]


def test_mission_duration_histogram_skips_when_first_seen_terminal() -> None:
    """A mission only ever observed as DONE contributes no sample.

    We have no start to subtract from — better an empty bucket than a
    fabricated zero.
    """

    from swarm_core.messages import MissionPhase, MissionView

    from backend.app.bus_consumer import BusConsumer
    from backend.app.observability.metrics import get_metrics

    class _Hub:
        async def broadcast(self, _frame: object) -> None:
            return None

    consumer = BusConsumer(_Hub())  # type: ignore[arg-type]
    metric = get_metrics().mission_duration_seconds
    base_count = metric._sum.get()  # type: ignore[attr-defined]

    done_only = MissionView(id="m-late", kind="PATROL", phase=MissionPhase.DONE)
    consumer._observe_mission_duration(done_only)
    assert metric._sum.get() == base_count  # type: ignore[attr-defined]
