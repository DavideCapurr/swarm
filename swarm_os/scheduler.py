"""Minimal Phase 1 patrol scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from swarm_core.messages import DockState

PATROL_INTERVAL_S = 300


class _StateLike(Protocol):
    docks: dict[str, DockState]


def next_patrol_at(dock: DockState, now: datetime) -> datetime:
    if dock.next_patrol_at and dock.next_patrol_at > now:
        return dock.next_patrol_at
    return now + timedelta(seconds=PATROL_INTERVAL_S)


def tick(state: _StateLike, now: datetime) -> None:
    """Refresh dock schedule metadata in memory."""

    for dock_id, dock in list(state.docks.items()):
        state.docks[dock_id] = dock.model_copy(
            update={
                "next_patrol_at": next_patrol_at(dock, now),
                "ts": now,
            }
        )
