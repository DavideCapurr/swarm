# SWARM OS — Architecture

## System diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Operator dashboard                                │
│                 frontend/ — Next.js + TS + MapLibre + WebSocket              │
└────────────────────────────────▲─────────────────────────────────────────────┘
                                 │ REST + WebSocket
┌────────────────────────────────┴─────────────────────────────────────────────┐
│                              Backend                                         │
│           backend/ — FastAPI (REST, WS), SQLAlchemy + TimescaleDB            │
│           Exposes /fleet, /missions, /anomalies, /telemetry                  │
└────────────────────────────────▲─────────────────────────────────────────────┘
                                 │ pub/sub
┌────────────────────────────────┴─────────────────────────────────────────────┐
│                            Transport bus                                     │
│              orchestrator/swarm_orchestrator/bus.py (Redis pub/sub)          │
│              Topics: /telemetry/{id}, /anomalies, /missions/announce, ...    │
└──────▲──────────────────────────▲──────────────────────────────▲─────────────┘
       │                          │                              │
┌──────┴────────┐         ┌───────┴────────┐            ┌────────┴──────────┐
│ Orchestrator  │         │  Perception    │            │   Fleet           │
│ auction       │         │  swarm_sim/    │            │   N x DroneAdapter│
│ mission alloc │         │  perception.py │            │                   │
│ FleetState    │         │  → /anomalies  │            │                   │
└───────────────┘         └────────────────┘            └─────────┬─────────┘
                                                                  │
                                                  ┌───────────────┼───────────────┐
                                                  │               │               │
                                          ┌───────▼──────┐ ┌──────▼─────┐ ┌──────▼─────┐
                                          │ simulated/   │ │ mavlink/   │ │ dji_cloud/ │
                                          │ → sim/       │ │ → MAVSDK   │ │ → DJI Cloud│
                                          │              │ │ → PX4/SITL │ │ → DJI Dock │
                                          └──────────────┘ └────────────┘ └────────────┘
                                          ┌──────────────────────────────────────────┐
                                          │ stubs: autel/ parrot/ skydio/ dji_psdk/  │
                                          │ (typed against vendor protocols)          │
                                          └──────────────────────────────────────────┘
```

## Layering rules

1. **`core/`** has zero I/O. No network, no DB, no asyncio. Pure data + logic. This
   is what makes SWARM testable and portable.
2. **`adapters/`** depend only on `core/` and the vendor SDK. Adapters NEVER reach
   back into orchestrator or backend.
3. **`orchestrator/`** depends on `core/` and `adapters/base`. It does not import
   any vendor-specific code.
4. **`backend/`** depends on `core/` and reads from the bus. It does not import
   `adapters/`.
5. **`frontend/`** consumes only the backend's REST + WebSocket API.

Violating these layers means the layer has the wrong responsibility.

## Message contracts (canonical)

Defined in `core/swarm_core/messages.py` and `core/swarm_core/missions.py`.

| Type | Topic | Producer | Consumer |
|---|---|---|---|
| `Telemetry`     | `/telemetry/{agent_id}`        | Adapter           | Orchestrator, Backend WS |
| `FleetState`    | `/fleet/state`                 | Orchestrator      | Backend, frontend (via WS) |
| `Anomaly`       | `/anomalies`                   | Perception        | Orchestrator, Backend |
| `MissionTask`   | `/missions/announce`           | Orchestrator      | All adapters (bidding) |
| `Bid`           | `/missions/bid/{mission_id}`   | Adapter (agent)   | Orchestrator |
| `Award`         | `/missions/award`              | Orchestrator      | Winning adapter |
| `MissionProgress` | `/missions/progress/{id}`    | Adapter           | Orchestrator, Backend |

### Mission DSL

`PATROL`, `VERIFY`, `COVER`, `RELAY`, `RTL_DOCK` — see `core/swarm_core/missions.py`.

Adapters translate these into vendor dialects:

| Mission | DJI Cloud API           | MAVLink                            | Simulated |
|---|---|---|---|
| `PATROL`    | DJI Waypoint KMZ upload | sequence of `MISSION_ITEM_INT`    | scripted waypoint loop |
| `VERIFY`    | Virtual Stick + camera  | `SET_POSITION_TARGET_GLOBAL_INT`  | direct setpoint |
| `RTL_DOCK`  | Auto-return command     | `MAV_CMD_NAV_RETURN_TO_LAUNCH`    | reset to dock |
| `RELAY`     | Hold position w/ comms  | guided-mode hover                 | hold position |

## Agent FSM (`core/swarm_core/fsm.py`)

```
DOCKED ──takeoff──▶ TAKEOFF ──mission─▶ EN_ROUTE ──arrive──▶ ON_STATION
   ▲                                          │                  │
   │                                          │             capture/hover
   │                                          ▼                  │
   ├────────── DOCKING ◀── LANDING ◀── RTL ◀──┴──────────────────┘
   │                                          ▲
   └──────────── (low battery / lost link / abort) ──────────────
```

Failsafes inside the adapter (lost-link RTL, low-battery RTL, geofence RTL) are
declared in the adapter's `autopilot_failsafes` property so SWARM can reason about
what the autopilot will do without SWARM commands.

## Auction protocol (Contract Net)

1. Orchestrator publishes `MissionTask` on `/missions/announce`.
2. Each available agent publishes a `Bid` on `/missions/bid/{mission_id}`:
   `score = w_distance · 1/distance_m + w_battery · battery_pct - w_busy · is_busy`.
3. Orchestrator collects bids for `BID_WINDOW_MS` (default 500 ms), publishes
   `Award` to the winner.
4. Winner transitions FSM and publishes `MissionProgress`.
5. New higher-priority `MissionTask` can cause `divert()` on a currently-executing
   adapter.

## Persistence

PostgreSQL with TimescaleDB extension. `telemetry` is a hypertable partitioned by
`ts`. Backend exposes time-range queries. See `infra/postgres/init.sql`.

## Frontend

Operator dashboard (`frontend/app/page.tsx`) shows:
- map: territory polygon, dock, drones (with vendor badge), anomalies, trails;
- fleet grid: per-drone FSM state, battery, mission, link;
- event feed: anomaly + mission timeline.

Design tokens placeholder in `frontend/lib/tokens.ts`; final values come from
`SWARM-design-system-v1.pdf` (see `docs/design-system.md`).

## Migration paths

- **Transport** — Redis pub/sub → NATS/MQTT (edge cellular) → ROS2 DDS (only if
  proprietary drones come into scope). The `bus.py` abstraction makes this swap
  local to one module.
- **Simulation** — `sim/swarm_sim/` → Gazebo + PX4 SITL (Phase 0 graduation).
  Adapter interface unchanged.
- **Perception** — heuristic in `sim/swarm_sim/perception.py` → real CV model in
  `ml/anomaly/` → on-device inference at the edge.
