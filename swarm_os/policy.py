"""Phase 6.A safety policy engine.

The engine is the single decision point for "is this mission safe?" and
"does any unit need to be auto-recalled?". It is side-effect free —
methods return `PolicyDecision` or `list[SafetyAction]`; the coordinator
turns those into state mutations + WS events.

Inputs:
  - `SiteConfig` (geofence, thresholds) — loaded once from
    `infra/config/sites/<site_id>.yaml`.
  - `WeatherProvider` (typically `LocalStubWeatherProvider` in CI;
    OpenWeather / Aviationweather plug in on hardware day — see
    `docs/ops/drone-day-checklist.md` §2.A).
  - The current `units` and `docks` slices of `SwarmState`.

The engine caches the weather snapshot for
`SiteConfig.weather_provider.refresh_interval_s` and fails closed
(returns `None` → safe-default lock) on any provider error.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from swarm_core.geometry import path_within_polygon
from swarm_core.messages import (
    DockState,
    MissionView,
    RejectedReason,
    UnitState,
)

from swarm_os.safety import (
    PolicyDecision,
    SafetyAction,
    SafetyActionKind,
    WeatherProvider,
    WeatherSnapshot,
)
from swarm_os.sites import SiteConfig

logger = logging.getLogger("swarm_os.policy")

WEATHER_PROVIDER_TIMEOUT_S = 10.0


class PolicyEngine:
    """Side-effect-free safety + geofence + weather + battery + link policy."""

    def __init__(
        self,
        site_config: SiteConfig,
        weather_provider: WeatherProvider,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.site = site_config
        self.weather_provider = weather_provider
        self._clock = clock or (lambda: datetime.now(UTC))
        self._weather_cache: WeatherSnapshot | None = None
        self._weather_cache_at: datetime | None = None

    # ── weather ──────────────────────────────────────────────────────────────

    async def current_weather(self) -> WeatherSnapshot | None:
        """Return the cached snapshot if fresh, else fetch.

        Fails closed: provider exceptions and timeouts return `None`, which
        `is_weather_locked` interprets as "lock the dock".
        """

        now = self._clock()
        refresh_s = self.site.weather_provider.refresh_interval_s
        if (
            self._weather_cache is not None
            and self._weather_cache_at is not None
            and (now - self._weather_cache_at).total_seconds() < refresh_s
        ):
            return self._weather_cache
        try:
            snap = await asyncio.wait_for(
                self.weather_provider.current(self.site.site_id),
                timeout=WEATHER_PROVIDER_TIMEOUT_S,
            )
        except Exception as exc:
            logger.warning(
                "weather provider failed; treating dock as locked",
                extra={"site_id": self.site.site_id, "error": repr(exc)},
            )
            return None
        self._weather_cache = snap
        self._weather_cache_at = now
        return snap

    def is_weather_locked(self, snapshot: WeatherSnapshot | None) -> bool:
        """Translate a snapshot into the boolean dock weather_lock.

        `None` is the safe-default lock — used when the provider is
        unreachable. Any threshold violation also locks.
        """

        if snapshot is None:
            return True
        thr = self.site.thresholds.weather
        return (
            snapshot.wind_mps > thr.max_wind_mps
            or snapshot.visibility_km < thr.min_visibility_km
            or snapshot.temp_c < thr.temp_c_min
            or snapshot.temp_c > thr.temp_c_max
        )

    # ── mission validation ───────────────────────────────────────────────────

    async def validate_mission(
        self,
        mission: MissionView,
        *,
        units: Mapping[str, UnitState],
        docks: Mapping[str, DockState],
    ) -> PolicyDecision:
        """Check geofence, altitude ceiling, battery, link, and weather.

        `RTL_DOCK` is intentionally exempt from the weather-lock branch:
        if conditions are bad, the *return-to-launch* path is the safety
        action, not the thing to block. The auto-RTL emitter relies on
        this exemption.
        """

        polygon = list(self.site.geofence.polygon)
        if mission.waypoints and not path_within_polygon(list(mission.waypoints), polygon):
            return PolicyDecision.deny(
                RejectedReason.OUTSIDE_GEOFENCE,
                f"mission {mission.id} waypoints or trajectory outside site geofence",
            )
        max_alt = self.site.geofence.max_alt_m
        for wp in mission.waypoints:
            if wp.alt_m > max_alt:
                return PolicyDecision.deny(
                    RejectedReason.OUTSIDE_GEOFENCE,
                    f"waypoint alt {wp.alt_m:.1f} m exceeds site max {max_alt:.1f} m",
                )
        if mission.assigned_agent is not None:
            unit = units.get(mission.assigned_agent)
            if unit is not None:
                required = self.site.thresholds.battery.required_for(mission.kind)
                if unit.battery_pct < required:
                    return PolicyDecision.deny(
                        RejectedReason.BATTERY_TOO_LOW,
                        f"unit {unit.agent_id} battery {unit.battery_pct:.0f}% < "
                        f"required {required:.0f}% for {mission.kind}",
                    )
                link_min = self.site.thresholds.link.min_quality_for_mission
                if unit.link_quality < link_min:
                    return PolicyDecision.deny(
                        RejectedReason.LINK_TOO_WEAK,
                        f"unit {unit.agent_id} link {unit.link_quality:.2f} "
                        f"below min {link_min:.2f}",
                    )
        if mission.kind.upper() != "RTL_DOCK":
            primary_docks = [d for d in docks.values() if d.primary]
            if primary_docks and all(d.weather_lock for d in primary_docks):
                return PolicyDecision.deny(
                    RejectedReason.WEATHER_LOCK,
                    "primary dock weather-locked; only RTL_DOCK allowed",
                )
        return PolicyDecision.ok()

    # ── safety actions (auto-RTL) ────────────────────────────────────────────

    def evaluate_safety_actions(
        self, units: Mapping[str, UnitState]
    ) -> list[SafetyAction]:
        """For each airborne unit, decide whether to queue an auto-RTL.

        Docked units (`unit.dock_id is not None`) are skipped — they have
        already returned. Per-unit checks short-circuit: a battery
        violation suppresses the link check for the same unit so the
        audit log only shows the most pressing reason.
        """

        actions: list[SafetyAction] = []
        rtl_battery = self.site.thresholds.battery.rtl_force_below_pct
        rtl_link = self.site.thresholds.link.rtl_below_quality
        for unit in units.values():
            if unit.dock_id is not None:
                continue
            if unit.battery_pct < rtl_battery:
                actions.append(
                    SafetyAction(
                        agent_id=unit.agent_id,
                        kind=SafetyActionKind.AUTO_RTL,
                        reason=RejectedReason.BATTERY_TOO_LOW,
                        detail=f"battery {unit.battery_pct:.0f}% below floor {rtl_battery:.0f}%",
                    )
                )
                continue
            if unit.link_quality < rtl_link:
                actions.append(
                    SafetyAction(
                        agent_id=unit.agent_id,
                        kind=SafetyActionKind.AUTO_RTL,
                        reason=RejectedReason.LINK_TOO_WEAK,
                        detail=f"link {unit.link_quality:.2f} below floor {rtl_link:.2f}",
                    )
                )
        return actions

    # ── priority resolution ──────────────────────────────────────────────────

    @staticmethod
    def resolve_priorities(missions: list[MissionView]) -> list[MissionView]:
        """Stable sort by descending `priority`.

        The scheduler consumes the result first-to-last when picking what
        to dispatch next; emergency missions (priority ≥ 100) precede
        operator commands (≥50), which precede auto-PATROL (≥10).
        """

        return sorted(missions, key=lambda m: -m.priority)


__all__ = ("WEATHER_PROVIDER_TIMEOUT_S", "PolicyEngine")
