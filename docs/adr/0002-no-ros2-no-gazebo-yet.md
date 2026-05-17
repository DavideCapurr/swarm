# ADR 0002 — No ROS2 / no Gazebo yet (and maybe never for SWARM OS itself)

**Status**: Accepted
**Date**: 2026-05-13

## Context

The strategy PDFs recommend ROS2 and Gazebo as foundational technologies. In a
focused workshop with the founder we clarified the actual scope:

- SWARM OS is the **mission + fleet layer** — orchestration, anomaly response,
  cross-vendor coordination, dashboards.
- The **flight layer** (PID, attitude, waypoint following, RTL, obstacle
  avoidance) is owned by the vendor autopilot — DJI's flight controller, PX4,
  Skydio's stack, etc.

ROS2 is middleware used inside *flight stacks* on proprietary autonomous robots.
Gazebo is a physics simulator used to test flight stacks.

If the priority is interoperating with drones **already on the market**
(DJI, Autel, Parrot, Skydio, custom MAVLink), the right interfaces are vendor
  SDKs and protocols — **DJI Cloud API (REST + MQTT)**, **MAVLink** (direct
  protocol/runtime choice in Phase 5, no `mavros` required), **Parrot Olympe**, etc. None of those
require ROS2.

## Decision

- **ROS2 is deferred**, not adopted, in commit 1 and the foreseeable Phase 0–2.
- **Gazebo is deferred**. The Python 2D sim is the placeholder. Phase 0
  graduation moves to Gazebo + PX4 SITL if we want realistic flight dynamics
  for sensor-fusion development.
- **MAVLink is adopted directly** — covers a huge slice of the non-DJI market
  without dragging in ROS2. The concrete Python runtime is selected in Phase 5
  after security audit, rather than installing a vulnerable SDK in Phase 0.
- **ROS2 becomes relevant only when proprietary drones come into scope**
  (Phase 5+). At that point, the same Mission DSL primitives map to ROS2 topics
  via a new adapter or transport bridge.

## Consequences

- Drastically lower onboarding cost — no ROS2 install (5+ GB), no `colcon`
  build pipeline, no DDS networking.
- Faster iteration cycles on the actual product (coordination, allocation, UI).
- We do NOT lose portability: the `DroneAdapter` interface and the Mission DSL
  are deliberately at a level all vendor autopilots can satisfy.
- If we later decide to publish a "SWARM ROS2 bridge" for proprietary builds,
  it is a new adapter, not a re-architecture.

## Alternatives considered

- **ROS2 + Gazebo from day 1** — rejected: heavy dependency footprint and slow
  iteration for a product whose value is *above* the autopilot layer.
- **MAVLink via `mavros` inside ROS2** — rejected: pulls all of ROS2 in before
  the product layer needs it.
