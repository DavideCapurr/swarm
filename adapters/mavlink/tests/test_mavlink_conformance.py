"""Run the cross-vendor conformance suite against the MAVLink adapter.

Uses `FakeMAVLinkEndpoint` instead of a real PX4 SITL container. The fake
covers the wire-protocol the adapter speaks; SITL is the hardware-bench
acceptance gate (see `docs/adapters/mavlink-setup.md`).

The conformance suite's `adapter_factory` is synchronous, but our adapter
needs a paired UDP endpoint task. We bind the socket synchronously, then
schedule `endpoint.start()` on the currently-running asyncio loop (every
conformance test method is `@pytest.mark.asyncio`).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.tests.conformance import AdapterConformanceTests


class _EndpointBag:
    """Per-test bag so the autouse fixture can `await endpoint.stop()`."""

    def __init__(self) -> None:
        self.endpoints: list[FakeMAVLinkEndpoint] = []
        self.tasks: list[asyncio.Task[None]] = []


@pytest.fixture
def endpoint_bag() -> _EndpointBag:
    return _EndpointBag()


@pytest.fixture(autouse=True)
async def _shutdown_endpoints(endpoint_bag: _EndpointBag) -> AsyncIterator[None]:
    yield
    while endpoint_bag.endpoints:
        ep = endpoint_bag.endpoints.pop()
        await ep.stop()


class TestMAVLinkAdapterConformance(AdapterConformanceTests):
    """Inherit the cross-vendor scenarios."""

    is_stub = False

    def adapter_factory(self) -> MAVLinkAdapter:  # type: ignore[override]
        # Each scenario calls this once. We capture the endpoint on `self`
        # so the autouse fixture cleans it up — even if the test raises.
        endpoint = FakeMAVLinkEndpoint()
        self._endpoint_bag.endpoints.append(endpoint)  # type: ignore[attr-defined]
        # Bind already happened in __init__; just schedule the IO loop. The
        # task reference is parked on the bag for the autouse fixture to
        # await during cleanup via `endpoint.stop()`.
        start_task = asyncio.create_task(endpoint.start())
        self._endpoint_bag.tasks.append(start_task)  # type: ignore[attr-defined]
        return MAVLinkAdapter(
            agent_id="mav-1",
            connection=f"udpout:127.0.0.1:{endpoint.port}",
            heartbeat_timeout_s=10.0,
        )

    @pytest.fixture(autouse=True)
    def _bind_bag(self, endpoint_bag: _EndpointBag) -> None:
        # Wire the bag onto `self` so `adapter_factory` can append to it.
        self._endpoint_bag = endpoint_bag  # type: ignore[attr-defined]
