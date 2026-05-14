"""Orchestrator service — auction loop, mission dispatch, fleet aggregation.

The orchestrator listens for `Anomaly` events, opens auctions, awards missions
to the best-scored adapter, dispatches `execute_mission`, and re-publishes
`MissionProgress`. It uses `AdapterRegistry` to look up adapters by
`agent_id` — never importing any vendor-specific class.

For commit 1 the orchestrator is intentionally simple:
  - Auction window is short (500 ms) and synchronous (collects all bids it can
    in the window, then picks).
  - It does NOT decompose `COVER` into per-agent `PATROL` slices yet — that's
    a follow-up.
  - It does NOT re-issue auctions for higher-priority anomalies mid-flight yet
    (`divert()` exists in the adapter, but the orchestrator does not invoke it
    in commit 1).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from swarm_core.allocator import build_bid, eligible, select_winner
from swarm_core.messages import (
    AgentState,
    Anomaly,
    Award,
    FleetState,
    Geo,
    MissionTask,
)
from swarm_core.missions import VERIFY

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import Bus

if TYPE_CHECKING:  # pragma: no cover
    from sim.swarm_sim.drone import Drone

logger = logging.getLogger("swarm.orchestrator")

AUCTION_WINDOW_S = 0.5
MIN_BATTERY_PCT = 25.0


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
    # Background tasks kept here so they aren't GC'd (RUF006).
    _background_tasks: set[asyncio.Task[None]] = field(default_factory=set)

    async def run(self) -> None:
        await asyncio.gather(self._anomaly_loop(), self._fleet_loop())

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

    async def _fleet_loop(self) -> None:
        """No-op for commit 1. Reserved for COVER decomposition, scheduled patrols,
        and re-balancing logic."""

        # Keeping this task alive ensures `gather` doesn't return early when run()
        # is awaited.
        while True:
            await asyncio.sleep(60.0)

    # ── auction ──────────────────────────────────────────────────────────────

    async def _auction_and_dispatch(self, mission: MissionTask) -> None:
        fleet = self._snapshot_fleet()
        candidates = eligible(fleet, min_battery_pct=MIN_BATTERY_PCT)
        if not candidates:
            logger.warning("no eligible bidders for mission %s", mission.id)
            return

        bids = [build_bid(mission, fs) for fs in candidates]
        winner = select_winner(bids)
        if winner is None:
            return

        award = Award(mission_id=mission.id, winner_agent_id=winner.agent_id, score=winner.score)
        await self.bus.publish("swarm:missions:award", award.model_dump_json())
        logger.info(
            "mission %s awarded to %s (score=%.3f)", mission.id, winner.agent_id, winner.score
        )

        adapter = self.registry.get(winner.agent_id)
        mission.assigned_agent = winner.agent_id
        # Keep a strong reference so the task isn't GC'd mid-flight (RUF006).
        task = asyncio.create_task(self._execute_mission_task(adapter, mission))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _execute_mission_task(self, adapter: object, mission: MissionTask) -> None:
        """Drives the adapter and streams `MissionProgress` to the bus."""
        try:
            async for progress in adapter.execute_mission(mission):  # type: ignore[attr-defined]
                await self.bus.publish(
                    f"swarm:missions:progress:{mission.id}",
                    progress.model_dump_json(),
                )
                if progress.phase in ("DONE", "FAILED"):
                    return
        except Exception as e:
            logger.exception("mission %s failed: %s", mission.id, e)

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
