"""Multi-unit composition for the existing single-aircraft MAVLink runner.

`MAVLinkRunner` remains the unit-level primitive. This module only composes
multiple independent adapters/runners so the backend can expose one registry
containing several PX4/SITL vehicles to the vendor-neutral orchestrator.

Configuration:

    MAVLINK_FLEET="mav-001=udp:localhost:14540,mav-002=udp:localhost:14541"

When `MAVLINK_FLEET` is unset, the legacy `MAVLINK_AGENT_ID` /
`MAVLINK_CONNECTION` path is preserved exactly through `adapter_from_env()`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.runner import MAVLinkRunner, adapter_from_env
from orchestrator.swarm_orchestrator.bus import Bus

logger = logging.getLogger("mavlink.fleet_runner")


class MAVLinkFleetConfigError(ValueError):
    """Raised when `MAVLINK_FLEET` is malformed or ambiguous."""


@dataclass(frozen=True)
class MAVLinkUnitConfig:
    agent_id: str
    connection: str


def parse_mavlink_fleet(raw: str) -> tuple[MAVLinkUnitConfig, ...]:
    """Parse `agent_id=connection` entries from `MAVLINK_FLEET`."""

    units: list[MAVLinkUnitConfig] = []
    seen_ids: set[str] = set()
    for token in raw.split(","):
        item = token.strip()
        if not item:
            continue
        agent_id, sep, connection = item.partition("=")
        agent_id = agent_id.strip()
        connection = connection.strip()
        if not sep or not agent_id or not connection:
            raise MAVLinkFleetConfigError(
                "MAVLINK_FLEET entries must use agent_id=connection"
            )
        if agent_id in seen_ids:
            raise MAVLinkFleetConfigError(
                f"duplicate MAVLink agent_id in MAVLINK_FLEET: {agent_id}"
            )
        seen_ids.add(agent_id)
        units.append(MAVLinkUnitConfig(agent_id=agent_id, connection=connection))

    if not units:
        raise MAVLinkFleetConfigError("MAVLINK_FLEET contains no units")
    return tuple(units)


def adapters_from_env() -> list[MAVLinkAdapter]:
    """Build one or many MAVLink adapters while preserving legacy env config."""

    raw = (os.getenv("MAVLINK_FLEET") or "").strip()
    if not raw:
        return [adapter_from_env()]

    model = os.getenv("MAVLINK_MODEL", "px4-x500")
    rate_limit_hz = float(os.getenv("MAVLINK_RATE_LIMIT_HZ", "50"))
    adapters: list[MAVLinkAdapter] = []
    for unit in parse_mavlink_fleet(raw):
        adapters.append(
            MAVLinkAdapter(
                agent_id=unit.agent_id,
                connection=unit.connection,
                model=model,
                rate_limit_hz=rate_limit_hz,
            )
        )
    return adapters


@dataclass
class MAVLinkFleetRunner:
    """Own several already-configured `MAVLinkRunner` instances as one unit."""

    runners: list[MAVLinkRunner]
    _started: list[MAVLinkRunner] = field(default_factory=list)

    async def start(self) -> None:
        try:
            for runner in self.runners:
                await runner.start()
                self._started.append(runner)
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        while self._started:
            runner = self._started.pop()
            await runner.stop()


async def boot_fleet_runner(
    bus: Bus,
    registry: AdapterRegistry | None = None,
    *,
    adapters: list[MAVLinkAdapter] | None = None,
) -> MAVLinkFleetRunner:
    """Start all configured adapters, then atomically expose them in registry."""

    resolved = adapters if adapters is not None else adapters_from_env()
    fleet = MAVLinkFleetRunner(
        runners=[MAVLinkRunner(adapter=adapter, bus=bus) for adapter in resolved]
    )
    await fleet.start()

    registered: list[str] = []
    try:
        if registry is not None:
            for adapter in resolved:
                registry.register(adapter)
                registered.append(adapter.agent_id)
    except Exception:
        if registry is not None:
            for agent_id in registered:
                registry.unregister(agent_id)
        await fleet.stop()
        raise

    logger.info("mavlink fleet online: %s", ", ".join(a.agent_id for a in resolved))
    return fleet


__all__ = (
    "MAVLinkFleetConfigError",
    "MAVLinkFleetRunner",
    "MAVLinkUnitConfig",
    "adapters_from_env",
    "boot_fleet_runner",
    "parse_mavlink_fleet",
)
