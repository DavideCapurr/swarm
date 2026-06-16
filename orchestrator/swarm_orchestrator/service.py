"""Orchestrator service — auction loop, mission dispatch, fleet aggregation.

The orchestrator listens for `Anomaly` events, opens auctions, awards missions
to the best-scored adapter, dispatches `execute_mission`, and re-publishes
`MissionProgress`. It uses `AdapterRegistry` to look up adapters by
`agent_id` — never importing any vendor-specific class.

Two reactive loops run concurrently:

  - `_anomaly_loop` opens a VERIFY auction for every anomaly. When the fleet
    is flying continuous patrol and no unit is docked, the nearest airborne
    unit is *diverted* to the verify — the realistic behaviour: a patrolling
    unit peels off, confirms, then returns to its sweep.
  - `_patrol_loop` keeps the whole fleet sweeping when `continuous_patrol` is
    on. Each idle docked unit is dispatched a PATROL loop over its own wedge
    of the territory, so the map is never static and every unit moves. Patrol
    progress is deliberately **not** published on the bus: only VERIFY
    missions emit `MissionProgress`, because a completed mission is what the
    truth layer treats as a verification (`coordinator._promote_verified_
    anomaly`). Patrol flights still move the drones, so telemetry + fleet
    frames animate the Console without touching the verify-loop.

`continuous_patrol` defaults to off so the deterministic test fixtures and the
single-shot acceptance flow are unchanged; the sim runner turns it on.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from swarm_core.allocator import build_bid, eligible, select_winner
from swarm_core.geometry import haversine_m
from swarm_core.messages import (
    AgentState,
    Anomaly,
    Award,
    FleetState,
    Geo,
    MissionTask,
)
from swarm_core.missions import PATROL, VERIFY

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import Bus

if TYPE_CHECKING:  # pragma: no cover
    from sim.swarm_sim.drone import Drone

logger = logging.getLogger("swarm.orchestrator")

AUCTION_WINDOW_S = 0.5
MIN_BATTERY_PCT = 25.0
_M_PER_DEG = 111_000.0  # equirectangular approximation, matches the sim


@dataclass
class Orchestrator:
    bus: Bus
    registry: AdapterRegistry
    # `world_drones` is optional: when running with the simulated adapter, we
    # use it as the ground truth for fleet state because telemetry bus latency
    # would otherwise slow down the auction.
    world_drones: list[Drone] | None = None
    # How long to hover when running a VERIFY mission triggered by an anomaly.
    # Production default is realistic (15 s); tests may override.
    verify_hover_s: float = 15.0
    # ── continuous patrol (sim runner opt-in) ────────────────────────────────
    # When on, idle docked units are kept sweeping their own wedge of the
    # territory so the Console map is alive and every unit moves.
    continuous_patrol: bool = False
    patrol_origin: Geo | None = None
    patrol_radius_m: float = 130.0
    patrol_altitude_m: float = 55.0
    patrol_period_s: float = 4.0
    min_patrol_battery_pct: float = 35.0
    # Background tasks kept here so they aren't GC'd (RUF006).
    _background_tasks: set[asyncio.Task[None]] = field(default_factory=set)
    # Per-agent in-flight mission task (so a patrol can be cancelled to divert).
    _agent_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    # Agents currently executing any orchestrator mission (patrol or verify).
    _busy: set[str] = field(default_factory=set)
    # Agents currently executing a VERIFY — never diverted out from under one.
    _verifying: set[str] = field(default_factory=set)
    # Monotonic patrol cycle counter — rotates each unit's sweep so the
    # pattern shifts cycle to cycle instead of retracing one fixed loop.
    _patrol_cycle: int = 0

    async def run(self) -> None:
        await asyncio.gather(self._anomaly_loop(), self._patrol_loop())

    # ── reactive loops ───────────────────────────────────────────────────────

    async def _anomaly_loop(self) -> None:
        """Subscribe to /anomalies, open a VERIFY auction for each one."""

        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                anomaly = Anomaly.model_validate_json(payload)
            except Exception as e:
                logger.warning("invalid anomaly payload: %s", e)
                continue
            logger.info("anomaly received: %s @ (%.5f, %.5f)", anomaly.kind.value, anomaly.geo.lat, anomaly.geo.lon)
            mission = VERIFY(
                geo=anomaly.geo,
                hover_s=self.verify_hover_s,
                priority=80 + int(anomaly.confidence * 20),
            )
            await self._auction_and_dispatch(mission)

    async def _patrol_loop(self) -> None:
        """Keep idle docked units sweeping when continuous patrol is enabled.

        A no-op (kept alive so `gather` doesn't return early) when patrol is
        off — this preserves the prior `_fleet_loop` placeholder behaviour.
        """

        if not self.continuous_patrol:
            while True:
                await asyncio.sleep(60.0)

        # Let the first fleet snapshot settle before the opening sortie.
        await asyncio.sleep(1.0)
        while True:
            try:
                self._dispatch_idle_patrols()
            except Exception:  # never let a transient error kill the loop
                logger.exception("patrol dispatch failed")
            self._patrol_cycle += 1
            await asyncio.sleep(self.patrol_period_s)

    # ── patrol ─────────────────────────────────────────────────────────────--

    def _dispatch_idle_patrols(self) -> None:
        fleet = sorted(self._snapshot_fleet(), key=lambda f: f.agent_id)
        n = len(fleet) or 1
        for idx, fs in enumerate(fleet):
            if fs.agent_id in self._busy:
                continue
            if fs.fsm_state is not AgentState.DOCKED:
                continue
            if fs.battery_pct < self.min_patrol_battery_pct:
                continue
            mission = PATROL(
                area=self._patrol_area(idx, n),
                altitude_m=self.patrol_altitude_m,
                priority=1,
            )
            self._start_mission(fs.agent_id, mission, is_verify=False)
            logger.info("patrol dispatched to %s (wedge %d/%d)", fs.agent_id, idx + 1, n)

    def _patrol_origin(self) -> Geo:
        if self.patrol_origin is not None:
            return self.patrol_origin
        if self.world_drones:
            return self.world_drones[0].dock
        return Geo(lat=0.0, lon=0.0, alt_m=0.0)

    def _patrol_area(self, idx: int, n: int) -> list[Geo]:
        """Closed loop over unit `idx`'s wedge of the territory.

        The fleet's coverage is split into `n` angular wedges. Each unit sweeps
        an outer arc then an inner arc of its wedge, forming a closed loop the
        adapter flies before returning to dock. A per-cycle phase rotates the
        whole pattern so successive sweeps don't retrace one fixed path.
        """

        origin = self._patrol_origin()
        span = 2.0 * math.pi / n
        margin = span * 0.10
        phase = (self._patrol_cycle % 6) * (math.pi / 90.0)  # ±a few degrees
        a0 = idx * span + margin + phase
        a1 = (idx + 1) * span - margin + phase
        r_out = self.patrol_radius_m
        r_in = self.patrol_radius_m * 0.42
        steps = 3
        loop: list[Geo] = []
        for k in range(steps + 1):  # outer arc a0 → a1
            a = a0 + (a1 - a0) * k / steps
            loop.append(self._offset(origin, r_out * math.sin(a), r_out * math.cos(a)))
        for k in range(steps + 1):  # inner arc a1 → a0
            a = a1 - (a1 - a0) * k / steps
            loop.append(self._offset(origin, r_in * math.sin(a), r_in * math.cos(a)))
        return loop

    def _offset(self, origin: Geo, east_m: float, north_m: float) -> Geo:
        dlat = north_m / _M_PER_DEG
        dlon = east_m / (_M_PER_DEG * math.cos(math.radians(origin.lat)))
        return Geo(
            lat=origin.lat + dlat,
            lon=origin.lon + dlon,
            alt_m=self.patrol_altitude_m,
        )

    # ── auction ──────────────────────────────────────────────────────────────

    async def _auction_and_dispatch(self, mission: MissionTask) -> None:
        fleet = self._snapshot_fleet()
        candidates = eligible(fleet, min_battery_pct=MIN_BATTERY_PCT)
        if candidates:
            bids = [build_bid(mission, fs) for fs in candidates]
            winner = select_winner(bids)
            if winner is None:
                return
            await self._award_and_run(mission, winner.agent_id, winner.score)
            return

        # No docked unit free. Under continuous patrol, divert the nearest
        # airborne unit that isn't already verifying — it peels off its sweep
        # to confirm, then the patrol loop re-launches it once it re-docks.
        if self.continuous_patrol:
            victim = self._nearest_airborne(fleet, mission)
            if victim is not None:
                await self._divert_to_verify(victim, mission)
                return

        logger.warning("no eligible bidders for mission %s", mission.id)

    def _nearest_airborne(
        self, fleet: list[FleetState], mission: MissionTask
    ) -> str | None:
        from swarm_core.allocator import _mission_geo

        mgeo = _mission_geo(mission)
        airborne = [
            f
            for f in fleet
            if f.fsm_state is not AgentState.DOCKED
            and f.battery_pct >= MIN_BATTERY_PCT
            and f.agent_id not in self._verifying
        ]
        if not airborne:
            return None
        if mgeo is None:
            return sorted(airborne, key=lambda f: f.agent_id)[0].agent_id
        nearest = min(airborne, key=lambda f: haversine_m(f.geo, mgeo))
        return nearest.agent_id

    async def _divert_to_verify(self, agent_id: str, mission: MissionTask) -> None:
        task = self._agent_tasks.pop(agent_id, None)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._busy.discard(agent_id)
        logger.info("diverting %s to VERIFY %s", agent_id, mission.id)
        await self._award_and_run(mission, agent_id, score=0.0)

    async def _award_and_run(
        self, mission: MissionTask, agent_id: str, score: float
    ) -> None:
        award = Award(mission_id=mission.id, winner_agent_id=agent_id, score=score)
        await self.bus.publish("swarm:missions:award", award.model_dump_json())
        logger.info("mission %s awarded to %s (score=%.3f)", mission.id, agent_id, score)
        self._start_mission(agent_id, mission, is_verify=True)

    # ── mission execution ─────────────────────────────────────────────────────

    def _start_mission(
        self, agent_id: str, mission: MissionTask, *, is_verify: bool
    ) -> asyncio.Task[None]:
        self._busy.add(agent_id)
        if is_verify:
            self._verifying.add(agent_id)
        mission.assigned_agent = agent_id
        adapter = self.registry.get(agent_id)
        task = asyncio.create_task(
            self._run_mission(agent_id, adapter, mission, is_verify=is_verify)
        )
        self._agent_tasks[agent_id] = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _run_mission(
        self, agent_id: str, adapter: object, mission: MissionTask, *, is_verify: bool
    ) -> None:
        """Drive the adapter. VERIFY missions stream `MissionProgress`; PATROL
        missions move the drone but stay off the bus (see module docstring)."""

        try:
            async for progress in adapter.execute_mission(mission):  # type: ignore[attr-defined]
                if not is_verify:
                    continue
                await self.bus.publish(
                    f"swarm:missions:progress:{mission.id}",
                    progress.model_dump_json(),
                )
                if progress.phase in ("DONE", "FAILED"):
                    return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("mission %s failed: %s", mission.id, e)
        finally:
            self._busy.discard(agent_id)
            self._verifying.discard(agent_id)
            if self._agent_tasks.get(agent_id) is asyncio.current_task():
                self._agent_tasks.pop(agent_id, None)

    # ── fleet snapshot ───────────────────────────────────────────────────────

    def _snapshot_fleet(self) -> list[FleetState]:
        """Best-available `FleetState` snapshot for auction scoring."""
        out: list[FleetState] = []
        if self.world_drones:
            for d in self.world_drones:
                adapter = self.registry.get(d.agent_id)
                state = AgentState.DOCKED if d.is_docked else AgentState.EN_ROUTE
                out.append(
                    FleetState(
                        agent_id=d.agent_id,
                        vendor=adapter.vendor,  # type: ignore[attr-defined]
                        model=adapter.model,  # type: ignore[attr-defined]
                        fsm_state=state,
                        battery_pct=d.battery_pct,
                        geo=Geo(lat=d.geo.lat, lon=d.geo.lon, alt_m=d.geo.alt_m),
                    )
                )
            return out

        # Fallback: scan registry — assumes adapters expose `geo`/`battery_pct` somehow,
        # which in production they would via `stream_telemetry()` aggregated elsewhere.
        # Commit 1 leaves this empty when no `world_drones` were passed.
        return out
