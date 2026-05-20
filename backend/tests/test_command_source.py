"""Phase 7.B — OperatorCommand.source persistence + API guard tests.

Asserts the additive source column on operator_commands:
  - default value is "operator" on every existing call site
  - "autonomy" round-trips through the repository unchanged
  - the schema validator accepts both literals
  - the HTTP boundary still forces operator-issued commands to a valid
    operator-id (the AUTONOMY_OPERATOR_ID sentinel is unreachable via
    the API even if the caller forges the JSON)

The migration round-trip is covered by the existing
test_alembic_migration.py — this file focuses on the column value flow.
"""

from __future__ import annotations

import pytest
from swarm_core.messages import OperatorAction, OperatorCommand

from backend.app.db.repository import Repository
from backend.app.security import is_valid_operator_id
from swarm_os.command_bus import AUTONOMY_OPERATOR_ID

pytestmark = pytest.mark.asyncio


async def test_operator_command_default_source_is_operator() -> None:
    cmd = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="anomaly:abcd",
        operator_id="op-alice01",
    )
    assert cmd.source == "operator"


async def test_operator_command_schema_accepts_autonomy() -> None:
    cmd = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="anomaly:abcd",
        operator_id=AUTONOMY_OPERATOR_ID,
        source="autonomy",
    )
    assert cmd.source == "autonomy"


async def test_operator_command_schema_rejects_unknown_source() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OperatorCommand(
            action=OperatorAction.VERIFY,
            target="anomaly:abcd",
            operator_id="op-alice01",
            source="rogue-actor",  # type: ignore[arg-type]
        )


async def test_autonomy_source_round_trips_through_repository(
    memory_repository: Repository,
) -> None:
    cmd = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="anomaly:abcd",
        operator_id=AUTONOMY_OPERATOR_ID,
        source="autonomy",
    )
    await memory_repository.write_operator_command(cmd)
    rows = await memory_repository.list_operator_commands()
    assert len(rows) == 1
    assert rows[0].source == "autonomy"
    assert rows[0].operator_id == AUTONOMY_OPERATOR_ID


async def test_operator_source_round_trips_through_repository(
    memory_repository: Repository,
) -> None:
    cmd = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="anomaly:abcd",
        operator_id="op-alice01",
    )
    await memory_repository.write_operator_command(cmd)
    rows = await memory_repository.list_operator_commands()
    assert len(rows) == 1
    assert rows[0].source == "operator"


async def test_autonomy_operator_id_unreachable_via_http_regex() -> None:
    """Defense in depth: even if a caller forges the JSON, the API
    operator-id regex (`^op-[a-z0-9]{4,32}$`) won't accept the sentinel.

    Autonomy must always inject via the in-process command_submit path.
    """

    assert is_valid_operator_id(AUTONOMY_OPERATOR_ID) is False
    assert is_valid_operator_id("op-alice01") is True


async def test_bus_consumer_persists_autonomy_commands(
    memory_repository: Repository,
) -> None:
    """Phase 7.C unblock — autonomy commands surfaced in `state.commands`
    by `_apply_autonomy_decisions` must reach the DB through the bus
    consumer's persistence hook. Without this, autonomy decisions vanish
    at backend restart and the audit log breaks the verifiability
    invariant (PDF §10).
    """

    from unittest.mock import AsyncMock, MagicMock

    from swarm_core.messages import OperatorCommand as Cmd

    from backend.app.bus_consumer import BusConsumer
    from backend.app.db import repository as repo_module

    # Inject the in-memory repository globally so the bus consumer's
    # `get_repository()` returns the test instance.
    original = repo_module._REPOSITORY  # type: ignore[attr-defined]
    repo_module.set_repository(memory_repository)
    try:
        consumer = BusConsumer(MagicMock())
        # Seed an autonomy + an operator command directly in state.commands
        # — the bus consumer's `_persist_new_autonomy_commands` should
        # pick up only the autonomy row.
        autonomy_cmd = Cmd(
            action=OperatorAction.VERIFY,
            target="anomaly:abcd",
            operator_id=AUTONOMY_OPERATOR_ID,
            source="autonomy",
        )
        operator_cmd = Cmd(
            action=OperatorAction.VERIFY,
            target="anomaly:wxyz",
            operator_id="op-alice01",
            source="operator",
        )
        consumer._coordinator.state.commands[autonomy_cmd.id] = autonomy_cmd
        consumer._coordinator.state.commands[operator_cmd.id] = operator_cmd

        await consumer._persist_new_autonomy_commands()

        rows = await memory_repository.list_operator_commands()
        ids = {r.id for r in rows}
        assert autonomy_cmd.id in ids, (
            "autonomy command must be persisted by the bus consumer"
        )
        assert operator_cmd.id not in ids, (
            "operator commands are persisted via the HTTP route, not this hook"
        )

        # Idempotent — re-running the hook does not re-write.
        n_before = len(rows)
        await consumer._persist_new_autonomy_commands()
        rows_again = await memory_repository.list_operator_commands()
        assert len(rows_again) == n_before, (
            "the seen-set must prevent re-writes of already-persisted rows"
        )

        # New autonomy command on a later tick is picked up.
        autonomy_cmd2 = Cmd(
            action=OperatorAction.ESCALATE,
            target="anomaly:abcd",
            operator_id=AUTONOMY_OPERATOR_ID,
            source="autonomy",
        )
        consumer._coordinator.state.commands[autonomy_cmd2.id] = autonomy_cmd2
        await consumer._persist_new_autonomy_commands()
        rows_after = await memory_repository.list_operator_commands()
        assert autonomy_cmd2.id in {r.id for r in rows_after}

        # Cleanup the seeded state so other tests don't see these rows.
        del consumer._coordinator.state.commands[autonomy_cmd.id]
        del consumer._coordinator.state.commands[operator_cmd.id]
        del consumer._coordinator.state.commands[autonomy_cmd2.id]
    finally:
        repo_module._REPOSITORY = original  # type: ignore[attr-defined]
    # Mock kept around to avoid the linter complaining about unused import.
    _ = AsyncMock
