# SWARM — Vision

*Distilled from the strategy documents in `docs/pdf/`. Single canonical source. When
sentiment diverges between PDFs, the most recent version wins (`*_v2.pdf`).*

## What SWARM is

SWARM is the **operating system for autonomous drone operations** — vendor-
neutral **autonomous coordination infrastructure**, not a drone company.

The drones are replaceable; the coordination layer is the product. One OS,
any airframe, generalizing across drone **task classes** — patrol, inspection,
monitoring, environmental intelligence, disaster response, logistics and
defense ISR — civilian and (ISR-only) non-civilian. Today it is executed
deeply on **one** wedge (see below); the platform is earned, not declared.

## The wedge

Initial market: **private high-value territories** — villas, vineyards, resorts,
agricultural land, isolated luxury properties. Subscription-first.

Initial product shape: **SWARM Patrol Cell** — mobile patrol and verification for
private territories without requiring SWARM-owned fixed cameras, thermal towers,
or proprietary ground sensors in the MVP.

Initial beachhead: **wildfire-risk patrol, verification and response
coordination**. Wildfire is the first proof path, not the product boundary.
The same Patrol Cell loop can support private-territory incidents such as
intrusion, unknown person/vehicle, missing-person search inside a bounded site,
post-storm damage checks, asset anomalies, manual verification requests and
stale-sector checks when they reuse the same patrol, evidence and supervised
decision path.

SWARM does not initially replace firefighters or first responders and does not
promise continuous 24/7 detection without enough drones, docks and regulatory
clearance. It reduces the time between a suspicious cue and an operator-visible
evidence packet.

The wedge is wildfire because it is:
- economically urgent
- globally increasing
- operationally measurable
- socially accepted
- technically coherent with the long-term architecture

The MVP input model is deliberately lightweight: weather and fire-risk feeds,
public satellite or hotspot signals where available, human reports, guard/owner
call-ins, previous drone patrol observations, and stale-sector routines. These
inputs are cues, not truth; SWARM turns them into patrol priorities,
verification missions and auditable decisions.

## Long-term vision

A distributed autonomous **coordination** infrastructure layer for
time-critical territorial events. The same decide → verify → evidence →
supervise loop is **dual-use** at the core:

- **Civilian resilience** — environmental monitoring, wildfire response,
  disaster coordination, environmental intelligence, infrastructure sensing,
  autonomous operational systems.
- **Defense ISR** — perimeter and base/border security, counter-UAS
  awareness, force protection: the same patrol → verify → evidence → escalate
  loop, human-on-the-loop. Intelligence, surveillance and reconnaissance —
  **not** weapons.

One coordination core, many territories. The civilian wedge ships first on
purpose (see "The wedge"); the dual-use platform is the long game, bounded by
the permanent rule below.

## The moat

- **Coordination** — auction-based mission allocation across heterogeneous fleets.
- **Interoperability** — uniform `DroneAdapter` across DJI, MAVLink/PX4, Autel,
  Parrot, Skydio. Customers pay for outcomes, not for one vendor's lock-in.
- **Telemetry & intelligence** — historical data per territory drives risk scoring
  and adaptive patrol routes.
- **Orchestration** — multi-drone cooperation (relay + scan, rotational coverage,
  battery-aware swap).
- **Mobile coverage** — drones act as movable sensors and response units, so the
  first wedge can start without a fixed sensor buildout.

Hardware commoditizes. The network becomes the product.

## What SWARM does NOT do (initially)

- Replace firefighters or first responders.
- Build proprietary drones.
- Install a proprietary fixed sensor network as a prerequisite for the MVP.
- Promise continuous detection before the hardware, staffing and regulatory
  envelope make it true.
- Operate in dense urban / highly occluded environments.
- Government / defense ISR contracts **in the MVP**. Defense ISR is a
  deliberate *later* lane (see Long-term vision), not an MVP target; the
  civilian estate/wildfire wedge ships first.
- Broad crime/public-safety/security marketplaces. Private-territory
  intrusion can be a supported event class only when it reuses the same
  Patrol Cell workflow.

## Permanent boundary (every context, civilian or defense)

These hold regardless of customer or phase — they are **not** "initially":

- **No weaponization.** SWARM coordinates, patrols, verifies and produces
  evidence. It is not a weapons system: no lethal autonomy, no autonomous
  targeting, no weapons payload, no strike tasking.
- **Human-on-the-loop, always.** Autonomy decides and executes; a human can
  always intervene. No autonomy that isn't verifiable (the shadow-mode gate).
- **Export-control discipline.** Any defense or dual-use engagement is
  reviewed for ITAR/EAR and applicable law before it proceeds.

## Phased roadmap

The long-range capability horizon below comes from
`SWARM_execution_roadmap_0_to_100M.pdf`. Current execution from the
Phase 7 state is tracked in
[`docs/plan/swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md):
finish the wildfire proof, validate the buyer and flight path, then earn
pilot, capital and later platform scope.

| Phase | Months | Focus |
|---|---|---|
| 0 | 0–3   | Study, simulation, capability accumulation |
| 1 | 3–6   | First B-Lite prototype: dock v0 + 2–4 drones, scheduled patrol |
| 2 | 6–12  | Territory understanding (geometry, obstacles, safe flight zones) |
| 3 | 12–18 | Patrol intelligence (adaptive logic, risk scoring) |
| 4 | 18–30 | Persistent awareness layer (rotation, relay, hybrid sensing) |
| 5 | 30–42 | True swarm coordination (mission allocation, cooperative verify) |
| 6 | 42–54 | Reliability — false positive reduction, weather, maintenance |

B-Full ≠ zero humans. B-Full = minimal required human configuration.

## Operating principles

- Capability before narrative.
- Realism over aesthetics. "Operational, not cinematic."
- One wedge, executed deeply.
- The network is the product, not the drone.

## Voice

> Quiet. Precise. Already arrived.
> Many units. One intention.
