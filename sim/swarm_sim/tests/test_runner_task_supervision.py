"""Sim runner — background-task failure supervision.

Regression coverage for a real incident: a fire-and-forget task spawned in
`main()` (e.g. `_publish_anomalies`, which drives `CVPerception.run()`)
could raise and die with zero signal. Nothing ever awaited its result, and
the final `asyncio.gather(..., return_exceptions=True)` at shutdown
discarded whatever it collected — so the sim kept running, the Console kept
showing an honest "no objective held", and neither an operator nor a
developer had any way to learn why. `_spawn` + `_log_task_failure`
(sim/swarm_sim/runner.py) close that gap by logging any unhandled task
exception the moment the task dies.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

import pytest

from orchestrator.swarm_orchestrator.bus import InMemoryBus
from sim.swarm_sim.cv.detector import CVRuntimeUnavailable
from sim.swarm_sim.cv.perception_cv import CVPerception
from sim.swarm_sim.runner import _publish_anomalies, _spawn
from sim.swarm_sim.scenario import load_scenario

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"


async def test_spawn_logs_a_task_that_raises(caplog: pytest.LogCaptureFixture) -> None:
    async def _boom() -> None:
        raise ValueError("kaboom")

    with caplog.at_level(logging.ERROR, logger="sim.runner"):
        task = _spawn(_boom(), name="boom-task")
        with contextlib.suppress(ValueError):
            await task
        await asyncio.sleep(0)

    assert "boom-task" in caplog.text
    assert "kaboom" in caplog.text  # the traceback, via exc_info=exc


async def test_spawn_does_not_log_a_clean_cancellation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _forever() -> None:
        await asyncio.sleep(3600)

    with caplog.at_level(logging.ERROR, logger="sim.runner"):
        task = _spawn(_forever(), name="forever-task")
        await asyncio.sleep(0)  # let it actually start before cancelling
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)

    assert caplog.text == ""


async def test_publish_anomalies_task_failure_is_logged_not_silent(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """End-to-end reproduction of the original incident, now fixed.

    `intrusion_owner_land.yaml` is built exactly as `runner.main()` builds
    it, then driven through `_publish_anomalies` exactly as `runner.main()`
    spawns it (`_spawn`, fire-and-forget). The runtime-import seam is
    forced to fail the way it does when `ultralytics`/`torch` aren't
    installed. The task must end up failed AND logged — not silently stuck
    forever, which is what actually happened before this fix.
    """

    def _raise() -> None:
        raise CVRuntimeUnavailable(
            "ultralytics/torch not installed — run `make setup-cv`"
        )

    monkeypatch.setattr("sim.swarm_sim.cv.detector._load_runtime", _raise)

    scenario = load_scenario(SCENARIO_DIR / "intrusion_owner_land.yaml")
    world = scenario.build_world()
    assert isinstance(world.perception, CVPerception)

    bus = InMemoryBus()
    await bus.connect()
    try:
        with caplog.at_level(logging.ERROR, logger="sim.runner"):
            task = _spawn(_publish_anomalies(world, bus), name="publish_anomalies")
            with contextlib.suppress(CVRuntimeUnavailable):
                await asyncio.wait_for(task, timeout=1.0)
            await asyncio.sleep(0)
    finally:
        await bus.close()

    assert task.done() and not task.cancelled()
    assert isinstance(task.exception(), CVRuntimeUnavailable)
    assert "publish_anomalies" in caplog.text
    assert "make setup-cv" in caplog.text
