"""CI coverage for the Phase 9 SITL probe logic (`scripts/phase5_sitl_probe.py`).

The probe's *evidence* (`docs/bench/artifacts/phase9-sitl-probe.json`) is produced
against a live PX4 SITL endpoint and cannot run in CI (it needs Docker + Gazebo).
But every logic path the probe drives must still be exercised here against the
in-process `FakeMAVLinkEndpoint`, so the probe code itself can't silently rot:

  * the full ``--exercise-verify`` gate set rolls up to ``status: "pass"`` with
    a ``heartbeat → health → telemetry → verify_mission → safety_return`` step
    sequence, each tagged with its Phase 9 gate; and
  * a missing autopilot HEARTBEAT rolls up to a *visible* ``status: "fail"``
    (the same failure the prior real probe recorded), never a false green.
"""

from __future__ import annotations

import argparse

import pytest

from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from scripts.phase5_sitl_probe import run_probe

EXPECTED_STEPS = ["heartbeat", "health", "telemetry", "verify_mission", "safety_return"]
EXPECTED_GATES = {
    "connect",
    "status_visibility",
    "telemetry_ingest",
    "mission_dispatch",
    "safety_return_abort",
}


def _args(endpoint: FakeMAVLinkEndpoint, **overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "connection": f"udpout:127.0.0.1:{endpoint.port}",
        "agent_id": "mav-probe-test",
        "model": "px4-x500",
        "stream_url": None,
        "connect_timeout_s": 5.0,
        "response_timeout_s": 2.0,
        "telemetry_timeout_s": 5.0,
        "mission_timeout_s": 20.0,
        "exercise_verify": True,
        "verify_lat": 44.7,
        "verify_lon": 8.03,
        "json_out": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.mark.asyncio
async def test_probe_passes_full_gate_set_against_fake() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    try:
        code, report = await run_probe(_args(endpoint))
    finally:
        await endpoint.stop()

    assert code == 0
    assert report["status"] == "pass"

    steps = report["steps"]
    assert [s["name"] for s in steps] == EXPECTED_STEPS
    assert all(s["status"] == "pass" for s in steps)
    assert {s["gate"] for s in steps} == EXPECTED_GATES

    # mission_dispatch proof: VERIFY actually progressed to a terminal DONE.
    verify = next(s for s in steps if s["name"] == "verify_mission")
    assert verify["detail"]["phases"][-1] == "DONE"
    assert verify["detail"]["phases"][0] == "EN_ROUTE"

    # safety_return proof: RTL_DOCK reached the autopilot and was accepted.
    safety = next(s for s in steps if s["name"] == "safety_return")
    assert safety["detail"]["phases"] == ["DONE"]
    assert endpoint.state.rtl_triggered is True


@pytest.mark.asyncio
async def test_probe_fails_visibly_without_heartbeat() -> None:
    # No HEARTBEAT — the exact gap the 2026-05-16 probe hit. The roll-up must
    # surface it as a fail, not coast to a misleading pass.
    endpoint = FakeMAVLinkEndpoint(emit_heartbeat=False)
    await endpoint.start()
    try:
        code, report = await run_probe(
            _args(
                endpoint,
                connect_timeout_s=0.3,
                response_timeout_s=0.3,
                telemetry_timeout_s=1.0,
                mission_timeout_s=2.0,
            )
        )
    finally:
        await endpoint.stop()

    assert code == 2
    assert report["status"] == "fail"
    assert report["steps"][-1]["name"] == "probe_error"
    assert report["steps"][-1]["status"] == "fail"
