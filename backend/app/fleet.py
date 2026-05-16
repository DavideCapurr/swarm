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
boot a no-op fleet. The simulator runner is **not** owned by this module —
it lives in `sim.swarm_sim.runner` and is launched as a subprocess by
`scripts/dev_up.sh`. This module only manages the in-process MAVLink
runner that needs to share the FastAPI event loop with the bus consumer.

Why in-process for MAVLink and out-of-process for simulator? The simulator
needs a `World` tick at a steady rate; the MAVLink runner is just a thin
adapter wrapping `pymavlink` — co-locating it with the backend avoids a
second Redis hop for the demo bench and keeps the `make demo` graph
simpler.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from adapters.base import AdapterRegistry
from adapters.mavlink.runner import MAVLinkRunner
from adapters.mavlink.runner import boot_runner as boot_mavlink_runner
from orchestrator.swarm_orchestrator.bus import Bus

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
                f"unknown vendor {vendor!r} in SWARM_VENDORS — "
                f"allowed: {sorted(SUPPORTED_VENDORS)}"
            )
        if vendor not in seen:
            seen.append(vendor)
    return tuple(seen)


# ── Fleet manager ─────────────────────────────────────────────────────────────


VendorBooter = Callable[[Bus, AdapterRegistry], Awaitable[object]]


@dataclass
class FleetManager:
    """Owns the lifecycle of every in-process vendor runner."""

    bus: Bus
    registry: AdapterRegistry = field(default_factory=AdapterRegistry)
    vendors: tuple[str, ...] = ()
    _runners: list[object] = field(default_factory=list)
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
            except Exception:
                logger.exception("fleet: %r runner boot failed", vendor)
                continue
            self._runners.append(runner)
            logger.info("fleet: %r runner online", vendor)

    async def stop(self) -> None:
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
    "fleet_from_env",
    "parse_vendors",
)
