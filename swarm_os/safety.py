"""Safety primitives for the Phase 6.A policy engine.

This module owns the small, side-effect-free data types the policy engine
consumes and emits:

- thresholds (battery / link / weather) — pydantic so they validate at
  YAML load time and surface clear errors on misconfiguration;
- `PolicyDecision` — what the engine returns when validating a mission;
- `SafetyAction` — what the engine emits when a unit needs an auto-RTL
  or auto-hold;
- `WeatherSnapshot` + `WeatherProvider` — the protocol the engine talks
  to. A `LocalStubWeatherProvider` is supplied for dev/CI; real
  providers (OpenWeather, Aviationweather) plug in on hardware day —
  see `docs/ops/drone-day-checklist.md` §2.A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from swarm_core.messages import RejectedReason

# pydantic strict for every config type loaded from YAML — extra keys raise.
_STRICT = ConfigDict(extra="forbid", frozen=True)


# ── threshold types (loaded from site config YAML) ───────────────────────────


class BatteryThresholds(BaseModel):
    """Per-mission-kind battery minimums and the forced-RTL floor.

    `rtl_force_below_pct` is the absolute floor: under it the policy engine
    queues an auto-RTL regardless of the mission in flight. The per-kind
    minimums gate _new_ mission acceptance.
    """

    model_config = _STRICT
    patrol_min_pct: float = Field(30.0, ge=0.0, le=100.0)
    verify_min_pct: float = Field(40.0, ge=0.0, le=100.0)
    rtl_dock_min_pct: float = Field(15.0, ge=0.0, le=100.0)
    rtl_force_below_pct: float = Field(20.0, ge=0.0, le=100.0)

    def required_for(self, mission_kind: str) -> float:
        kind = mission_kind.upper()
        if kind == "PATROL":
            return self.patrol_min_pct
        if kind == "VERIFY":
            return self.verify_min_pct
        if kind == "RTL_DOCK":
            return self.rtl_dock_min_pct
        # COVER and RELAY default to the highest non-RTL bar (operator-visible).
        return self.verify_min_pct


class LinkThresholds(BaseModel):
    """Link-quality bounds. Below `rtl_below_quality` the engine forces RTL."""

    model_config = _STRICT
    min_quality_for_mission: float = Field(0.5, ge=0.0, le=1.0)
    rtl_below_quality: float = Field(0.3, ge=0.0, le=1.0)


class WeatherThresholds(BaseModel):
    """Bounds outside which docks weather-lock. Inclusive of the bound."""

    model_config = _STRICT
    max_wind_mps: float = Field(12.0, ge=0.0)
    min_visibility_km: float = Field(3.0, ge=0.0)
    temp_c_min: float = Field(-5.0)
    temp_c_max: float = Field(40.0)


# ── policy results ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PolicyDecision:
    """What the policy engine returns when asked to validate a mission."""

    allowed: bool
    reason: RejectedReason | None = None
    detail: str = ""

    @classmethod
    def ok(cls) -> PolicyDecision:
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: RejectedReason, detail: str = "") -> PolicyDecision:
        return cls(allowed=False, reason=reason, detail=detail)


class SafetyActionKind(str, Enum):
    AUTO_RTL = "auto_rtl"
    HOLD_PATROL = "hold_patrol"


@dataclass(frozen=True)
class SafetyAction:
    """Engine-emitted action that the coordinator should apply.

    The engine never mutates `SwarmState` directly — it emits these and the
    coordinator decides how to translate them into missions / events.
    """

    agent_id: str
    kind: SafetyActionKind
    reason: RejectedReason
    detail: str
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── weather provider protocol + stub ─────────────────────────────────────────


@dataclass(frozen=True)
class WeatherSnapshot:
    """A single weather reading. `source` is the provider id — never trust
    the value silently; the engine's `evaluate_dock_weather` decides what to
    do with it."""

    wind_mps: float
    visibility_km: float
    temp_c: float
    source: str
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class WeatherProvider(Protocol):
    """Async source of current weather for a given site.

    Real providers must respect a hard timeout and surface failures as
    exceptions; the engine catches and falls back to a safe lock.
    """

    async def current(self, site_id: str) -> WeatherSnapshot: ...


class LocalStubWeatherProvider:
    """Always returns benign weather. Marked `source='stub'` so the policy
    engine and audit log can recognise it. **Not for production** —
    `docs/ops/drone-day-checklist.md` §2.A is the hand-off."""

    def __init__(
        self,
        *,
        wind_mps: float = 3.0,
        visibility_km: float = 10.0,
        temp_c: float = 18.0,
    ) -> None:
        self._wind_mps = wind_mps
        self._visibility_km = visibility_km
        self._temp_c = temp_c

    async def current(self, site_id: str) -> WeatherSnapshot:
        return WeatherSnapshot(
            wind_mps=self._wind_mps,
            visibility_km=self._visibility_km,
            temp_c=self._temp_c,
            source="stub",
        )


__all__ = (
    "BatteryThresholds",
    "LinkThresholds",
    "LocalStubWeatherProvider",
    "PolicyDecision",
    "SafetyAction",
    "SafetyActionKind",
    "WeatherProvider",
    "WeatherSnapshot",
    "WeatherThresholds",
)
