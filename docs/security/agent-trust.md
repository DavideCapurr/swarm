# Physical-agent trust boundary

This note complements [`threat-model.md`](threat-model.md) and
[`ADR 0011`](../adr/0011-central-decision-authority.md).

## Security objective

A physical agent is an execution endpoint and evidence source, not a
mission-authority principal.

Compromise of one drone/robot must not legitimately grant that endpoint the
ability to:

- create or award fleet missions;
- select itself or peers for work;
- retask another agent;
- change fleet policy;
- turn a local detection directly into a fleet command;
- form an independently commanding sub-swarm.

Only SwarmOS owns those actions.

## What centralization does not solve

This boundary does **not** make a physical agent unhackable.

A compromised endpoint may still:

- falsify position, battery, health or other telemetry;
- manipulate camera/sensor output;
- replay or omit evidence;
- ignore SwarmOS commands;
- be directly controlled through a compromised autopilot or vendor link.

A false observation can still cause a bad central decision if SwarmOS trusts it
blindly. Agent-originated data must therefore be treated as semi-trusted input.

## Current controls

Current repository controls include:

- canonical typed telemetry/fleet-state models;
- freshness checks before a bus-backed agent enters allocation;
- value/range validation in core models and adapter paths;
- inbound rate limiting in adapter telemetry paths;
- central policy/geofence validation;
- central mission allocation and audit;
- local geofence, low-battery and lost-link failsafes where declared by the
  adapter/autopilot.

These controls reduce risk but are not proof against a fully compromised flight
controller or forged sensor source.

## Future hardening directions

Do not claim these as implemented until they are built and validated:

- hardware/device identity and remote attestation;
- cryptographic telemetry provenance;
- per-agent command authorization with short-lived credentials;
- cross-agent or fixed-sensor corroboration;
- plausibility checks across position, kinematics and independent observations;
- quarantine/reputation logic for inconsistent agents;
- redundant command/control paths for critical deployments.

## Availability tradeoff

Central mission authority makes SwarmOS a critical availability and integrity
component. Losing SwarmOS must not make an airborne vehicle unsafe.

That is why bounded autopilot-side safety reflexes remain allowed and required:
low-battery RTL, lost-link behavior, geofence enforcement, stabilization and
other immediate flight-safety functions may execute without waiting for a
central mission decision.

The boundary is therefore:

```text
SwarmOS:   what / who / where / when / why / what next
Autopilot: how to execute safely + how to fail safe locally
```
