"""Fuzz tests for SwarmOS Pydantic models.

The goal is robustness, not correctness: parse a wide range of inputs and
make sure the validator never crashes uncontrollably (e.g. exceeds a sane
time/memory bound). Pydantic v2 should raise ValidationError on bad input;
we assert that, and nothing escapes as a different exception class.

Light-weight scaffolding for Phase 0 — random inputs only. Phase 1 can
swap in `hypothesis` for property-based coverage once we depend on it.
"""

from __future__ import annotations

import contextlib
import random
import string

import pytest
from pydantic import ValidationError
from swarm_core.messages import (
    AwarenessBreakdown,
    Event,
    Geo,
    OperatorCommand,
    UnitState,
)

random.seed(20260514)  # deterministic across CI runs

# Strings the parser must never crash on. Mixes ascii, unicode, control chars,
# SQL/HTML-y payloads, very long strings, empty, whitespace.
_BAD_STRINGS = [
    "",
    " " * 100,
    "\x00\x01\x02",
    "𓂀" * 200,  # unicode astral plane
    "a" * 10_000,
    "<script>alert(1)</script>",
    "'; DROP TABLE events;--",
    "../" * 64,
    "\n\r\t",
    "{}[]<>",
    "0",
    "false",
    "null",
]


@pytest.mark.parametrize("s", _BAD_STRINGS)
def test_event_body_never_crashes_validator(s: str) -> None:
    """Whatever string we put in body must parse or ValidationError; nothing else."""
    with contextlib.suppress(ValidationError):
        Event.model_validate({"kind": "system", "body": s})


@pytest.mark.parametrize("s", _BAD_STRINGS)
def test_operator_command_target_never_crashes(s: str) -> None:
    with contextlib.suppress(ValidationError):
        OperatorCommand.model_validate(
            {
                "action": "verify",
                "target": s,
                "operator_id": "op-davide",
            }
        )


def test_geo_bounds_fuzz() -> None:
    """Many random lat/lon — exactly the inside ones validate."""
    for _ in range(500):
        lat = random.uniform(-200, 200)
        lon = random.uniform(-400, 400)
        try:
            Geo(lat=lat, lon=lon)
            assert -90 <= lat <= 90 and -180 <= lon <= 180
        except ValidationError:
            assert not (-90 <= lat <= 90 and -180 <= lon <= 180)


def test_awareness_score_fuzz() -> None:
    """Score must be clamped to [0, 100]."""
    for _ in range(200):
        score = random.uniform(-1000, 1000)
        try:
            AwarenessBreakdown(score=score)
            assert 0 <= score <= 100
        except ValidationError:
            assert not (0 <= score <= 100)


def test_unit_state_minimal_random_battery() -> None:
    """Random battery_pct only validates when in [0, 100]."""
    for _ in range(200):
        b = random.uniform(-50, 200)
        try:
            UnitState(
                agent_id="d-1",
                vendor="x",
                model="y",
                fsm_state="DOCKED",  # type: ignore[arg-type]
                battery_pct=b,
                geo=Geo(lat=0, lon=0),
            )
            assert 0 <= b <= 100
        except ValidationError:
            assert not (0 <= b <= 100)


def _rand_str(n: int) -> str:
    return "".join(random.choices(string.printable, k=n))


def test_event_random_kind_field() -> None:
    """An unknown `kind` value should ValidationError, never crash."""
    for _ in range(100):
        candidate = _rand_str(random.randint(1, 30))
        with contextlib.suppress(ValidationError):
            Event.model_validate({"kind": candidate, "body": "x"})
