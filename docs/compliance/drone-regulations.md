# Drone Regulations Reference (Phase 6.I)

> **SwarmOS is software. It does not decide whether a flight is legal
> in a given jurisdiction.** The Operator is responsible for every
> regulatory obligation that applies to the flight of an unmanned
> aircraft at the Operator's site. This document is a reference, not a
> compliance certification.

For the data-protection counterpart of this document see
[`gdpr.md`](gdpr.md). For the runtime controls that SwarmOS does
enforce (geofence, battery / link / weather thresholds), see
[`docs/architecture/overview.md`](../architecture/overview.md).

## 1. Responsibility split

| Aspect                                  | Responsibility       |
|-----------------------------------------|----------------------|
| Aircraft registration                   | Operator             |
| Operator certificate / remote-pilot certificate | Operator     |
| Insurance                               | Operator             |
| Airspace authorisation (controlled, U-space, NOTAM compliance) | Operator |
| Pre-flight risk assessment (SORA / equivalent) | Operator      |
| Geofence enforcement at runtime         | SwarmOS              |
| Battery / link / weather lock at runtime | SwarmOS             |
| Auto-RTL on degraded state              | SwarmOS              |
| Audit log of every operator intent      | SwarmOS              |
| NOTAM / NFZ feed ingestion              | SwarmOS hook ready, real feed drone-day |
| Camera-payload data minimisation        | Operator's site policy (drone-day when payload arrives) |

## 2. Jurisdictional reference (informational)

| Region    | Authority          | Key framework                                              | Notes |
|-----------|--------------------|------------------------------------------------------------|-------|
| EU + EEA  | EASA               | Reg. (EU) 2019/947 + 2019/945 — Open / Specific / Certified categories, U-space (Reg. (EU) 2021/664) | The Open category is the default for most light commercial flights; the Specific category requires a SORA-based authorisation; the Certified category is reserved for high-risk operations. |
| UK        | CAA                | CAP 722, CAP 2553 (UK regulatory framework)                | Mirrors the EASA structure with UK-specific identifiers (Operator ID, Flyer ID, GVC). |
| USA       | FAA                | 14 CFR Part 107 + Remote ID (Part 89)                      | Part 107 covers small UAS commercial operations; Remote ID is mandatory since 2024. |
| Switzerland | FOCA             | FOCA Drone Ordinance (aligned with EASA)                   | Aligned with EU framework. |
| Other     | National authority | National framework                                         | The Operator must confirm the applicable framework before flight. |

**This table is informational only.** Regulations evolve frequently;
the Operator is responsible for confirming the current text and any
local amendments before flying.

## 3. What SwarmOS enforces at runtime

### 3.1 Geofence

* Source: `infra/config/sites/<site_id>.yaml` — `geofence_polygon` (list
  of `[lat, lon]` pairs forming a closed polygon).
* Enforcement point: `swarm_os/policy.py::PolicyEngine.evaluate`
  (side-effect-free). Called by:
  * `swarm_os/scheduler.py` before auto-spawning a `PATROL` mission.
  * `swarm_os/command_bus.py` before accepting a `VERIFY` / `RETURN`
    operator intent.
  * `swarm_os/coordinator.py` when refreshing the auto-RTL queue.
* Rejection: `PolicyDecision(action=SafetyAction.REJECT,
  reason='geofence_violation')`. The operator sees the rejection in
  the timeline as an audit event with `rejected_reason='geofence'`.

### 3.2 Battery / link thresholds

* Source: `infra/config/sites/<site_id>.yaml` — `battery_floor_pct`,
  `link_floor`. Defaults in `swarm_os/safety.py`.
* Enforcement: `PolicyEngine.evaluate` rejects new missions when a
  unit's battery or link is below the floor; `coordinator.py` queues
  an auto-RTL `RTL_DOCK` for any airborne unit that crosses the floor
  during a mission.

### 3.3 Weather lock

* Source: `WeatherProvider` Protocol injected at boot. The default is
  `LocalStubWeatherProvider` (returns `wind_mps=0`); production
  providers (OpenWeather, Aviationweather) are wired on drone-day
  per [`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md)
  §2.A.
* Enforcement: when `wind_mps` is above the dock's `weather_lock_mps`
  threshold, the dock's `weather_lock` field is set to `True` and
  every mission departing from that dock is rejected with
  `rejected_reason='weather_lock'`.

### 3.4 NOTAM / NFZ — hook only

The runtime hook is in place but the feed is not wired by default.
The Operator must integrate the relevant national NOTAM service before
flight in any jurisdiction where NOTAM compliance is mandatory.
Catalogued in `drone-day-checklist.md` §2.A.

## 4. Pre-flight / post-flight log expectations

SwarmOS's audit log (`events` table, `operator_commands` table) covers
the in-flight intents and the safety decisions taken by the software.
Pre-flight and post-flight checklists are **operational artefacts**
managed by the Operator outside SwarmOS — the recommended floor is:

* **Pre-flight** (logged by the Operator's procedure, referenced from
  `/admin/export` evidence on demand):
  * Aircraft and Operator registration numbers.
  * Airspace authorisation (NOTAM filed, U-space authorisation
    received, etc.).
  * Battery state, payload check, geofence polygon confirmation
    against the published site config.
  * Weather window confirmation (live wind / visibility within
    operator thresholds).
* **In-flight** (captured automatically by SwarmOS):
  * Every `OperatorCommand` (verify / hold-patrol / return / dismiss
    / emergency-rtl-all) with timestamps and outcome.
  * Every `system` event (auto-RTL, weather lock, geofence rejection,
    site config reload, login / logout / refresh).
  * Telemetry samples per unit (30-day retention).
* **Post-flight** (logged by the Operator's procedure):
  * Aircraft state on landing, anomalies observed by the operator
    that did not trigger an automated intent.
  * Maintenance log entries.

## 5. Camera payload — site-level policy

When the camera payload is wired (drone-day), the Operator must
publish a site-level data-protection policy before ingest is enabled:

* **Purpose** — why frames are captured.
* **Lawful basis** — Art. 6 lawful basis (likely 6(1)(f) legitimate
  interest, balanced against the rights of data subjects in the
  operating area).
* **Minimisation** — frame rate, resolution, on-device blurring of
  faces / plates where possible before egress.
* **Retention** — per `retention.md`, governed by site policy.
* **Signage** — visible signage in the operating area as required by
  the local jurisdiction's data-protection law.

SwarmOS's role is to enforce the retention numbers configured in the
site policy and to expose the video frames only on authenticated
endpoints. The lawful-basis assessment is the Operator's.

## 6. Drone-day checklist

The regulatory items that require external assets are catalogued in
[`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md)
§2.A and §2.I:

* Aircraft and Operator registration with the relevant authority.
* Pilot certification (CAA / FAA / EASA, as applicable).
* Insurance contract.
* NOTAM / U-space integration credentials.
* Site-level camera policy (when the payload arrives).
* Signed DPA between Operator and any Processor.
