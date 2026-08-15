# Phase 11 — Multi-agent execution group validation

**Status:** PASS  
**Date:** 2026-08-15  
**Validated surface:** SwarmOS-owned `COOPERATIVE_VERIFY` executed by multiple live PX4 v1.14 SITL instances through the real MAVLink backend runtime.

## Claim validated

One logical SwarmOS objective can be decomposed centrally into multiple role-specific child missions, assigned to distinct physical executors, executed concurrently, and aggregated back into one authoritative `ExecutionGroup` without giving mission-level decision authority to the agents.

This is a SITL validation. It is not field-flight or physical-hardware proof.

## Validation run

- GitHub Actions run: `31890903690`
- Job: `95026908982`
- Validated branch head: `abb7ed8a779ca2e4728906a965c7b32bbccf1842`
- Validation artifact: `execution-group-live-sitl-validation`
- Artifact ID: `9248543815`
- Artifact ZIP SHA-256: `4065d94b71c993a09128336738730e243d460c219263f697cb55a5a9b8dcc7dd`
- Probe: `scripts/phase11_execution_group_probe.py`
- Probe result: `status=pass`
- Probe duration: `45.699 s`

The artifact contains the probe JSON plus backend and PX4 diagnostics.

## PX4 fleet proof

Four independent PX4 SITL instances produced MAVLink heartbeats before SwarmOS started the cooperative mission runtime:

| SWARM unit | UDP port | PX4 system id |
|---|---:|---:|
| `mav-001` | 14541 | 2 |
| `mav-002` | 14542 | 3 |
| `mav-003` | 14543 | 4 |
| `mav-004` | 14544 | 5 |

All four were published as available fleet state before the anomaly was injected.

## Execution group truth

A high-confidence intrusion (`confidence=0.99`) produced one parent objective and one authoritative group:

- anomaly: `f771f7a6bf11421091f1097631cbacd1`
- group: `87bc1e7685984be6a5d3aff7afdeb623`
- objective kind: `COOPERATIVE_VERIFY`
- parent objective mission: `2f4907d5684e462f9c6732b720c932aa`
- requested members: `3`
- final state: `COMPLETED`
- failure reason: `null`

SwarmOS selected:

| Role | Agent | Child mission | Allocation score | Final state |
|---|---|---|---:|---|
| `PRIMARY_OBSERVER` | `mav-004` | `1f8daa173a0b4fb1bae3e6f3b868d0a2` | 2.2613445425 | `COMPLETED` |
| `SECONDARY_OBSERVER` | `mav-003` | `0b7fdd840ff24454a2b72fed9255c32c` | 2.2599149690 | `COMPLETED` |
| `OVERWATCH` | `mav-002` | `569e4b2c664640a89352d7f435466663` | 2.2583318588 | `COMPLETED` |

`mav-001` remained the unassigned spare.

The probe observed awards for the three child missions and verified that the parent objective mission received **no award**. The physical executors therefore received only child work selected by SwarmOS; no agent received or interpreted the multi-agent parent objective.

## Runtime evidence

Each selected PX4 produced the same authoritative runtime sequence:

1. `EN_ROUTE`
2. `ON_STATION` with `mavlink_mission_item_reached`
3. `DONE` with `mavlink_rtl_command_acknowledged`

This was verified independently for all three child mission IDs. The aggregate group moved to `COMPLETED` only after all required roles completed.

## Failure and authority gates covered separately

The deterministic integration suite also validates:

- three requested roles are assigned to three unique agents;
- insufficient eligible capacity fails closed before any partial dispatch;
- a failed member is replaced centrally by a spare agent;
- an executor exception becomes explicit terminal failure truth and enters the same replacement policy;
- only `PRIMARY_OBSERVER` may execute the presence-response payload policy;
- secondary and overwatch roles cannot independently activate payload actions;
- orchestration-only parent missions are rejected by physical adapters, including the simulator.

## Trust boundary

The validated architecture is:

```text
observation / anomaly
        ↓
      SwarmOS
  form ExecutionGroup
  select agents + roles
  create child missions
        ↓
MAVLink / vendor adapters
        ↓
 thin physical executors
        ↓
progress + runtime evidence
        ↓
      SwarmOS
 aggregate / replace / complete
```

Agents do not elect themselves, choose peers, negotiate roles, command other agents, or decide how to repair a degraded group. Those decisions remain in SwarmOS.

## Demo/UI boundary

The Console may render `ExecutionGroup` composition, role ownership, scores, replacement history and runtime evidence because those are server-published truth frames. It must not infer membership or recompute coordination client-side.

Existing stock CCTV and drone footage remain visualization only and must continue to be labeled simulated. This validation does not turn imagery into live sensor evidence.
