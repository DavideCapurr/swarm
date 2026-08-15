# Phase 10 dynamic multi-event validation — changing-condition fleet coordination

Date: 2026-08-15
PR: #124 (`agent/dynamic-multi-event-demo`)
Base: PR #123 (`agent/mavlink-multi-agent-orchestrator`)
Validated feature commit: `b952ba6b9c6a8422ae62085d4c58a213c45ac6f7`
GitHub Actions run: `31878636052`
Artifact: `9245447732`
Artifact digest: `sha256:4013e44e824181dae018c6750656a8f8b165f8bea0315ad398aea2d181008ec4`
Permanent probe evidence: [`artifacts/phase10-dynamic-multi-event-probe.json`](artifacts/phase10-dynamic-multi-event-probe.json)

## Result

**PASS — while the first PX4 VERIFY mission was still actively EN_ROUTE, a second event changed SWARM's fleet plan and was allocated to the other available PX4. Both aircraft then independently reached their targets and completed RTL.**

This extends the Phase 9 two-PX4 proof from a single fleet decision to a changing-world response:

`event A → fleet auction → PX4 A airborne → event B while A active → second fleet auction → PX4 B → both missions complete`

The behavior is deliberately described as **concurrent fleet reallocation**. It is not same-aircraft preemption, diversion, or cancellation/replanning of the first mission.

## Live setup

The validation used the same real backend path already proven by PR #123:

- real Redis;
- real `uvicorn backend.app.main:app`;
- two independent PX4 v1.14 Gazebo Classic `iris` instances;
- one `MAVLinkFleetRunner`;
- one shared `AdapterRegistry`;
- one `BusFleetOrchestrator`;
- external Redis-only event/progress probe.

PX4 links:

- `mav-001`: PX4 instance 1 / MAV_SYS_ID 2, UDP local 14581 → remote 14541;
- `mav-002`: PX4 instance 2 / MAV_SYS_ID 3, UDP local 14582 → remote 14542.

Both independent heartbeat gates passed before the backend was started.

## Acceptance sequence

1. Wait until both PX4 instances appear as canonical `FleetState` and are `DOCKED`.
2. Publish event A (`INTRUSION`, confidence 0.90) at 47.3980, 8.5460.
3. Observe SWARM award mission A to `mav-002`.
4. Wait for mission A to emit `EN_ROUTE` and for `mav-002` itself to appear as `EN_ROUTE` in canonical fleet state.
5. Confirm mission A has not reached a terminal phase.
6. Publish event B (`HEAT_SPOT`, confidence 0.99) at 47.39795, 8.54590 while mission A is still active.
7. Observe a second fleet-level award.
8. Require the second winner to differ from the first winner.
9. Require the second award to happen before mission A terminates.
10. Require both missions to reach `EN_ROUTE → ON_STATION → DONE`.

## Observed result

Mission A:

- winner: `mav-002`;
- mission: `5915bd56a1464fd5beb1a4691615dcf5`;
- award timestamp: 10:07:18.869983Z;
- fleet state confirmed `EN_ROUTE` before event B;
- phases: `EN_ROUTE → ON_STATION → DONE`.

Mission B:

- event published: 10:07:25.881126Z;
- winner: `mav-001`;
- mission: `06eb39fd75524823bde4c4e939fa4b38`;
- award timestamp: 10:07:25.882201Z;
- phases: `EN_ROUTE → ON_STATION → DONE`.

The second award followed event B essentially immediately while mission A was still active. Mission A remained non-terminal for another **28.178 s** after event B. Mission B remained active for **33.783 s** after event B. Total probe duration was **40.993 s**.

That overlap is the critical evidence: the two responses were not serialized.

## PX4-side evidence

Both PX4 instance logs independently record a real SITL mission lifecycle:

- `Armed by external command`;
- `Takeoff to 40.0 meters above home`;
- `Takeoff detected`;
- `Mission finished, loitering`;
- `Returning to launch`;
- `RTL HOME activated`;
- `RTL: landing at home position`.

Combined with PR #123's reach-aware mission semantics, `ON_STATION` is emitted only after final `MISSION_ITEM_REACHED`, not merely because a mission item became current.

## Integration-test proof

Before live SITL, `backend/tests/test_mavlink_dynamic_reallocation.py` passed against two slow reach-aware MAVLink fake autopilots.

The test intentionally holds mission A active long enough to publish event B after the first winner is visible as `EN_ROUTE`. It then requires:

- first winner = the near unit for event A;
- second winner = the other idle unit;
- distinct mission IDs;
- mission A still non-terminal at second award;
- both missions terminal only after event B was published.

This catches accidental serialization or reuse of a busy unit without paying the PX4/Gazebo cost on every unit-test run.

## What this proves

- SWARM's anomaly loop remains responsive while a real mission task is executing.
- Canonical fleet state makes an airborne unit unavailable to the normal allocator.
- A new event can trigger another auction while the first response remains active.
- The allocator can choose a different available PX4 and dispatch a second real SITL mission concurrently.
- Both missions retain the strict waypoint-reached/RTL completion semantics established by PR #123.

## What this does not prove

- No physical aircraft flew.
- This is not same-aircraft mid-flight preemption or diversion.
- There is no explicit priority-based cancellation/replanning policy yet.
- The Console does not yet expose a structured allocation explanation showing which units were eligible/excluded and why the winner was chosen.
- No customer workflow or field pilot is validated by this technical evidence.

## Next demo step

The next code should make this already-proven fleet decision **visible**, not invent another coordination engine.

Publish a structured allocation-decision frame alongside each award and project it into the Console so the operator can see, for example:

- event B arrived;
- `mav-002` excluded because `EN_ROUTE` / busy;
- `mav-001` eligible;
- `mav-001` selected with its score;
- both missions active concurrently.

That turns the validated backend behavior into the short investor/YC demo without overstating preemption capabilities.
