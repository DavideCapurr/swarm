"""Phase 6.G — HTTP-side tests for ``POST /actions/emergency-rtl-all``.

The kernel mechanics are covered in
``swarm_os/tests/test_phase6_emergency.py``. These tests target only
the API surface: auth + RBAC + MFA, the double-confirmation envelope,
the dedicated rate limiter, the audit + WS broadcast side-effects,
and the structured error shape.

Every test cleans the COORDINATOR / SWARM_STATE under it so the
shared singleton does not leak between tests.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from swarm_core.messages import AgentState, Geo, UnitState

from backend.app.api.actions import _emergency_limiter
from backend.app.api.actions import router as actions_router
from backend.app.hub import HUB
from backend.app.observability.metrics import get_metrics
from swarm_os import COORDINATOR, SWARM_STATE
from swarm_os.command_bus import EMERGENCY_MISSION_PREFIX

EMERGENCY_PATH = "/actions/emergency-rtl-all"
EMERGENCY_PHRASE = "RETURN ALL UNITS"


def _reset_state() -> None:
    SWARM_STATE.missions.clear()
    SWARM_STATE.commands.clear()
    SWARM_STATE.events.clear()
    SWARM_STATE.units.clear()
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.hold_patrol = False
    SWARM_STATE.emergency_active_at = None
    # Drop coordinator event-detector memory so a previous test's
    # anomaly transitions don't bleed into this one.
    COORDINATOR.events.__init__()  # type: ignore[misc]
    # Empty the dedicated emergency limiter so the 1/min bucket is full.
    _emergency_limiter._buckets.clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def isolate_state() -> Iterator[None]:
    _reset_state()
    yield
    _reset_state()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(actions_router)
    return TestClient(app)


def _seed_airborne_unit(agent_id: str = "sim-air-1") -> None:
    SWARM_STATE.units[agent_id] = UnitState(
        agent_id=agent_id,
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=80.0,
        geo=Geo(lat=44.700, lon=8.030, alt_m=15.0),
    )


# ── Auth + RBAC ───────────────────────────────────────────────────────────────


def test_emergency_returns_401_without_token() -> None:
    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
    )
    assert r.status_code == 401


def test_emergency_returns_403_for_viewer(viewer_headers: dict[str, str]) -> None:
    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=viewer_headers,
    )
    assert r.status_code == 403


def test_emergency_returns_403_for_operator(
    operator_headers: dict[str, str],
) -> None:
    """Operator role is not enough — commander floor is required."""

    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=operator_headers,
    )
    assert r.status_code == 403


def test_emergency_returns_403_for_commander_without_mfa(
    commander_headers_no_mfa: dict[str, str],
) -> None:
    """A commander whose access token carries ``mfa=False`` is rejected.

    Re-checked on every commander-only endpoint: the issuer cannot
    promote a non-MFA token after the fact."""

    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers_no_mfa,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "mfa_required"


# ── Double-confirmation envelope ──────────────────────────────────────────────


def test_emergency_rejects_missing_confirm_field(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    # Pydantic strict — missing field → 422.
    assert r.status_code == 422


def test_emergency_rejects_confirm_false(commander_headers: dict[str, str]) -> None:
    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": False, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    # Pydantic Literal[True] rejects False → 422.
    assert r.status_code == 422


def test_emergency_rejects_wrong_phrase(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": "return all units"},  # wrong case
        headers=commander_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "emergency_confirmation_required"


def test_emergency_rejects_extra_fields(commander_headers: dict[str, str]) -> None:
    """``extra="forbid"`` guards against smuggled fields."""

    client = _client()
    r = client.post(
        EMERGENCY_PATH,
        json={
            "confirm": True,
            "confirmation_phrase": EMERGENCY_PHRASE,
            "override_safety": True,  # not a real field
        },
        headers=commander_headers,
    )
    assert r.status_code == 422


# ── Happy path ────────────────────────────────────────────────────────────────


def test_emergency_dispatches_rtl_for_every_airborne_unit(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    _seed_airborne_unit("sim-air-1")
    _seed_airborne_unit("sim-air-2")
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["command_id"]
    assert body["status"] == "completed"
    spawned = {
        m.assigned_agent
        for m in SWARM_STATE.missions.values()
        if m.id.startswith(EMERGENCY_MISSION_PREFIX)
    }
    assert spawned == {"sim-air-1", "sim-air-2"}


def test_emergency_appends_audit_event(
    commander_headers: dict[str, str],
) -> None:
    """The system event records the operator + count + bypass note."""

    client = _client()
    _seed_airborne_unit("sim-air-1")
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    assert r.status_code == 202
    audit_bodies = [e.body for e in SWARM_STATE.events]
    matches = [b for b in audit_bodies if "emergency rtl all triggered" in b]
    assert matches, audit_bodies
    body = matches[-1]
    assert "op-commander01" in body
    assert "safety policy bypassed" in body


def test_emergency_broadcasts_event_on_ws(
    commander_headers: dict[str, str],
) -> None:
    """A connected WS client sees the system event without polling."""

    import json

    received: list[dict[str, object]] = []

    class _FakeSocket:
        async def send_text(self, payload: str) -> None:
            received.append(json.loads(payload))

    fake = _FakeSocket()
    HUB._clients.add(fake)  # type: ignore[arg-type]
    try:
        _seed_airborne_unit("sim-air-1")
        client = _client()
        r = client.post(
            EMERGENCY_PATH,
            json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
            headers=commander_headers,
        )
        assert r.status_code == 202
        # We expect at least one system Event frame in the receive log.
        kinds = [m.get("kind") for m in received]
        assert "event" in kinds
    finally:
        HUB._clients.discard(fake)  # type: ignore[arg-type]


# ── Rate limiter ──────────────────────────────────────────────────────────────


def test_emergency_rate_limit_blocks_second_call(
    commander_headers: dict[str, str],
) -> None:
    """The dedicated 1/min limiter rejects the second call.

    The rejected command is still audited with RATE_LIMITED so abuse is
    visible in the operator timeline.
    """

    client = _client()
    _seed_airborne_unit("sim-air-1")
    first = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    assert first.status_code == 202
    second = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    assert second.status_code == 429
    body = second.json()
    assert body["status"] == "rejected"
    assert body["rejected_reason"] == "rate_limited"


def test_emergency_metrics_counter_increments(
    commander_headers: dict[str, str],
) -> None:
    """``swarm_actions_total{action="emergency_rtl_all",outcome="accepted"}``
    moves by exactly one on a happy-path call."""

    client = _client()
    _seed_airborne_unit("sim-air-1")
    metrics = get_metrics()
    before = metrics.actions_total.labels(
        action="emergency_rtl_all", outcome="accepted"
    )._value.get()
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    assert r.status_code == 202
    after = metrics.actions_total.labels(
        action="emergency_rtl_all", outcome="accepted"
    )._value.get()
    assert after == before + 1


# ── Confidence-bound audit copy ───────────────────────────────────────────────


def test_emergency_audit_event_is_voice_clean(
    commander_headers: dict[str, str],
) -> None:
    """The audit body must not carry any FORBIDDEN_WORDS — voice §5.2.

    "emergency" itself is not on the forbidden list (it is a domain
    word, not a marketing one), but "alarm" / "Intruder" / "Manual" /
    "fly drone" / "red-alert" / "red state" are. The audit body the
    backend writes must stay clean even though the route name is
    'emergency-rtl-all'."""

    client = _client()
    _seed_airborne_unit("sim-air-1")
    r = client.post(
        EMERGENCY_PATH,
        json={"confirm": True, "confirmation_phrase": EMERGENCY_PHRASE},
        headers=commander_headers,
    )
    assert r.status_code == 202
    from swarm_core.voice import FORBIDDEN_WORDS

    for event in SWARM_STATE.events:
        for word in FORBIDDEN_WORDS:
            assert word not in event.body, f"forbidden word {word!r} in {event.body!r}"


