"""Tests for `swarm_core.rate_limit.TelemetryRateLimiter`."""

from __future__ import annotations

import pytest

from swarm_core.rate_limit import DEFAULT_MAX_HZ, TelemetryRateLimiter


def test_default_cap_matches_roadmap() -> None:
    # Pin the default so a relaxed cap shows up in code review.
    assert DEFAULT_MAX_HZ == 50.0


def test_rejects_non_positive_max_hz() -> None:
    with pytest.raises(ValueError):
        TelemetryRateLimiter(max_hz=0.0)
    with pytest.raises(ValueError):
        TelemetryRateLimiter(max_hz=-1.0)


def test_accepts_up_to_cap_in_one_second() -> None:
    fake_now = [0.0]

    def clock() -> float:
        return fake_now[0]

    limiter = TelemetryRateLimiter(max_hz=10.0, clock=clock)
    accepted = 0
    for _ in range(10):
        if limiter.should_accept("agent-1"):
            accepted += 1
        fake_now[0] += 0.01  # 100 Hz — all 10 fit in the first second
    assert accepted == 10


def test_drops_above_cap() -> None:
    fake_now = [0.0]

    def clock() -> float:
        return fake_now[0]

    limiter = TelemetryRateLimiter(max_hz=5.0, clock=clock)
    accepted = 0
    dropped = 0
    for _ in range(10):
        # All 10 calls within the same second; only 5 should be accepted.
        if limiter.should_accept("agent-1"):
            accepted += 1
        else:
            dropped += 1
        fake_now[0] += 0.001
    assert accepted == 5
    assert dropped == 5
    assert limiter.stats["dropped_total"] == 5


def test_window_slides_after_one_second() -> None:
    fake_now = [0.0]

    def clock() -> float:
        return fake_now[0]

    limiter = TelemetryRateLimiter(max_hz=2.0, clock=clock)
    assert limiter.should_accept("agent-1")
    assert limiter.should_accept("agent-1")
    assert not limiter.should_accept("agent-1")
    # Advance time by 1.5 s — both earlier timestamps fall out of the window.
    fake_now[0] += 1.5
    assert limiter.should_accept("agent-1")
    assert limiter.should_accept("agent-1")


def test_per_agent_isolation() -> None:
    fake_now = [0.0]

    def clock() -> float:
        return fake_now[0]

    limiter = TelemetryRateLimiter(max_hz=2.0, clock=clock)
    assert limiter.should_accept("a")
    assert limiter.should_accept("a")
    assert not limiter.should_accept("a")
    # Different agent has its own bucket.
    assert limiter.should_accept("b")
    assert limiter.should_accept("b")
    assert not limiter.should_accept("b")


def test_reset_clears_one_agent() -> None:
    fake_now = [0.0]
    limiter = TelemetryRateLimiter(max_hz=1.0, clock=lambda: fake_now[0])
    assert limiter.should_accept("a")
    assert not limiter.should_accept("a")
    limiter.reset("a")
    assert limiter.should_accept("a")


def test_reset_clears_all_agents() -> None:
    fake_now = [0.0]
    limiter = TelemetryRateLimiter(max_hz=1.0, clock=lambda: fake_now[0])
    limiter.should_accept("a")
    limiter.should_accept("b")
    limiter.reset()
    assert limiter.should_accept("a")
    assert limiter.should_accept("b")


def test_rejects_empty_agent_id() -> None:
    limiter = TelemetryRateLimiter(max_hz=10.0)
    with pytest.raises(ValueError):
        limiter.should_accept("")


def test_explicit_now_overrides_clock() -> None:
    # When the caller already knows the timestamp (e.g., from a frame's
    # ts field) the limiter must use it instead of the wall clock.
    limiter = TelemetryRateLimiter(max_hz=1.0, clock=lambda: 0.0)
    assert limiter.should_accept("a", now=0.0)
    assert not limiter.should_accept("a", now=0.5)
    assert limiter.should_accept("a", now=1.5)


def test_50hz_default_in_practice() -> None:
    fake_now = [0.0]

    def clock() -> float:
        return fake_now[0]

    limiter = TelemetryRateLimiter(clock=clock)
    accepted = 0
    for _ in range(100):
        if limiter.should_accept("hot-drone"):
            accepted += 1
        fake_now[0] += 0.005  # 200 Hz inbound
    # Only the first 50 fit in the 1-second window.
    assert accepted == 50
