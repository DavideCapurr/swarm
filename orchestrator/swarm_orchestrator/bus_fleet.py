"""Bus-backed fleet state for orchestrators that do not own a simulator world.

The simulator can inspect ``world_drones`` directly. Real adapters cannot, so
this runtime consumes the same canonical ``FleetState`` frames already emitted
by vendor runners and uses them for central allocation and execution-group
composition.

Only states for adapters present in this orchestrator's ``AdapterRegistry`` are
eligible. That keeps mixed bus traffic from another fleet/process from being
awarded to an adapter this runtime does not own.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from swarm_core.messages import FleetState

from orchestrator.swarm_orchestrator.adaptive_execution_groups import (
    AdaptiveExecutionGroupOrchestrator,
)

logger = logging.getLogger("swarm.orchestrator.bus_fleet")


@dataclass
class BusFleetOrchestrator(AdaptiveExecutionGroupOrchestrator):
    """Orchestrator whose fleet snapshot is projected from bus state.

    The bus-backed runtime now uses the same idle/preemptible capacity planner as
    the adaptive simulator path. This is product orchestration logic; the fleet
    adapter remains an execution boundary and does not choose preemption.
    """

    fleet_state_stale_s: float = 5.0
    _fleet_state_by_id: dict[str, FleetState] = field(default_factory=dict)

    async def run(self) -> None:
        await asyncio.gather(super().run(), self._fleet_state_loop())

    async def _fleet_state_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:fleet:state"):
            try:
                state = FleetState.model_validate_json(payload)
            except Exception as exc:
                logger.warning("invalid fleet-state payload: %s", exc)
                continue
            self._fleet_state_by_id[state.agent_id] = state

    def _snapshot_fleet(self) -> list[FleetState]:
        if self.world_drones:
            return super()._snapshot_fleet()

        owned_ids = {adapter.agent_id for adapter in self.registry.all()}
        if not owned_ids:
            return []

        now = datetime.now(UTC)
        fresh: list[FleetState] = []
        for agent_id in sorted(owned_ids):
            state = self._fleet_state_by_id.get(agent_id)
            if state is None:
                continue
            age_s = max(0.0, (now - state.ts).total_seconds())
            if age_s > self.fleet_state_stale_s:
                continue
            fresh.append(state)
        return fresh

    async def wait_for_registered_fleet(self, *, timeout_s: float = 5.0) -> None:
        """Wait until every currently registered adapter has a fresh state.

        Backend startup uses this as a fail-closed readiness gate before it
        advertises a MAVLink-only fleet as mission-dispatch capable.
        """

        target_ids = {adapter.agent_id for adapter in self.registry.all()}
        if not target_ids:
            return

        async def _wait() -> None:
            while True:
                fresh_ids = {state.agent_id for state in self._snapshot_fleet()}
                if target_ids.issubset(fresh_ids):
                    return
                await asyncio.sleep(0.05)

        try:
            await asyncio.wait_for(_wait(), timeout=max(0.1, timeout_s))
        except TimeoutError as exc:
            fresh_ids = {state.agent_id for state in self._snapshot_fleet()}
            missing = sorted(target_ids - fresh_ids)
            raise TimeoutError(
                "timed out waiting for fresh FleetState from registered adapter(s): "
                + ", ".join(missing)
            ) from exc


__all__ = ("BusFleetOrchestrator",)
