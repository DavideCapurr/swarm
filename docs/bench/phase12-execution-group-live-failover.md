# Phase 12 — Live PX4 execution-group failover validation

**Status:** PASS  
**Date:** 2026-08-15  
**Validated surface:** SwarmOS-owned `COOPERATIVE_VERIFY` execution group with a real process-level failure injected into one PX4 v1.14 SITL member while the mission was active.

## Claim validated

A physical executor can disappear during an active multi-agent objective without gaining or requiring peer-level decision authority. SwarmOS detects the resulting execution failure, marks the original member as replaced, centrally selects an unused spare for the same role, dispatches a new child mission, and preserves the aggregate objective through completion.

This is a SITL validation. It is not physical-aircraft or field-network proof.

## Validation run

- GitHub Actions run: `31898333764`
- Job: `95044998197`
- Validated branch head: `6e3b8ef7c9652d19d1d9303e661cc6dff7761569`
- Artifact: `execution-group-live-failover-validation`
- Artifact ID: `9250436509`
- Artifact ZIP SHA-256: `d099879c54fad86caea36d9b0a3aa990e713a1ef257131c9b1d65cf42824c439`
- Probe result: `status=pass`
- Probe duration: `49.959 s`

The artifact contains the authoritative probe JSON plus backend and PX4 diagnostics.

## Fleet and initial group

Four independent PX4 SITL endpoints produced heartbeats before SwarmOS accepted the cooperative objective:

| SWARM unit | UDP port | PX4 system id |
|---|---:|---:|
| `mav-001` | 14541 | 2 |
| `mav-002` | 14542 | 3 |
| `mav-003` | 14543 | 4 |
| `mav-004` | 14544 | 5 |

A confidence `0.99` intrusion created:

- anomaly: `d3e97452bda44cbc99cd5e16d67aed2f`
- execution group: `4efceb04bdda4f3e88f9da18dbb158c6`
- parent objective: `8582edb3f2984289ab756602ac03aad5`
- objective kind: `COOPERATIVE_VERIFY`
- requested roles: `3`

SwarmOS initially selected:

| Role | Agent | Child mission | Score |
|---|---|---|---:|
| `PRIMARY_OBSERVER` | `mav-004` | `0a224497d6384724aa3ee4043dcffc26` | 2.2613507126 |
| `SECONDARY_OBSERVER` | `mav-003` | `b9a64ed080bc47e498ea18e4d8655069` | 2.2599093608 |
| `OVERWATCH` | `mav-002` | `3dbd3eeaee6f43d29f6498a8042990ab` | 2.2583201001 |

`mav-001` remained unused spare capacity.

The parent objective received **no physical award**. Only the three SwarmOS-created child missions were awarded.

## Physical fault injection

The validation waited until the selected `SECONDARY_OBSERVER` was actually `EN_ROUTE`.

At `2026-08-15T17:29:07.164547Z`, the validation process sent `SIGKILL` to the PX4 process for `mav-003` / SITL instance 3:

```text
killing agent=mav-003 instance=3 pid=692
```

The probe did **not** publish a synthetic `FAILED` mission frame and did not call execution-group orchestration internals.

The real runtime subsequently emitted:

```text
mission: b9a64ed080bc47e498ea18e4d8655069
agent: mav-003
phase: FAILED
error: MAVLinkCommandError: COMMAND_LONG 20 timed out waiting for COMMAND_ACK
```

Failure truth was observed at `2026-08-15T17:29:14.240655Z`.

Observed process-failure detection latency from SIGKILL to the recorded `FAILED` event was approximately **7.08 s**.

## Central replacement

SwarmOS then selected the previously unused `mav-001` for the same logical role:

```text
failed member:
  mav-003 -> SECONDARY_OBSERVER -> REPLACED

replacement:
  mav-001 -> SECONDARY_OBSERVER
  replaces_agent_id: mav-003
  mission: a03fd8ddc5c140e89ec0eeb717296c42
  score: 2.2566069734
```

The replacement selection was visible in authoritative execution-group truth at `2026-08-15T17:29:14.245648Z`, about **2 ms** after the probe observed the failure event.

A new award was then published for the replacement child mission with `winner_agent_id=mav-001`.

No surviving drone selected the spare, negotiated the role, or commanded `mav-001`. The decision was made by SwarmOS.

## Recovery evidence

The replacement `mav-001` produced the required physical-runtime evidence:

```text
EN_ROUTE
-> ON_STATION + mavlink_mission_item_reached
-> DONE + mavlink_rtl_command_acknowledged
```

`mav-001` reached verified `ON_STATION` at `2026-08-15T17:29:54.641438Z` and completed with accepted RTL at `2026-08-15T17:29:54.675475Z`.

The aggregate group then reached:

```text
state: COMPLETED
failure_reason: null
```

The other required roles also completed with the same evidence boundary:

- `mav-004` / `PRIMARY_OBSERVER`: `MISSION_ITEM_REACHED` then RTL acknowledgement
- `mav-002` / `OVERWATCH`: `MISSION_ITEM_REACHED` then RTL acknowledgement

Total elapsed time from killing `mav-003` to recovered group completion was approximately **47.51 s** in this run.

## What this proves

This run supports these claims:

1. one logical objective can depend on multiple physical agents;
2. one active member can disappear at the process/executor level;
3. the failed member is converted into explicit runtime failure truth rather than silently ignored;
4. SwarmOS, not a peer drone, chooses the spare and preserves the role;
5. replacement ownership is auditable through `replaces_agent_id` and a new child award;
6. the replacement reaches the mission target with real `MISSION_ITEM_REACHED` evidence;
7. the replacement returns through an acknowledged RTL command;
8. the overall execution group can still complete after losing one of its original members.

This is the concrete redundancy/fungibility proof behind the architecture principle:

> **Make the agents cheap. Make the swarm intelligent.**

## Boundaries

This validation does **not** prove:

- physical-aircraft fault tolerance;
- cellular/radio network partition handling;
- malicious telemetry detection;
- safe physical behavior of a failed aircraft after loss of SwarmOS control;
- regulatory or field-flight readiness;
- unlimited replacement depth. The current execution-group policy intentionally bounds replacements per role.

The killed PX4 was a SITL process, and failure was recognized when an expected MAVLink command acknowledgement timed out. Those limits should remain explicit in demos and external claims.
