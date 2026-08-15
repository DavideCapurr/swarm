"""Vendor runner registry — picks which adapters the backend boots.

Phase 5 introduces side-by-side simulator + MAVLink fleets. The `SWARM_VENDORS`
env var is a comma-separated allowlist; for each token, this module spawns the
corresponding runner so its telemetry / fleet-state / stream-descriptor frames
flow onto the same bus the backend consumes.

Defaults:
  - `SWARM_VENDORS` unset            → `simulator`
  - `SWARM_VENDORS=simulator`        → simulator only
  - `SWARM_VENDORS=simulator,mavlink`→ both
  - `SWARM_VENDORS=mavlink`          → MAVLink only

Unknown vendors are surfaced via `UnknownVendor` so a typo doesn't silently
boot a no-op fleet. Requested vendor boot failures are surfaced via
`VendorBootError`; Phase 5 is fail-fast for both `mavlink` and
`simulator,mavlink` because silently dropping a requested real adapter would
make the backend report a fake-complete fleet.

Why in-process for MAVLink and out-of-process for simulator? The simulator
needs a `World` tick at a steady rate; the MAVLink runner is just a thin
adapter wrapping `pymavlink` — co-locating it with the backend avoids a
second Redis hop for the demo bench and keeps the `make demo` graph
simpler.

Mission ownership is intentionally narrower than telemetry ownership. A
MAVLink-only backend also owns one `BusFleetOrchestrator`, so anomalies can be
auctioned against the registered real adapters and dispatched through their
existing `execute_mission()` contract. Mixed `simulator,mavlink` mode does not
start a second backend orchestrator because the simulator process already owns
one; unified mixed-fleet routing remains a later explicit design step.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from adapters.base import AdapterRegistry
from adapters.mavlink.runner import MAVLinkRunner
from adapters.mavlink.runner import boot_runner as boot_mavlink_runner
from orchestrator.swarm_orchestrator.bus import Bus
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator

logger = logging.getLogger("backend.fleet")

#: Vendors recognized by `parse_vendors`. The simulator is always implicitly
#: supported even when running standalone — it ships with the repo.
SUPPORTED_VENDORS: frozenset[str] = frozenset({"simulator", "mavlink"})

#: Vendors this module is responsible for booting **in-process** alongside
#: the backend. The simulator is **not** in this set because its runner is
#: a separate process; including it here would double-spawn it.
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


# ── Fleet manager ─────────────────────────────────────────────────────────────


VendorBooter = Callable[[Bus, AdapterRegistry], Awaitable[object]]


@dataclass
class FleetManager:
    """Owns in-process vendor runners and their mission-dispatch runtime."""

    bus: Bus
    registry: AdapterRegistry = field(default_factory=AdapterRegistry)
    vendors: tuple[str, ...] = ()
    mission_ready_timeout_s: float = 8.0
    _runners: list[object] = field(default_factory=list)
    _mission_orchestrator: BusFleetOrchestrator | None = None
    _mission_task: asyncio.Task[None] | None = None
    # Test-only seam: swap a vendor's boot function. Production code lets
    # the defaults below take over via `_default_booters`.
    booters: dict[str, VendorBooter] = field(default_factory=dict)

    async def start(self) -> None:
        booters = {**_default_booters(), **self.booters}
        for vendor in self.vendors:
            if vendor not in IN_PROCESS_VENDORS:
                logger.info("fleet: vendor %r is out-of-process — skipping in-process boot", vendor)
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
            await self._start_mission_runtime()
        except Exception as exc:
            logger.exception("fleet: mission runtime boot failed")
            await self.stop()
            raise VendorBootError("MAVLink mission runtime boot failed") from exc

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

        orchestrator = BusFleetOrchestrator(
            bus=self.bus,
            registry=self.registry,
            continuous_patrol=False,
        )
        task = asyncio.create_task(orchestrator.run())
        self._mission_orchestrator = orchestrator
        self._mission_task = task
        await orchestrator.wait_for_registered_fleet(
            timeout_s=self.mission_ready_timeout_s
        )
        logger.info(
            "fleet: mission orchestrator ready for %d MAVLink adapter(s)",
            len(self.registry),
        )

    async def stop(self) -> None:
        if self._mission_task is not None:
            self._mission_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._mission_task
            self._mission_task = None
            self._mission_orchestrator = None

        for runner in self._runners:
            stop = getattr(runner, "stop", None)
            if stop is not None:
                try:
                    await stop()
                except Exception:  # pragma: no cover — defensive
                    logger.exception("fleet: runner stop failed")
        self._runners.clear()


def _default_booters() -> dict[str, VendorBooter]:
    async def _mavlink(bus: Bus, registry: AdapterRegistry) -> MAVLinkRunner:
        return await boot_mavlink_runner(bus, registry)

    return {"mavlink": _mavlink}


def fleet_from_env(bus: Bus, *, registry: AdapterRegistry | None = None) -> FleetManager:
    """Build a FleetManager from the `SWARM_VENDORS` env var."""
    vendors = parse_vendors(os.getenv("SWARM_VENDORS"))
    return FleetManager(
        bus=bus,
        registry=registry or AdapterRegistry(),
        vendors=vendors,
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