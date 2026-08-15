# SwarmOS — execution status

Live, slim status. Read this first for the current execution state.

The canonical company thesis is [`../swarm-thesis.md`](../swarm-thesis.md). When this status document or an older product/roadmap document conflicts with the thesis, the thesis wins.

Full historical phase notes live in [`STATUS-archive.md`](STATUS-archive.md).

## Current strategic state — 2026-08-15

SWARM has an end-to-end PX4 SITL coordination path and an operator Console that renders backend-owned allocation/runtime/payload truth.

The core architecture invariant is now explicit:

> **SwarmOS decides. Physical agents execute. Console supervises.**

Drones do not legitimately select fleet missions, elect themselves or peers, command other units, or turn local observations directly into fleet actions. Onboard autopilots still own low-level flight execution and bounded safety failsafes such as stabilization, waypoint following, geofence enforcement, low-battery RTL, lost-link behavior, and obstacle avoidance.

Centralizing mission authority limits each endpoint's legitimate authority surface. It does not make an aircraft impossible to compromise: agent-originated telemetry and sensor data remain semi-trusted evidence.

## Current proof

The real backend-owned PX4 path has successive SITL proofs through the same orchestration lifecycle:

1. **multi-vehicle execution:** two independent PX4 v1.14 instances become one SWARM fleet, SWARM centrally evaluates fleet state, selects a unit, the selected PX4 reaches the final waypoint, and SWARM commands RTL;
2. **changing-condition coordination:** while the first PX4 is still `EN_ROUTE`, a second event triggers another central allocation and SWARM assigns the second response to the other available PX4. Both missions remain independently active and complete;
3. **bounded physical-output response:** after verified `ON_STATION`, SWARM drives a configured PX4 offboard actuator output, confirms the output state from PX4 telemetry, runs bounded cleanup, then allows the lifecycle to continue to RTL/DONE;
4. **truth-rendering Console:** `/demo/intrusion` renders structured backend allocation decisions, eligible/excluded units, score breakdown, winner, mission ownership, runtime evidence and payload execution mode rather than reconstructing those claims in React.

The MAVLink/PX4 path remains **SITL-validated, not bench- or field-validated on physical aircraft**.

## Current state

| Area | State |
|---|---|
| Core domain / mission model / FSM | **done** |
| Centralized fleet-state allocator | **done** |
| Thin physical-agent adapter boundary | **done / architecture-guarded** |
| Simulated adapter and scenarios | **done** |
| Console + backend + telemetry | **done** |
| Structured allocation truth | **done** |
| Structured runtime evidence | **done** |
| Structured payload evidence | **done** |
| Persistence / audit / security baseline | **done** |
| Autonomy + shadow-mode baseline | **done; server-side** |
| MAVLink/PX4 adapter | **live PX4 SITL-validated; no physical aircraft proof yet** |
| Multi-vehicle PX4 backend orchestration | **live 2-vehicle SITL-validated** |
| Dynamic multi-event fleet reallocation | **live 2-vehicle SITL-validated** |
| Waypoint-completion semantics | **final `MISSION_ITEM_REACHED` required; timeout fails closed** |
| Bounded payload presence response | **PX4 SITL output-confirmed; speaker remains explicit simulation** |
| Intrusion demo Console `/demo/intrusion` | **live truth renderer** |
| Same-aircraft preemption/diversion | **not implemented / not claimed** |
| First-class one-mission multi-agent execution groups | **not implemented / architecture defined only** |
| Physical bench / field proof | **not yet done** |
| Pilot / revenue | **none yet** |

## Decision-authority model

SwarmOS owns mission-level decisions including:

- whether a cue requires action;
- which unit or units are eligible;
- exclusions and reasons;
- candidate scoring and winner selection;
- mission ownership;
- retask, replacement, rotation, abort and return decisions;
- payload-response policy;
- future execution-group composition and role assignment.

Physical agents/adapters own execution only:

- low-level flight control through the autopilot;
- following SWARM-issued mission primitives;
- local safety reflexes/failsafes;
- sensor capture;
- telemetry, progress and execution evidence.

See [`adr/0011-central-decision-authority.md`](adr/0011-central-decision-authority.md) and [`security/agent-trust.md`](security/agent-trust.md).

## Evidence already available

### Single and multi-PX4

The original MAVLink/PX4 path has a reproducible single-vehicle SITL proof covering connect, status visibility, telemetry ingest, mission dispatch and return-to-launch. See [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md).

The backend-owned fleet path has a reproducible **two-PX4 live SITL proof**. See [`bench/phase9-multi-sitl-validation.md`](bench/phase9-multi-sitl-validation.md) and [`bench/artifacts/phase9-multi-sitl-backend-probe.json`](bench/artifacts/phase9-multi-sitl-backend-probe.json).

### Dynamic multi-event allocation

The changing-condition path has a reproducible **two-event / two-PX4 overlap proof**. See [`bench/phase10-dynamic-multi-event-validation.md`](bench/phase10-dynamic-multi-event-validation.md) and [`bench/artifacts/phase10-dynamic-multi-event-probe.json`](bench/artifacts/phase10-dynamic-multi-event-probe.json).

In that live run:

- event A was assigned to `mav-002`;
- SWARM waited until `mav-002` was visibly `EN_ROUTE` in canonical fleet state;
- event B arrived while mission A was still active;
- the central allocator treated the first unit as occupied and selected `mav-001` for event B;
- mission A stayed active for another **28.178 s** after event B;
- mission B stayed active for **33.783 s** after event B;
- both missions completed `EN_ROUTE → ON_STATION → DONE`;
- both PX4 logs independently show arm, takeoff, mission finish, RTL and landing.

This proves concurrent fleet reallocation, not same-aircraft preemption and not first-class group composition.

### Bounded payload response

The bounded payload path has a reproducible **two-PX4 live SITL proof on the same backend-owned lifecycle**. See [`bench/payload-presence-sitl-validation.md`](bench/payload-presence-sitl-validation.md) and [`bench/artifacts/payload-presence-sitl-backend-probe.json`](bench/artifacts/payload-presence-sitl-backend-probe.json).

In that run:

- both PX4 instances had unused MAIN5 mapped to `Offboard Actuator Set 1` before the backend started;
- an `INTRUSION` anomaly at confidence `0.95` entered SWARM;
- SWARM selected `mav-002` centrally;
- mission progress was `EN_ROUTE → ON_STATION → DONE`;
- `ON_STATION` required the final `MISSION_ITEM_REACHED`;
- light ON was reported only after PX4 output channel 5 was observed in the requested high state;
- the restricted-area speaker message remained explicitly `SIMULATED`;
- cleanup stopped the message and confirmed the PX4 output low state;
- `DONE` arrived only after that cleanup sequence;
- the external probe passed in **36.912 s**.

This is flight-controller command-to-output proof in SITL, not proof of a physical lamp, driver, cable or speaker.

## Console truth boundary

The `/demo/intrusion` Console may display only server-issued operational truth:

- anomaly identity/evidence;
- eligible units;
- excluded units and exclusion reason;
- exact allocator score and score breakdown;
- selected unit;
- mission ownership;
- mission runtime phase/evidence;
- structured payload status and execution mode.

Stock CCTV/drone footage is visualization only and must remain clearly labeled simulated. The frontend must not calculate winners, synthesize mission state, upgrade a simulated payload to physical, or infer `ON_STATION` from a timer.

## Multi-agent collective capability

The current system already coordinates multiple units and parallel missions. It does **not yet** have a first-class runtime object for several agents jointly satisfying one logical mission.

The intended next-level model is:

```text
SWARM mission objective
        │
        ▼
SwarmOS execution group
  ├── mav-002 → role A
  ├── mav-004 → role B
  └── mav-006 → role C
```

The execution group will be a SwarmOS-owned logical object. Member agents will not negotiate roles or become local decision authorities. Until that runtime exists and is tested, external claims must distinguish “multi-agent fleet / simultaneous missions” from “one mission dynamically composed from several agents.”

## Current engineering posture

The validated Console path is now sufficient to rehearse and record the existing allocation/reallocation story. Avoid adding unrelated product breadth merely for visual complexity.

If the next demo is expanded to more than two PX4 instances, validate that exact scale before claiming it. If SWARM later demonstrates one mission using multiple units together, implement that as a centrally planned execution-group capability rather than peer-to-peer drone autonomy.

## Permanent claim boundaries

- simulated ≠ SITL-validated;
- SITL-validated ≠ physical bench/field proof;
- PX4 output confirmation ≠ physical payload proof;
- multiple units in the fleet ≠ first-class execution-group support;
- central mission authority ≠ unhackable physical endpoints;
- local autopilot safety reflexes ≠ fleet-level mission autonomy.
