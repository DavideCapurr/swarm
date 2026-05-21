"""Phase 7.C — DB round-trip for ``events.source`` and ``operator_commands.rule``.

The repository now writes + reads the new columns, and Pydantic
validation on the read path keeps ``source`` inside the closed
{"operator", "autonomy"} set even if a corrupted row sneaks past the
migration default.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from swarm_core.messages import (
    CommandStatus,
    Event,
    EventKind,
    OperatorAction,
    OperatorCommand,
)

from backend.app.db.repository import Repository

pytestmark = pytest.mark.asyncio


def _event(
    *, source: str = "operator", body: str = "operator intent accepted · verify"
) -> Event:
    # Use model_construct to bypass Literal validation on the test seam;
    # production callers always pass a typed source.
    return Event.model_construct(
        kind=EventKind.OPERATOR,
        body=body,
        source=source,  # type: ignore[arg-type]
    )


def _command(
    *,
    source: str = "operator",
    rule: str | None = None,
    cmd_id: str = "cmd-test-1",
) -> OperatorCommand:
    return OperatorCommand.model_construct(
        id=cmd_id,
        action=OperatorAction.VERIFY,
        target="anomaly:a-1",
        operator_id="op-test",
        source=source,  # type: ignore[arg-type]
        rule=rule,
        status=CommandStatus.ACCEPTED,
        submitted_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC),
        ts=datetime.now(UTC),
    )


async def test_event_source_round_trip(memory_repository: Repository) -> None:
    """Both source values round-trip through write_events / list_events."""

    autonomy_event = _event(
        source="autonomy", body="autonomy verify dispatched · R1"
    )
    operator_event = _event()
    await memory_repository.write_events([autonomy_event, operator_event])

    rows = await memory_repository.list_events(limit=10)
    by_id = {r.id: r for r in rows}
    assert by_id[autonomy_event.id].source == "autonomy"
    assert by_id[autonomy_event.id].body == "autonomy verify dispatched · R1"
    assert by_id[operator_event.id].source == "operator"


async def test_legacy_event_rows_default_to_operator(
    memory_repository: Repository,
) -> None:
    """Rows written without a source column (legacy migration) read back as 'operator'."""

    now = datetime.now(UTC)
    async with memory_repository._session() as db:
        await db.execute(
            text(
                "INSERT INTO events (id, ts, kind, body) "
                "VALUES (:id, :ts, :kind, :body)"
            ),
            {"id": "legacy-1", "ts": now, "kind": "anomaly", "body": "legacy row"},
        )
        await db.commit()

    rows = await memory_repository.list_events(limit=10)
    legacy = next(r for r in rows if r.id == "legacy-1")
    assert legacy.source == "operator"


async def test_operator_command_rule_round_trip(
    memory_repository: Repository,
) -> None:
    """`rule` round-trips for autonomy commands and stays None for operator."""

    autonomy_cmd = _command(
        cmd_id="cmd-auto-1", source="autonomy", rule="R1"
    )
    operator_cmd = _command(cmd_id="cmd-op-1", source="operator", rule=None)
    await memory_repository.write_operator_command(autonomy_cmd)
    await memory_repository.write_operator_command(operator_cmd)

    rows = await memory_repository.list_operator_commands(limit=10)
    by_id = {c.id: c for c in rows}
    assert by_id["cmd-auto-1"].rule == "R1"
    assert by_id["cmd-auto-1"].source == "autonomy"
    assert by_id["cmd-op-1"].rule is None
    assert by_id["cmd-op-1"].source == "operator"
