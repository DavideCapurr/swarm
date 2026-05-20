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
