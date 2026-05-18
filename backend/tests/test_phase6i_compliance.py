"""Phase 6.I — compliance endpoint tests.

Covers ``POST /admin/export`` and ``POST /admin/forget``:

* Auth + RBAC + MFA gating (401 anon, 403 viewer / operator /
  commander-no-mfa).
* Body validation (extra fields, missing confirmation, wrong phrase,
  invalid operator_id shape, already-erased subject).
* Happy-path semantics: export returns the persisted operator_commands
  + audit-event rows that reference the subject; erasure rewrites
  the operator id to the deterministic pseudonym; both append a
  ``system`` audit event with the actor + subject and broadcast on
  the hub.
* Rate limiter (1/min/commander).
* Metrics increments.
* Voice-clean audit copy (§5.2 forbidden tokens absent).
* Repository helpers exercised against an aiosqlite memory engine.

The repository singleton is swapped via ``set_repository`` in the
``swap_repo`` fixture so the tests run on a real persistence layer
without touching Postgres.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from swarm_core.messages import (
    CommandStatus,
    OperatorAction,
    OperatorCommand,
)

from backend.app.api.compliance import (
    ERASED_PREFIX,
    ERASURE_PHRASE,
    _compliance_limiter,
    _pseudonymise,
)
from backend.app.api.compliance import router as compliance_router
from backend.app.db import set_repository
from backend.app.db.models import Base
from backend.app.db.repository import Repository
from backend.app.hub import HUB
from backend.app.observability.metrics import get_metrics
from swarm_os import COORDINATOR, SWARM_STATE

EXPORT_PATH = "/admin/export"
FORGET_PATH = "/admin/forget"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _reset_singletons() -> None:
    SWARM_STATE.events.clear()
    SWARM_STATE.commands.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.anomalies.clear()
    COORDINATOR.events.__init__()  # type: ignore[misc]
    _compliance_limiter._buckets.clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def isolate_state() -> Iterator[None]:
    _reset_singletons()
    yield
    _reset_singletons()


@pytest_asyncio.fixture
async def swap_repo() -> AsyncIterator[Repository]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    repo = Repository(sm)
    set_repository(repo)
    yield repo
    set_repository(Repository(None))
    await engine.dispose()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(compliance_router)
    return TestClient(app)


async def _seed_operator_commands(
    repo: Repository, subject: str, count: int = 2
) -> list[OperatorCommand]:
    """Write `count` accepted operator commands for `subject`."""
    base_ts = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    cmds: list[OperatorCommand] = []
    for i in range(count):
        cmd = OperatorCommand(
            action=OperatorAction.VERIFY,
            target=f"sector-{i:02d}",
            operator_id=subject,
            status=CommandStatus.COMPLETED,
            submitted_at=base_ts + timedelta(seconds=i * 5),
            ts=base_ts + timedelta(seconds=i * 5),
            mission_id=f"mission-{i:02d}",
        )
        await repo.write_operator_command(cmd)
        cmds.append(cmd)
    return cmds


# ── /admin/export — auth ──────────────────────────────────────────────────────


def test_export_returns_401_without_token() -> None:
    client = _client()
    r = client.post(EXPORT_PATH, json={"operator_id": "op-operator01"})
    assert r.status_code == 401


def test_export_returns_403_for_viewer(viewer_headers: dict[str, str]) -> None:
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": "op-operator01"},
        headers=viewer_headers,
    )
    assert r.status_code == 403


def test_export_returns_403_for_operator(
    operator_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": "op-operator01"},
        headers=operator_headers,
    )
    assert r.status_code == 403


def test_export_returns_403_for_commander_without_mfa(
    commander_headers_no_mfa: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": "op-operator01"},
        headers=commander_headers_no_mfa,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "mfa_required"


# ── /admin/export — body validation ───────────────────────────────────────────


def test_export_rejects_missing_operator_id(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(EXPORT_PATH, json={}, headers=commander_headers)
    assert r.status_code == 422


def test_export_rejects_extra_fields(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": "op-operator01", "include_telemetry": True},
        headers=commander_headers,
    )
    assert r.status_code == 422


def test_export_rejects_malformed_operator_id(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": "OP-WITH-CAPS"},
        headers=commander_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_operator_id"


# ── /admin/export — happy path ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_returns_subject_commands(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    cmds = await _seed_operator_commands(swap_repo, subject, count=3)
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"] == subject
    assert body["exported_at"]
    assert body["audit_event_id"]
    returned_ids = [c["id"] for c in body["operator_commands"]]
    assert returned_ids == [c.id for c in cmds]
    for row in body["operator_commands"]:
        assert row["operator_id"] == subject


@pytest.mark.asyncio
async def test_export_ignores_other_operators(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    """The export must scope strictly to the requested operator."""
    await _seed_operator_commands(swap_repo, "op-operator01", count=2)
    await _seed_operator_commands(swap_repo, "op-other99", count=2)
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": "op-operator01"},
        headers=commander_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["operator_commands"]) == 2
    assert all(c["operator_id"] == "op-operator01" for c in body["operator_commands"])


@pytest.mark.asyncio
async def test_export_appends_audit_event(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=1)
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"subject": subject, "operator_id": subject},  # extra "subject" → 422
        headers=commander_headers,
    )
    # Defensive: with extra="forbid" this is a 422; if it ever changes
    # to 200 the audit assertion below would still hold.
    assert r.status_code == 422
    # Now the proper call:
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert r.status_code == 200
    bodies = [e.body for e in SWARM_STATE.events]
    matches = [b for b in bodies if "data export" in b and subject in b]
    assert matches, bodies
    assert "op-commander01" in matches[-1]


@pytest.mark.asyncio
async def test_export_broadcasts_on_ws(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    received: list[dict[str, object]] = []

    class _FakeSocket:
        async def send_text(self, payload: str) -> None:
            received.append(json.loads(payload))

    fake = _FakeSocket()
    HUB._clients.add(fake)  # type: ignore[arg-type]
    try:
        subject = "op-operator01"
        await _seed_operator_commands(swap_repo, subject, count=1)
        client = _client()
        r = client.post(
            EXPORT_PATH,
            json={"operator_id": subject},
            headers=commander_headers,
        )
        assert r.status_code == 200
        kinds = [m.get("kind") for m in received]
        assert "event" in kinds
    finally:
        HUB._clients.discard(fake)  # type: ignore[arg-type]


# ── /admin/forget — auth ──────────────────────────────────────────────────────


def test_forget_returns_401_without_token() -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
    )
    assert r.status_code == 401


def test_forget_returns_403_for_viewer(viewer_headers: dict[str, str]) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=viewer_headers,
    )
    assert r.status_code == 403


def test_forget_returns_403_for_operator(
    operator_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=operator_headers,
    )
    assert r.status_code == 403


def test_forget_returns_403_for_commander_without_mfa(
    commander_headers_no_mfa: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers_no_mfa,
    )
    assert r.status_code == 403


# ── /admin/forget — body validation ───────────────────────────────────────────


def test_forget_rejects_missing_confirm(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 422


def test_forget_rejects_confirm_false(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": False,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 422


def test_forget_rejects_wrong_phrase(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": True,
            "confirmation_phrase": "erase operator data",  # wrong case
        },
        headers=commander_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "erasure_confirmation_required"


def test_forget_rejects_extra_fields(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "op-operator01",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
            "delete_operator_yaml": True,  # not a field
        },
        headers=commander_headers,
    )
    assert r.status_code == 422


def test_forget_rejects_malformed_operator_id(
    commander_headers: dict[str, str],
) -> None:
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": "OPERATOR",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_operator_id"


def test_forget_rejects_already_erased_pseudonym(
    commander_headers: dict[str, str],
) -> None:
    """Defence in depth: re-anonymising a pseudonym would mask the audit
    trail. The endpoint refuses ids that start with the erased prefix.

    The pseudonym itself does *not* match ``is_valid_operator_id`` (the
    regex forbids extra dashes), so the request is rejected at the
    operator-id validation step with ``invalid_operator_id`` — exactly
    the right outcome, but reached one branch earlier. Either way the
    pseudonym cannot be re-anonymised."""

    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": f"{ERASED_PREFIX}deadbeefdeadbeef",
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] in {"invalid_operator_id", "already_erased"}


# ── /admin/forget — happy path ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forget_anonymises_operator_commands(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=3)
    pseudonym = _pseudonymise(subject)
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": subject,
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"] == subject
    assert body["pseudonym"] == pseudonym
    assert body["rewritten"] == 3
    # Round-trip: a subsequent export against the original subject
    # finds zero rows (the operator_id column was rewritten).
    r2 = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    # 429 on the second call to the limiter — explicitly clear it for
    # this assertion.
    _compliance_limiter._buckets.clear()  # type: ignore[attr-defined]
    r2 = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["operator_commands"] == []


@pytest.mark.asyncio
async def test_forget_is_idempotent(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=2)
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": subject,
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 200
    assert r.json()["rewritten"] == 2
    # Clear the limiter so a second call passes the rate gate.
    _compliance_limiter._buckets.clear()  # type: ignore[attr-defined]
    r2 = client.post(
        FORGET_PATH,
        json={
            "operator_id": subject,
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["rewritten"] == 0


@pytest.mark.asyncio
async def test_forget_appends_audit_event(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=1)
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": subject,
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 200
    bodies = [e.body for e in SWARM_STATE.events]
    matches = [b for b in bodies if "data erasure" in b and subject in b]
    assert matches, bodies
    assert "op-commander01" in matches[-1]
    assert _pseudonymise(subject) in matches[-1]


# ── Rate limiter ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compliance_limiter_blocks_second_call(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=1)
    client = _client()
    first = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert first.status_code == 200
    second = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert second.status_code == 429
    assert second.json()["detail"] == "rate_limited"


# ── Metrics ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_metrics_counter_increments(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=1)
    metrics = get_metrics()
    before = metrics.actions_total.labels(
        action="data_export", outcome="accepted"
    )._value.get()
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert r.status_code == 200
    after = metrics.actions_total.labels(
        action="data_export", outcome="accepted"
    )._value.get()
    assert after == before + 1


@pytest.mark.asyncio
async def test_forget_metrics_counter_increments(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=1)
    metrics = get_metrics()
    before = metrics.actions_total.labels(
        action="data_erasure", outcome="accepted"
    )._value.get()
    client = _client()
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": subject,
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 200
    after = metrics.actions_total.labels(
        action="data_erasure", outcome="accepted"
    )._value.get()
    assert after == before + 1


# ── Voice-clean audit copy ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_bodies_are_voice_clean(
    swap_repo: Repository,
    commander_headers: dict[str, str],
) -> None:
    """No forbidden voice tokens in any audit body emitted from this module."""

    from swarm_core.voice import FORBIDDEN_WORDS

    subject = "op-operator01"
    await _seed_operator_commands(swap_repo, subject, count=1)
    client = _client()
    r = client.post(
        EXPORT_PATH,
        json={"operator_id": subject},
        headers=commander_headers,
    )
    assert r.status_code == 200
    _compliance_limiter._buckets.clear()  # type: ignore[attr-defined]
    r = client.post(
        FORGET_PATH,
        json={
            "operator_id": subject,
            "confirm": True,
            "confirmation_phrase": ERASURE_PHRASE,
        },
        headers=commander_headers,
    )
    assert r.status_code == 200
    for event in SWARM_STATE.events:
        for word in FORBIDDEN_WORDS:
            assert word not in event.body, (
                f"forbidden word {word!r} in {event.body!r}"
            )


# ── Pseudonym determinism ─────────────────────────────────────────────────────


def test_pseudonym_is_deterministic() -> None:
    a = _pseudonymise("op-someone")
    b = _pseudonymise("op-someone")
    c = _pseudonymise("op-someoneelse")
    assert a == b
    assert a != c
    assert a.startswith(ERASED_PREFIX)
    # 16 hex chars after the prefix.
    assert len(a) == len(ERASED_PREFIX) + 16


# ── Repository helpers (independent of HTTP layer) ────────────────────────────


@pytest.mark.asyncio
async def test_repo_export_emits_correlated_events(
    memory_repository: Repository,
) -> None:
    """An event whose body references the operator id is included in the
    export even if the row has no explicit operator_id column."""

    from swarm_core.messages import Event, EventKind

    subject = "op-operator01"
    cmds = await _seed_operator_commands(memory_repository, subject, count=1)
    await memory_repository.write_events(
        [
            Event(
                kind=EventKind.SYSTEM,
                body=f"login by {subject}",
            ),
            Event(
                kind=EventKind.SYSTEM,
                body="login by op-someoneelse",  # different subject
            ),
            Event(
                kind=EventKind.MISSION,
                mission_id=cmds[0].mission_id,
                body="patrol started",
            ),
        ]
    )
    payload = await memory_repository.export_operator(subject)
    bodies = [e["body"] for e in payload["events"]]
    assert f"login by {subject}" in bodies
    assert "patrol started" in bodies  # correlated via mission_id
    assert "login by op-someoneelse" not in bodies


@pytest.mark.asyncio
async def test_repo_prune_old_rows(memory_repository: Repository) -> None:
    """Application-level prune drops only the rows older than the cut-off."""
    from swarm_core.messages import Session as SessionMsg

    now = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    fresh = SessionMsg(label="fresh", site_id="vineyard-01", started_at=now, ts=now)
    old = SessionMsg(
        label="old",
        site_id="vineyard-01",
        started_at=now - timedelta(days=400),
        ts=now - timedelta(days=400),
    )
    await memory_repository.write_session(fresh)
    await memory_repository.write_session(old)
    await memory_repository.write_sector_visit(
        "sec-001", "sim-1", now - timedelta(days=400), 0.9
    )
    await memory_repository.write_sector_visit(
        "sec-002", "sim-1", now, 0.95
    )
    cut_off = now - timedelta(days=365)
    deleted = await memory_repository.prune_old_rows(
        sessions_older_than=cut_off,
        sector_visits_older_than=cut_off,
    )
    assert deleted["sessions"] == 1
    assert deleted["sector_visits"] == 1
