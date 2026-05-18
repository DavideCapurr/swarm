# Phase 6.F — Load + scale tests

Two layers, one source of truth for the SLO thresholds.

## In-process smoke (`pytest -m load_smoke`)

`tests/load/test_load_inproc.py` drives the real `BusConsumer` +
`InMemoryBus` + a real `WSHub` from inside the test process. A
`RecorderWS` fake captures each broadcast with a `time.monotonic()`
timestamp; the test pairs publishes to receipts and computes p95.

Runs on every push as part of CI (the `load-smoke` job in
`.github/workflows/test.yml`). Thresholds:

| Sample                          | Target                              |
| ------------------------------- | ----------------------------------- |
| WS frame p95 (`unit`)           | < 200 ms                            |
| REST p95 (`/awareness`, `/units`, `/anomalies`) | < 100 ms |
| 200-unit burst                  | no exception; rate-limiter drops > 0 |

Local invocation:

```bash
make load-smoke
```

## Out-of-process soak (`python -m tests.load.driver`)

`tests/load/driver.py` hits a *live* backend over REST + WS and a *live*
Redis with telemetry publishes. Used by `make load-soak` (500 msg/s × 5
min) and by `.github/workflows/load-test.yml` (Monday 04:17 UTC).

Auth: the driver `POST /auth/login` with credentials from
`SWARM_LOAD_USER` / `SWARM_LOAD_PASSWORD` (defaults `op-operator01` /
`swarm-dev` — `make bootstrap-auth-dev` provisions them).

Output: `tests/load/results/last.json` carries p50/p95/p99 for WS and
REST plus publish/receipt counts and any REST 5xx tally. Exit code is
non-zero on any SLO breach so the weekly job fails loudly.

Local invocation (requires `make infra && make backend`):

```bash
make load-soak                                 # 500 msg/s × 5 min
python -m tests.load.driver --rate 200 --duration 30   # quick custom run
```

## Reading the results

```jsonc
{
  "publishes": 150000,
  "received_ws_frames": 600000,
  "ws_samples": 149800,
  "ws_p50_ms": 8.4,
  "ws_p95_ms": 38.2,
  "ws_p99_ms": 71.5,
  "rest_samples": 4800,
  "rest_p50_ms": 6.1,
  "rest_p95_ms": 22.9,
  "rest_errors": 0,
  "ws_p95_target_ms": 200,
  "rest_p95_target_ms": 100
}
```

`*_p95_ms > *_p95_target_ms` is the failure signal. The matching alert
rule (panels in `infra/grafana/dashboards/swarmos-overview.json`) fires
the same threshold off the live `swarm_http_request_duration_seconds`
histogram.

See `docs/ops/performance.md` for the full SLO table and how the
threshold relates to the existing histogram buckets in
`backend/app/observability/metrics.py`.
