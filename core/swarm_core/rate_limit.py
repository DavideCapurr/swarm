"""Telemetry rate limiter.

Phase 5 introduces a sanity cap on inbound telemetry from real adapters
(roadmap §Phase 5, security additions). A misbehaving autopilot — or a
malicious MAVLink endpoint — could otherwise saturate the bus with
hundreds of Hz of position frames. The roadmap fixes the cap at 50 Hz.

This is a per-agent leaky-bucket / token-bucket hybrid:
- Each agent has its own budget.
- `should_accept(agent_id, now)` returns True up to `max_hz` calls per
  second; subsequent calls in the same window return False so the caller
  can drop the frame.
- The implementation is pure-Python and lock-free — it is safe to call
  from many async tasks because each agent_id has its own list.

The limiter is deliberately stateful (not a Pydantic model): adapters
instantiate one per process and share it across telemetry consumers.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

#: Default sanity cap on inbound telemetry frames per agent per second.
#: 50 Hz is the upper bound documented in `docs/plan/swarmos-roadmap.md`
#: §Phase 5 "Security additions Phase 5 → Rate-limit telemetry inbound".
DEFAULT_MAX_HZ: float = 50.0


def _monotonic() -> float:
    import time

    return time.monotonic()


class TelemetryRateLimiter:
    """Drops telemetry frames once an agent's inbound rate exceeds `max_hz`.

    The limiter remembers the timestamps of frames it has *accepted* in a
    sliding 1-second window. When a new frame arrives:
      1. Expire timestamps older than `now - 1.0`.
      2. If the window is below `max_hz`, accept and record the timestamp.
      3. Otherwise, return False — the caller drops the frame.

    Memory is bounded: each agent keeps at most `ceil(max_hz)` timestamps.
    """

    def __init__(
        self,
        max_hz: float = DEFAULT_MAX_HZ,
        *,
        clock: Callable[[], float] = _monotonic,
    ) -> None:
        if max_hz <= 0:
            raise ValueError(f"max_hz must be positive, got {max_hz!r}")
        self._max_hz = float(max_hz)
        self._clock = clock
        # Per-agent ring of accepted timestamps within the last second.
        self._windows: dict[str, deque[float]] = {}
        # Counters for diagnostics / tests.
        self._accepted_total = 0
        self._dropped_total = 0

    @property
    def max_hz(self) -> float:
        return self._max_hz

    @property
    def stats(self) -> dict[str, int]:
        return {
            "accepted_total": self._accepted_total,
            "dropped_total": self._dropped_total,
        }

    def should_accept(self, agent_id: str, *, now: float | None = None) -> bool:
        """Return True iff the caller may keep the frame for `agent_id`."""

        if not agent_id:
            raise ValueError("agent_id must be non-empty")
        ts = now if now is not None else self._clock()
        window = self._windows.setdefault(agent_id, deque())
        # Drop timestamps older than 1 second.
        cutoff = ts - 1.0
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self._max_hz:
            self._dropped_total += 1
            return False
        window.append(ts)
        self._accepted_total += 1
        return True

    def reset(self, agent_id: str | None = None) -> None:
        """Clear the window for one agent or all agents."""

        if agent_id is None:
            self._windows.clear()
        else:
            self._windows.pop(agent_id, None)


__all__ = ("DEFAULT_MAX_HZ", "TelemetryRateLimiter")
