# SwarmOS performance + scale (Phase 6.F)

This doc lists the Phase 6.F SLO targets, how to verify them locally,
how CI checks them, and how the existing observability surface in
`backend/app/observability/metrics.py` maps onto the same numbers.

> Audience: SRE / on-call. Pair with
> [`deploy.md`](deploy.md) for the deploy posture and
> [`drone-day-checklist.md`](drone-day-checklist.md) for the production
> assets that gate a real customer rollout.

---

## 1. Service-level objectives

Per **site** (one SwarmOS instance):

| Surface                  | Target           | Source of truth                                                                 |
| ------------------------ | ---------------- | ------------------------------------------------------------------------------- |
| Concurrent units         | 50               | Roadmap §Phase 6.F                                                              |
| Telemetry rate (per unit)| 10 Hz            | Roadmap §Phase 5 + 6.F                                                          |
| Aggregate telemetry      | 500 msg/s        | 50 × 10 Hz                                                                      |
| WS broadcast emit p95    | **< 200 ms**     | Roadmap §Phase 6.F                                                              |
| REST p95                 | **< 100 ms**     | `/awareness`, `/units`, `/anomalies`, `/missions`                               |
| Burst tolerance          | 200 units, no 5xx| `core/swarm_core/rate_limit.py` enforces; `backend/app/bus_consumer.py:141` re-applies |
| Frontend WS reconnect    | ≤ 6 s            | `frontend/lib/ws.ts:91,112` exponential backoff (500 ms first retry, 10 s cap)  |
| Redis pause survival     | 0 crash; in-memory fallback | `backend/app/bus_consumer.py:67-91` (boot-time) |
| Multi-site               | 10 sites / instance | Roadmap §Phase 6.F (one site per process today; multiplex is Phase 7) |

The targets are **emit-side**, not end-to-end network. The
`swarm_http_request_duration_seconds` histogram in
`backend/app/observability/metrics.py` already carries buckets at
0.05, 0.1, 0.25 seconds — both SLO thresholds map onto existing
buckets, so the Grafana panel for "REST p95" reads off the live data
without a metric change.

---

## 2. Verifying locally

### 2.1 In-process smoke (≤ 15 s wall)

The smoke runs entirely in-process: a real `BusConsumer` on an
`InMemoryBus`, a real `WSHub`, and a fake WS client that timestamps
each broadcast. No infra required.

```bash
make load-smoke
# pytest tests/load -m load_smoke -q  → 3 passed in ~13 s
```

Three assertions:

- `test_p95_ws_latency` — WS p95 < 200 ms over a 50-agent × 1 Hz × 5 s
  window.
- `test_rest_p95_under_load` — same load profile; 4 concurrent REST
  pollers across `/awareness`, `/units`, `/anomalies`, `/missions`
  must keep p95 < 100 ms and 0 × 5xx.
- `test_burst_200_units_graceful` — 200 units publish above the
  `TelemetryRateLimiter` cap; `dropped_total` must advance and the
  consumer must never raise.

### 2.2 Out-of-process soak (5 min)

The soak hits a **live** backend over REST + WS and publishes
telemetry through Redis. Requires the dev stack:

```bash
make infra && make db-migrate
make bootstrap-auth-dev          # writes JWT secret + 3 dev accounts
make backend                     # leave running; uvicorn on :8765
make load-soak                   # 500 msg/s × 5 min; non-zero exit on SLO breach
```

Results land in `tests/load/results/last.json` as p50/p95/p99 (ms) for
WS and REST plus publish + receipt counts and 5xx tally. CI uploads
the same JSON as a workflow artifact.

### 2.3 Chaos drills

Both drills are manual; they're not invoked by `make test`. Run them
in a dev environment with the stack already up.

```bash
make chaos-redis                 # pause redis 8 s; /health 200 throughout
make chaos-backend               # SIGTERM uvicorn; reconnect ≤ 6 s
```

`scripts/chaos/redis_pause.sh` pauses the Redis container, polls
`/health` every 500 ms during the pause, and fails non-zero if any
poll returns non-200.

`scripts/chaos/backend_kill.sh` logs in as the dev viewer, opens a
`watch`-mode WS probe, SIGTERMs `backend.app.main`, restarts uvicorn,
and runs a `reconnect`-mode probe; it asserts `RECONNECT_MS <= 6000`.
The probe (`tests/chaos/ws_probe.py`) is a stand-alone module so it
can also be invoked from a CI step or a drone-day runbook.

---

## 3. Continuous verification

### 3.1 Every push — `.github/workflows/test.yml :: load-smoke`

A dedicated job re-runs the in-process smoke against the freshly
installed dependency set so a regression in WS / REST p95 fails the
PR alongside the existing `pytest` + `pip-audit` gates. The smoke is
in-process, so the job runs in ~30 s on a stock GitHub-hosted runner.

### 3.2 Weekly — `.github/workflows/load-test.yml`

Schedule `17 4 * * 1` (Mon 04:17 UTC, off-window from the daily
`image-scan.yml` at 03:11). Also exposed via `workflow_dispatch` so
the on-call can trigger it after a substantive change to the bus
consumer or the projection path.

The job spins Timescale + Redis as service containers (digests pinned
to match `docker-compose.yml`), boots the backend on
`127.0.0.1:8765`, waits for `/ready`, then runs the soak driver at
500 msg/s for 5 min. Artifacts (`results/last.json` + `backend.log`)
are retained for 30 days.

The driver exits non-zero on any of:

- WS p95 > 200 ms
- REST p95 > 100 ms
- 1 or more REST 5xx during the window

---

## 4. Diagnosing a breach

When CI flags an SLO breach, walk the call path bottom-up:

1. **Bus consumer** — `backend/app/bus_consumer.py:135-194`. Every
   telemetry / fleet / anomaly / mission frame is projected here.
   The `swarm_mission_duration_seconds` histogram is observed in this
   path too.
2. **Coordinator `_refresh`** — `swarm_os/coordinator.py:225-252`.
   Runs sector scoring, the scheduler, the command tick, and the
   event detector on every applied frame. If `_refresh` becomes the
   p95 contributor, the contingency described in
   `docs/plan/archive/phase-6f.md` §"Contingenti" — debouncing `_refresh` to
   50 ms — applies.
3. **Repository writes** — `backend/app/db/repository.py:96-189`.
   Per-message inserts. Plan §"Contingenti" describes the
   `RepositoryBatcher` (queue with `asyncio.Queue(maxsize=4096)`,
   drain every 100 ms via `bulk_insert_mappings`) that lands only if
   the soak proves DB writes are the bottleneck.
4. **WS fanout** — `backend/app/ws/telemetry.py:46-54`. Held under
   `WSHub._lock` while building the client list; the actual sends
   happen lock-free. If the lock becomes contended, switch the
   broadcast call to a `for ws in self._clients.copy()` snapshot
   outside the lock (in-place).
5. **Histogram surface** — `backend/app/observability/metrics.py:41-46`.
   The `swarm_http_request_duration_seconds` buckets already cover
   100 ms and 200 ms; the Grafana panel in
   `infra/grafana/dashboards/swarmos-overview.json` plots REST p95
   per route. The alert rule in `infra/grafana/alerts.yml` fires the
   same threshold off the same series — keep them aligned.

---

## 5. What Phase 6.F does **not** ship

- **DB write batching** — contingent. Only added if `make load-soak`
  proves per-message writes are the p95 bottleneck. Touch points
  catalogued in `docs/plan/archive/phase-6f.md` §"Contingenti".
- **Coordinator `_refresh` debouncing** — contingent for the same
  reason.
- **Patroni / Redis-Sentinel failover** — Phase 6.G.
- **24 h soak on prod-shape infra** — drone-day checklist.
- **Network-partition chaos via `tc netem`** — Phase 6.G.
- **New Grafana panels** for the load histograms — Phase 6.G.
  Phase 6.F only documents that the existing buckets already cover
  the SLO thresholds.
