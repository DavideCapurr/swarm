# SWARM Patrol Cell

## Positioning

SWARM Patrol Cell is the first product shape for SWARM: a mobile
territorial-awareness and incident-verification service for private
high-value land.

It uses drones as mobile sensors and response units. It does not require
SWARM-owned fixed cameras, fixed thermal towers, or proprietary ground
sensors in the MVP.

The promise is not continuous omniscience. The promise is risk-based
mobile coverage, rapid verification, and an auditable incident record
without installing a fixed sensor network.

## First Beachhead

The first proof and buyer conversation start with wildfire-risk patrol
because the problem is urgent, measurable, and coherent with territorial
resilience. That is a beachhead, not a product boundary.

The same Patrol Cell loop should support other private-territory event
classes when they reuse the same patrol, verification, evidence and
operator-supervision path:

- smoke, heat, flame or fire-risk cue;
- perimeter intrusion or unknown person/vehicle;
- missing person or welfare check inside a bounded property;
- post-storm or post-incident damage check;
- infrastructure or asset anomaly;
- manual "go verify this point" request;
- stale priority sector that needs a fresh observation.

The buyer does not pay for a drone to "look at a fire". The buyer pays
for:

- a recent view of the important parts of the territory;
- faster conversion of an uncertain signal into operational evidence;
- fewer unnecessary callouts from unverified signals;
- a clear escalation package when an event is credible, whatever the
  supported event class is;
- a record of patrols, decisions, and response times.

## Input Model

The MVP avoids proprietary fixed sensor infrastructure. SWARM can still
prioritize patrols and verification from lightweight or already-available
signals:

- weather and fire-risk feeds;
- public satellite or hotspot signals where available;
- human reports from a guard, owner, worker, guest, or neighbor;
- phone/manual call-ins from the property team;
- observations from previous drone patrols;
- automatic "stale sector" routines when an important area has not been
  seen recently.

External inputs are treated as cues, not truth. SWARM turns cues into
verification missions, evidence packets, and operator-visible decisions.

## Operating Loop

1. Onboard the territory into sectors, assets, safe flight areas, and
   risk zones.
2. Track coverage freshness for each sector: last seen, confidence,
   risk, and priority.
3. Schedule patrols from risk and freshness, not from a static route
   alone.
4. Create an anomaly from a patrol observation, external cue, manual
   report, or stale-sector rule.
5. Dispatch the best available drone to verify from one or more vantage
   points.
6. Build an evidence packet: coordinates, captures, source, confidence,
   timeline, nearby assets, and recommended disposition.
7. Let the operator escalate, dismiss, request another pass, or return
   the unit.
8. Produce customer-facing patrol and incident reports.

## MVP Metrics

The MVP should be judged on these metrics before expanding scope:

- coverage freshness: percentage of priority sectors seen within the
  target interval;
- worst-sector staleness during high-risk windows;
- cue-to-dispatch latency;
- dispatch-to-first-capture latency;
- cue-to-evidence-packet latency;
- verified events versus dismissed/false-positive cues;
- operator interventions and overrides;
- evidence completeness for each incident.

## Cost Logic

The first deployment stays lightweight by avoiding fixed infrastructure
first.

- Manual/supervised MVP: one thermal-capable drone, spare batteries,
  operator, SWARM Console, and reports. This validates buyer value with
  the lowest hardware commitment.
- Mobile cell: a vehicle-deployed or temporary patrol setup for seasonal
  high-risk windows. This can support multiple nearby properties before a
  permanent dock is justified.
- Docked cell: later premium configuration when the buyer needs repeated
  remote launches and the economics justify dock, power, connectivity,
  maintenance, and regulatory overhead.

Fixed sensors can become integrations later, but they are not required
for the Patrol Cell MVP and should not drive the first architecture.

## Non-Claims

SWARM Patrol Cell does not initially claim:

- 24/7 continuous detection without enough drones, docks, power, and
  regulatory clearance;
- replacement of firefighters, first responders, or licensed operators;
- guaranteed detection of every ignition, intrusion or incident at the
  moment it starts;
- proprietary drone hardware;
- a fixed sensor network owned or installed by SWARM.

The honest claim is narrower: SWARM reduces uncertainty by using mobile
drones to keep priority land recently observed, verify suspicious cues
across supported event classes, and produce evidence fast enough for a
supervised response.
