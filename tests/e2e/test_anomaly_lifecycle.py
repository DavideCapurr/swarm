"""Phase 6.J — canonical end-to-end test.

Exercises the anomaly lifecycle the roadmap mandates:

    PENDING → VERIFYING → VERIFIED → ESCALATION → RETURN → DOCKED

Every transition is driven through the public API or the real bus topic
the production runner uses. Internal mocks are forbidden (see the
``tests/test_phase6j_testing.py`` parity guard).
"""

from __future__ import annotations

import pytest
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    AnomalyState,
    Attitude,
    FleetState,
    Geo,
    OperatingMode,
    Telemetry,
)

from tests.e2e.conftest import E2EStack, drain_bus

pytestmark = pytest.mark.asyncio


async def _seed_units(stack: E2EStack) -> None:
    """Publish one telemetry frame per sim drone so the verifier is assignable."""

    for drone in stack.world.drones:
        telemetry = Telemetry(
            agent_id=drone.agent_id,
            geo=Geo(lat=drone.geo.lat, lon=drone.geo.lon, alt_m=20.0),
            attitude=Attitude(yaw_deg=0.0),
            battery_pct=95.0,
            link_quality=0.97,
        )
        await stack.bus.publish(  # type: ignore[attr-defined]
            f"swarm:telemetry:{drone.agent_id}",
            telemetry.model_dump_json(),
        )
    await drain_bus()


async def test_anomaly_lifecycle_no_internal_mocks(
    e2e_stack: E2EStack,
    operator_headers: dict[str, str],
) -> None:
    stack = e2e_stack

    await _seed_units(stack)
    r = await stack.client.get("/units", headers=operator_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["units"]) == len(stack.world.drones)

    anomaly = Anomaly(
        kind=AnomalyKind.SMOKE,
        geo=Geo(
            lat=stack.world.dock.lat + 0.0027,
            lon=stack.world.dock.lon + 0.0027,
        ),
        confidence=0.78,
    )
    await stack.bus.publish(  # type: ignore[attr-defined]
        "swarm:anomalies", anomaly.model_dump_json()
    )
    await drain_bus()

    r = await stack.client.get("/anomalies", headers=operator_headers)
    assert r.status_code == 200
    pending = r.json()["anomalies"]
    assert len(pending) == 1
    assert pending[0]["state"] == AnomalyState.PENDING.value

    r = await stack.client.post(
        "/actions/verify",
        json={"target": f"anomaly:{anomaly.id}"},
        headers=operator_headers,
    )
    assert r.status_code == 202, r.text

    r = await stack.client.get("/anomalies", headers=operator_headers)
    verifying = r.json()["anomalies"][0]
    assert verifying["state"] == AnomalyState.VERIFYING.value
    verifier_id = verifying["verifying_agent"]
    assert verifier_id is not None

    # In production the orchestrator publishes the confirmed anomaly back on
    # the same bus topic after the verify mission completes. The e2e test
    # uses the identical signal path with a real ``Anomaly`` payload — no
    # internal mock, no test-only side channel.
    confirmed = Anomaly(
        id=anomaly.id,
        kind=anomaly.kind,
        geo=anomaly.geo,
        confidence=anomaly.confidence,
        source_agent=verifier_id,
        verified=True,
    )
    await stack.bus.publish(  # type: ignore[attr-defined]
        "swarm:anomalies", confirmed.model_dump_json()
    )
    await drain_bus()

    r = await stack.client.get("/anomalies", headers=operator_headers)
    verified = r.json()["anomalies"][0]
    assert verified["state"] == AnomalyState.VERIFIED.value

    r = await stack.client.get("/awareness", headers=operator_headers)
    awareness = r.json()["awareness"]
    assert awareness["mode"] == OperatingMode.ESCALATION.value

    r = await stack.client.post(
        "/actions/return",
        json={"target": f"unit:{verifier_id}"},
        headers=operator_headers,
    )
    assert r.status_code == 202, r.text

    r = await stack.client.get("/missions", headers=operator_headers)
    missions = r.json()["missions"]
    rtl_missions = [m for m in missions if m["kind"] == "RTL_DOCK"]
    assert rtl_missions, "expected an RTL_DOCK mission after /actions/return"
    assert any(m["assigned_agent"] == verifier_id for m in rtl_missions)

    docked = FleetState(
        agent_id=verifier_id,
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=72.0,
        geo=Geo(lat=stack.world.dock.lat, lon=stack.world.dock.lon, alt_m=0.0),
    )
    await stack.bus.publish(  # type: ignore[attr-defined]
        "swarm:fleet:state", docked.model_dump_json()
    )
    await drain_bus()

    r = await stack.client.get("/units", headers=operator_headers)
    units = {u["agent_id"]: u for u in r.json()["units"]}
    assert units[verifier_id]["fsm_state"] == AgentState.DOCKED.value


async def test_unauthorized_verify_is_rejected(
    e2e_stack: E2EStack,
    viewer_headers: dict[str, str],
) -> None:
    """Viewer role is below the operator floor: /actions/verify must 403."""

    stack = e2e_stack
    await _seed_units(stack)

    anomaly = Anomaly(
        kind=AnomalyKind.SMOKE,
        geo=Geo(
            lat=stack.world.dock.lat + 0.001,
            lon=stack.world.dock.lon + 0.001,
        ),
        confidence=0.7,
    )
    await stack.bus.publish(  # type: ignore[attr-defined]
        "swarm:anomalies", anomaly.model_dump_json()
    )
    await drain_bus()

    r = await stack.client.post(
        "/actions/verify",
        json={"target": f"anomaly:{anomaly.id}"},
        headers=viewer_headers,
    )
    assert r.status_code == 403
