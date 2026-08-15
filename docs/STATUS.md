# SwarmOS — execution status

Live status for the current technical state. Historical phase notes live in [`STATUS-archive.md`](STATUS-archive.md).

## Current state — 2026-08-15

SWARM has an end-to-end PX4 SITL coordination path, first-class SwarmOS-owned multi-agent `ExecutionGroup`s, live member replacement, and an operator Console that renders backend-owned allocation/runtime/payload truth.

The architecture invariant is:

> **SwarmOS decides. Physical agents execute. Console supervises.**

Physical agents do not legitimately select fleet missions, elect themselves or peers, command other units, negotiate execution-group roles, or turn local observations directly into fleet actions. Onboard autopilots retain the low-level flight and bounded safety behavior necessary to execute safely.

The MAVLink/PX4 path remains **SITL-validated, not bench- or field-validated on physical aircraft**.

## Current proof summary

| Area | State |
|---|---|
| Core domain / mission model / FSM | **done** |
| Centralized fleet-state allocator | **done** |
| Thin physical-agent adapter boundary | **done / architecture-guarded** |
| Simulated adapter and scenarios | **done** |
| Console + backend + telemetry | **done** |
| Structured allocation/runtime/payload truth | **done** |
| Persistence / audit / security baseline | **done** |
| MAVLink/PX4 adapter | **live PX4 SITL-validated; no physical-aircraft proof yet** |
| Dynamic multi-event fleet reallocation | **live two-PX4 SITL-validated** |
| Waypoint-completion semantics | **final `MISSION_ITEM_REACHED` required; timeout fails closed** |
| Bounded payload presence response | **PX4 SITL output-confirmed; speaker explicitly simulated** |
| First-class one-mission multi-agent `ExecutionGroup` | **implemented and live four-PX4 SITL-validated** |
| Live execution-group member failure/replacement | **validated with PX4 process SIGKILL while `EN_ROUTE`** |
| Intrusion demo Console `/demo/intrusion` | **final demo surface; truth renderer** |
| Final demo rehearsal | **3 consecutive clean PASS takes, ~62 s each** |
| Same-aircraft preemption/diversion | **not implemented / not claimed** |
| Physical bench / field proof | **not yet done** |
| Pilot / revenue | **none yet** |

## Decision-authority model

SwarmOS owns mission-level decisions including:

- objective and event response;
- eligibility and exclusions;
- candidate scoring and allocation;
- required agent count;
- `ExecutionGroup` formation;
- role assignment;
- mission ownership;
- replacement and retasking;
- abort / return / rotation decisions;
- payload-response policy;
- fleet-level follow-up and conclusion.

Physical agents/adapters own execution only:

- low-level flight/motion control through the autopilot;
- following SwarmOS-issued mission primitives;
- local safety reflexes/failsafes;
- sensor capture;
- telemetry, progress, and execution evidence.

See [`adr/0011-central-decision-authority.md`](adr/0011-central-decision-authority.md).

## Validated evidence

### Dynamic multi-event allocation

The changing-condition path has a reproducible two-event / two-PX4 overlap proof. See [`bench/phase10-dynamic-multi-event-validation.md`](bench/phase10-dynamic-multi-event-validation.md).

In the validated path, event B arrives while mission A is active. The central allocator treats the first owner as occupied and selects another available unit. The proof demonstrates concurrent fleet reallocation, not same-aircraft preemption.

### Verified arrival and bounded payload response

The PX4 path requires final `MISSION_ITEM_REACHED` before accepting `ON_STATION`; timeout fails closed.

The bounded payload proof in [`bench/payload-presence-sitl-validation.md`](bench/payload-presence-sitl-validation.md) confirms the configured PX4 SITL output state before reporting the light as active. The restricted-area speaker remains explicitly `SIMULATED`.

This is flight-controller command-to-output proof in SITL, not proof of a physical lamp, cable, driver, or speaker.

### Multi-agent `ExecutionGroup`

[`bench/phase11-execution-group-validation.md`](bench/phase11-execution-group-validation.md) validates one SwarmOS-owned `COOPERATIVE_VERIFY` objective through four independent PX4 SITL instances.

SwarmOS:

- created one authoritative `ExecutionGroup`;
- required three roles;
- selected three distinct agents from four available agents;
- assigned `PRIMARY_OBSERVER`, `SECONDARY_OBSERVER`, and `OVERWATCH`;
- created role-specific child `VERIFY` missions;
- left one PX4 as spare capacity;
- dispatched no physical award for the orchestration-only parent objective;
- accepted `ON_STATION` only after `MISSION_ITEM_REACHED` for every selected child;
- accepted completion with acknowledged RTL for every child;
- completed the parent group only after all required roles completed.

This proves first-class one-objective multi-agent composition through the real MAVLink backend runtime while keeping mission authority in SwarmOS.

### Live member failure and replacement

[`bench/phase12-execution-group-live-failover.md`](bench/phase12-execution-group-live-failover.md) validates the replacement path against four independent PX4 SITL instances.

The selected `SECONDARY_OBSERVER`, `mav-003`, was SIGKILLed while actually `EN_ROUTE`. The probe did not inject a synthetic mission failure or call execution-group internals.

The runtime then:

1. emitted explicit failure truth for `mav-003`;
2. marked the original member `REPLACED`;
3. centrally selected unused spare `mav-001` for the same logical role;
4. published a new child award with replacement provenance;
5. observed `mav-001` reach `ON_STATION` through `mavlink_mission_item_reached`;
6. observed acknowledged RTL;
7. completed the aggregate `ExecutionGroup`.

No surviving physical agent selected or commanded the spare.

### Final demo rehearsal

[`bench/final-demo-rehearsal.md`](bench/final-demo-rehearsal.md) is the authoritative recording runbook for `/demo/intrusion`.

Three consecutive clean authenticated rehearsals passed at approximately 62 seconds each. Every take validated:

- clean startup;
- event 1 allocation and dispatch;
- `EN_ROUTE`;
- verified `ON_STATION`;
- bounded payload response;
- event 2 while mission 1 was still active;
- owner 1 excluded from event 2 as `BUSY` with mission 1's exact `active_mission_id`;
- a different owner selected for event 2;
- both missions active simultaneously before mission 1 cleanup;
- payload cleanup;
- acknowledged RTL.

The Console browser check was independent of the backend/bus truth probe.

## Console truth boundary

`/demo/intrusion` may display server-issued operational truth including:

- anomaly identity/evidence;
- eligible units;
- excluded units and exclusion reason;
- exact allocator score and score breakdown;
- selected unit and mission ownership;
- mission runtime phase/evidence;
- `ExecutionGroup` composition, role ownership, and replacement history;
- structured payload status and execution mode.

Stock CCTV/drone footage is visualization only and must remain clearly labeled simulated. The frontend must not calculate winners, synthesize mission state, upgrade a simulated payload to physical, or infer `ON_STATION` from a timer.

The legacy dashboard at `/` is separate from the definitive demo surface and is not part of the final-demo presentation path.

## Multi-agent collective capability

One logical objective can now be composed into several role-specific physical executors through a SwarmOS-owned `ExecutionGroup`:

```text
SWARM mission objective
        │
        ▼
SwarmOS ExecutionGroup
  ├── PRIMARY_OBSERVER   → physical agent → child mission
  ├── SECONDARY_OBSERVER → physical agent → child mission
  └── OVERWATCH          → physical agent → child mission
        │
        └── spare selected centrally on member failure
```

The group is not an autonomous sub-swarm. Member agents do not negotiate roles or gain authority over peers.

## Engineering posture

The demo path is feature-frozen. Do not add product breadth, frontend redesign, architecture changes, dependency upgrades, or runtime refactors merely for presentation polish.

The next technical evidence gap is physical hardware, not another simulated coordination feature. Until physical validation occurs, external claims must remain explicitly SITL-scoped.

## Permanent claim boundaries

- simulated ≠ SITL-validated;
- SITL-validated ≠ physical bench/field proof;
- PX4 output confirmation ≠ physical payload proof;
- central mission authority ≠ unhackable physical endpoints;
- local autopilot safety reflexes ≠ fleet-level mission autonomy;
- one successful injected SITL process failure ≠ general field fault tolerance.
