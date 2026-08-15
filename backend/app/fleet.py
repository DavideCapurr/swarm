"""Vendor runner registry — picks which adapters the backend boots.

Mission-level decisions remain in SwarmOS. A MAVLink-only backend owns one
bus-backed orchestrator; simulator fleets may own their orchestrator in the
out-of-process sim runner. Execution-group truth is projected from the shared
bus in both cases, so REST/WebSocket surfaces render the same server-owned group
composition regardless of vendor runtime.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from swarm_core.execution_groups import ExecutionGroup

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fleet_runner import MAVLinkFleetRunner, boot_fleet_runner
from adapters.mavlink.payload import MAVLinkPayloadController
from adapters.payload import PayloadControllerRegistry
from backend.app.hub import HUB
from backend.app.state import STATE
from orchestrator.swarm_orchestrator.bus import Bus
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator
from orchestrator.swarm_orchestrator.execution_groups import EXECUTION_GROUP_TOPIC
from orchestrator.swarm_orchestrator.presence_bus import (
    PresenceResponseBusFleetOrchestrator,
)

logger = logging.getLogger("backend.fleet")

SUPPORTED_VENDORS: frozenset[str] = frozenset({"simulator", "mavlink"})
IN_PROCESS_VENDORS: frozenset[str] = frozenset({"mavlink"})


class UnknownVendor(ValueError):
    """Raised when `SWARM_VENDORS` contains an unrecognized token."""


class VendorBootError(RuntimeError):
    """Raised when a requested in-process vendor runner fails to start."""


def parse_vendors(raw: str | None) -> tuple[str, ...]:
    """Split, strip, lowercase, dedupe, and validate the `SWARM_VENDORS` env."""
    if not raw or not raw.strip():
        return ("simulator",)
    seen: list[str] = []
    for token in raw.split(","):
        vendor = token.strip().lower()
        if not vendor:
            continue
        if vendor not in SUPPORTED_VENDORS:
            raise UnknownVendor(
                f"unknown vendor {vendor!r} in SWARM_VENDORS — allowed: {sorted(SUPPORTED_VENDORS)}"
            )
        if vendor not in seen:
            seen.append(vendor)
    return tuple(seen)


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{name} must be one of 1/0, true/false, yes/no, on/off")


def _env_optional_int_range(
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _env_float(
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    raw = (os.getenv(name) or "").strip()
    value = float(raw) if raw else default
    if value < minimum or (maximum is not None and value > maximum):
        suffix = f" and <= {maximum}" if maximum is not None else ""
        raise ValueError(f"{name} must be >= {minimum}{suffix}")
    return value


VendorBooter = Callable[[Bus, AdapterRegistry], Awaitable[object]]


@dataclass
class FleetManager:
    """Owns in-process vendor runners and their mission-dispatch runtime."""

    bus: Bus
    registry: AdapterRegistry = field(default_factory=AdapterRegistry)
    vendors: tuple[str, ...] = ()
    mission_ready_timeout_s: float = 8.0

    cooperative_verify_enabled: bool = False
    cooperative_verify_min_confidence: float = 0.90
    cooperative_verify_team_size: int = 3

    presence_response_enabled: bool = False
    presence_min_confidence: float = 0.85
    presence_hold_s: float = 5.0
    light_actuator_number: int | None = None
    light_output_channel: int | None = None
    simulate_speaker: bool = False
    payload_registry: PayloadControllerRegistry = field(
        default_factory=PayloadControllerRegistry
    )

    _runners: list[object] = field(default_factory=list)
    _mission_orchestrator: BusFleetOrchestrator | None = None
    _mission_task: asyncio.Task[None] | None = None
    _execution_group_projection_task: asyncio.Task[None] | None = None
    booters: dict[str, VendorBooter] = field(default_factory=dict)

    async def start(self) -> None:
        if self._execution_group_projection_task is not None:
            raise RuntimeError("fleet manager already started")
        self._execution_group_projection_task = asyncio.create_task(
            self._project_execution_groups()
        )

        booters = {**_default_booters(), **self.booters}
        for vendor in self.vendors:
            if vendor not in IN_PROCESS_VENDORS:
                logger.info(
                    "fleet: vendor %r is out-of-process — skipping in-process boot",
                    vendor,
                )
                continue
            booter = booters.get(vendor)
            if booter is None:
                logger.warning("fleet: no in-process booter registered for %r", vendor)
                continue
            try:
                runner = await booter(self.bus, self.registry)
            except Exception as exc:
                logger.exception("fleet: %r runner boot failed", vendor)
                await self.stop()
                raise VendorBootError(f"{vendor!r} runner boot failed") from exc
            self._runners.append(runner)
            logger.info("fleet: %r runner online", vendor)

        try:
            self._configure_payload_runtime()
            await self._start_mission_runtime()
        except Exception as exc:
            logger.exception("fleet: mission runtime boot failed")
            await self.stop()
            raise VendorBootError("MAVLink mission runtime boot failed") from exc

    async def _project_execution_groups(self) -> None:
        """Project exact SwarmOS group truth; never infer membership in backend."""

        async for _topic, payload in self.bus.subscribe(EXECUTION_GROUP_TOPIC):
            try:
                group = ExecutionGroup.model_validate_json(payload)
            except Exception:
                logger.warning("dropped malformed execution-group frame")
                continue
            STATE.execution_groups[group.id] = group
            await HUB.broadcast(
                {"kind": "execution_group", "data": group.model_dump(mode="json")}
            )

    def _configure_payload_runtime(self) -> None:
        if not self.presence_response_enabled:
            return
        if self.vendors != ("mavlink",):
            raise ValueError(
                "SWARM_PRESENCE_RESPONSE currently requires SWARM_VENDORS=mavlink"
            )

        for adapter in self.registry.all():
            if not isinstance(adapter, MAVLinkAdapter):
                continue
            controller = MAVLinkPayloadController(
                adapter=adapter,
                light_actuator_number=self.light_actuator_number,
                light_output_channel=self.light_output_channel,
                simulate_speaker=self.simulate_speaker,
            )
            if controller.capabilities:
                self.payload_registry.register(controller)

        if len(self.payload_registry) == 0:
            raise ValueError(
                "presence response enabled but no payload capability configured; "
                "set MAVLINK_LIGHT_ACTUATOR_NUMBER + MAVLINK_LIGHT_OUTPUT_CHANNEL "
                "and/or SWARM_PRESENCE_SIMULATE_SPEAKER=1"
            )

    async def _start_mission_runtime(self) -> None:
        if self.vendors != ("mavlink",):
            if "mavlink" in self.vendors:
                logger.warning(
                    "fleet: backend orchestrator disabled for mixed vendors=%s; "
                    "simulator process owns its own orchestrator",
                    self.vendors,
                )
            return
        if self._mission_task is not None:
            raise RuntimeError("mission runtime already started")

        if self.presence_response_enabled:
            orchestrator: BusFleetOrchestrator = PresenceResponseBusFleetOrchestrator(
                bus=self.bus,
                registry=self.registry,
                continuous_patrol=False,
                payload_registry=self.payload_registry,
                presence_min_confidence=self.presence_min_confidence,
                presence_hold_s=self.presence_hold_s,
                cooperative_verify_enabled=self.cooperative_verify_enabled,
                cooperative_verify_min_confidence=self.cooperative_verify_min_confidence,
                cooperative_verify_team_size=self.cooperative_verify_team_size,
            )
        else:
            orchestrator = BusFleetOrchestrator(
                bus=self.bus,
                registry=self.registry,
                continuous_patrol=False,
                cooperative_verify_enabled=self.cooperative_verify_enabled,
                cooperative_verify_min_confidence=self.cooperative_verify_min_confidence,
                cooperative_verify_team_size=self.cooperative_verify_team_size,
            )

        task = asyncio.create_task(orchestrator.run())
        self._mission_orchestrator = orchestrator
        self._mission_task = task
        await orchestrator.wait_for_registered_fleet(
            timeout_s=self.mission_ready_timeout_s
        )
        logger.info(
            "fleet: mission orchestrator ready for %d MAVLink adapter(s)%s%s",
            len(self.registry),
            " with bounded presence response" if self.presence_response_enabled else "",
            (
                f" with cooperative verify team={self.cooperative_verify_team_size}"
                if self.cooperative_verify_enabled
                else ""
            ),
        )

    async def stop(self) -> None:
        if self._mission_task is not None:
            self._mission_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._mission_task
            self._mission_task = None
            self._mission_orchestrator = None

        if self._execution_group_projection_task is not None:
            self._execution_group_projection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._execution_group_projection_task
            self._execution_group_projection_task = None

        for runner in self._runners:
            stop = getattr(runner, "stop", None)
            if stop is not None:
                try:
                    await stop()
                except Exception:  # pragma: no cover — defensive
                    logger.exception("fleet: runner stop failed")
        self._runners.clear()
        self.payload_registry = PayloadControllerRegistry()


def _default_booters() -> dict[str, VendorBooter]:
    async def _mavlink(bus: Bus, registry: AdapterRegistry) -> MAVLinkFleetRunner:
        return await boot_fleet_runner(bus, registry)

    return {"mavlink": _mavlink}


def fleet_from_env(bus: Bus, *, registry: AdapterRegistry | None = None) -> FleetManager:
    """Build a FleetManager from environment configuration."""

    vendors = parse_vendors(os.getenv("SWARM_VENDORS"))
    cooperative_team_size = (
        _env_optional_int_range(
            "SWARM_COOPERATIVE_VERIFY_TEAM_SIZE",
            minimum=2,
            maximum=32,
        )
        or 3
    )
    return FleetManager(
        bus=bus,
        registry=registry or AdapterRegistry(),
        vendors=vendors,
        cooperative_verify_enabled=_env_flag("SWARM_COOPERATIVE_VERIFY"),
        cooperative_verify_min_confidence=_env_float(
            "SWARM_COOPERATIVE_VERIFY_MIN_CONFIDENCE",
            0.90,
            minimum=0.0,
            maximum=1.0,
        ),
        cooperative_verify_team_size=cooperative_team_size,
        presence_response_enabled=_env_flag("SWARM_PRESENCE_RESPONSE"),
        presence_min_confidence=_env_float(
            "SWARM_PRESENCE_MIN_CONFIDENCE",
            0.85,
            minimum=0.0,
            maximum=1.0,
        ),
        presence_hold_s=_env_float(
            "SWARM_PRESENCE_HOLD_S",
            5.0,
            minimum=0.0,
        ),
        light_actuator_number=_env_optional_int_range(
            "MAVLINK_LIGHT_ACTUATOR_NUMBER",
            minimum=1,
            maximum=6,
        ),
        light_output_channel=_env_optional_int_range(
            "MAVLINK_LIGHT_OUTPUT_CHANNEL",
            minimum=1,
            maximum=8,
        ),
        simulate_speaker=_env_flag("SWARM_PRESENCE_SIMULATE_SPEAKER"),
    )


__all__ = (
    "IN_PROCESS_VENDORS",
    "SUPPORTED_VENDORS",
    "FleetManager",
    "UnknownVendor",
    "VendorBootError",
    "fleet_from_env",
    "parse_vendors",
)
