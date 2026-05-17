# Observability (Phase 6.D)

This document captures the design and runbook for the SwarmOS
observability stack: Prometheus metrics, structured JSON logs,
correlation IDs, optional OpenTelemetry tracing, and the
``/health`` / ``/ready`` probes. It complements
[`docs/security/threat-model.md`](../security/threat-model.md) (logs
under "Information disclosure") and
[`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md)
§2.D (the deployment checklist).

## 1. Model in one paragraph

The backend exposes a slim Prometheus exposition at ``/metrics``
(commander-gated by default, or IP-allowlisted for in-cluster
scrapers). Every HTTP response gets an ``X-Request-ID`` echo + log
correlation id. Logs are JSON via structlog, with a redactor
processor that scrubs sensitive keys (password, totp, jwt body,
refresh token, etc.) before the renderer ever sees them. Readiness
is an active probe of DB + Redis + auth singletons; ``/health``
remains a passive liveness check. OpenTelemetry tracing is opt-in:
set ``SWARM_OTLP_ENDPOINT`` to wire a batched OTLP exporter, leave
it unset and the path is a no-op.

## 2. Metrics

Source of truth: ``backend/app/observability/metrics.py``. All
collectors live in a single ``CollectorRegistry`` so tests can build
fresh instances per case.

| Metric                                  | Type      | Labels                  | Meaning |
|-----------------------------------------|-----------|-------------------------|---------|
| ``swarm_units_online``                  | Gauge     | —                       | Count of units in any non-OFFLINE FSM state. |
| ``swarm_anomalies_pending``             | Gauge     | —                       | Anomalies not yet verified / dismissed. |
| ``swarm_actions_total``                 | Counter   | ``action``, ``outcome`` | Operator action dispatches. ``outcome`` is ``accepted``, ``rate_limited``, or a ``RejectedReason`` value (``outside_geofence`` etc.). |
| ``swarm_ws_clients``                    | Gauge     | —                       | Live WS subscribers on the broadcast hub. |
| ``swarm_mission_duration_seconds``      | Histogram | —                       | Mission end-to-end duration in seconds. Buckets `[10, 30, 60, 120, 300, 600, 1800, 3600]`. |
| ``swarm_http_request_duration_seconds`` | Histogram | ``route``, ``method``, ``status`` | Per-route HTTP latency. ``route`` is the FastAPI template (``/missions/{mission_id}/history``), not the rendered path, so cardinality is bounded. |
| ``swarm_auth_failures_total``           | Counter   | ``reason``              | Login / refresh failures (bad password, unknown operator, bad TOTP, etc.). |

Histogram buckets for HTTP latency:
`0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0`
(upper bound matches the request-timeout middleware).

### Exposition gate

``/metrics`` requires either a JWT ``commander`` role *with* MFA
satisfied, or a client IP inside the
``SWARM_METRICS_IP_ALLOWLIST`` CIDR list (env-driven, defaults to
empty). Default posture is "JWT required". The IP path exists so a
Prometheus scraper sitting on the trusted side of the network can
skip the JWT — set ``SWARM_METRICS_IP_ALLOWLIST=10.0.0.0/8`` in the
prod overlay.

### Sample scrape config

```yaml
# Prometheus scrape config — drop this into your prom-stack values.
scrape_configs:
  - job_name: swarmos-backend
    metrics_path: /metrics
    scrape_interval: 15s
    static_configs:
      - targets: ['swarmos-backend.swarmos.svc.cluster.local:8765']
    # In-cluster scraper: backend exposes IP allowlist for the pod CIDR.
    # If running cross-cluster, add bearer_token from a service account
    # mapped to the commander role.
```

## 3. Logs

Source of truth: ``backend/app/observability/logging.py``.

- **Format**: JSON line per event. Keys: ``timestamp`` (ISO 8601
  UTC), ``level``, ``event`` (free-form message), plus structured
  kv pairs. Stdlib logs (``logging.getLogger(...).info(...)``) are
  routed through the same ``ProcessorFormatter`` so the third-party
  output (uvicorn, sqlalchemy, etc.) is JSON too.
- **Correlation id**: ``RequestIDMiddleware`` reads or mints
  ``X-Request-ID``, binds it to the structlog context with the
  request path + method, and emits it on every log line for the
  duration of the request. The response header echoes the id back.
  Validation: alphanumeric + ``_-`` only, ≤ 128 chars; anything
  else is replaced with a fresh server-side UUID hex to block log
  injection.
- **Redaction**: a structlog processor scrubs sensitive keys
  (``password``, ``totp``, ``mfa_secret``, ``refresh_token``,
  ``access_token``, ``authorization``, ``cookie``, etc. — full list
  in ``observability/logging.py``) before the renderer. It also
  strips JWT-like substrings (three base64url segments joined by
  ``.``) from free-text values and replaces ``Bearer <token>`` with
  ``Bearer <redacted>``.
- **PII**: telemetry geo coordinates are not redacted (they're
  operational truth, not PII); operator ids are kept (audit need).

### Log shipper note

Loki/Vector/Fluent Bit can scrape stdout directly. No agent-side
parsing is required — the lines are already JSON, so a simple
``json`` parser in Loki's promtail config is enough. Recommended
labels: ``service=swarmos-backend``, ``site=$SWARM_SITE_ID``,
``env=$SWARM_ENV``.

## 4. Traces (opt-in)

OpenTelemetry tracing is wired by ``init_tracing(app)`` in
``backend/app/main.py``. It is a no-op unless ``SWARM_OTLP_ENDPOINT``
is set. The ``[otel]`` extra (in ``pyproject.toml``) pulls
``opentelemetry-sdk`` + ``opentelemetry-instrumentation-fastapi``;
default installs do not include the extra, keeping the audit surface
flat for the most-common deploy.

If the env var is set but the extra wasn't installed, the init
function logs a warning and continues — tracing is non-essential.

## 5. Health endpoints

### ``/health`` (liveness, public)

Unchanged from Phase 4: returns 200 if the process is alive, plus
the in-memory state size + persistence flag. Used by Kubernetes
liveness probes.

### ``/ready`` (readiness, public, new in 6.D)

Active probe of three subsystems:

- **db** — if persistence is enabled, runs ``SELECT 1`` against the
  repository sessionmaker. Disabled persistence is treated as
  ``ok`` (demo path).
- **redis** — calls ``ping()`` on the underlying Redis client of
  the bus consumer. ``InMemoryBus`` (no ``_redis`` attribute) is
  treated as ``ok``. A pre-startup bus reports ``down``.
- **auth** — verifies the JWT service + operator store singletons
  are loaded. ``SWARM_AUTH_DISABLED=1`` short-circuits to ``ok``.

Body shape (both 200 and 503):

```json
{
  "status": "ready",
  "checks": {"db": "ok", "redis": "ok", "auth": "ok"}
}
```

Failure → 503 with ``"status": "degraded"`` and the failing
subsystem's value set to ``"down"``. **No stack traces ever appear
in the payload** — failure reasons are server-side via the logger.

## 6. Alerting

Source of truth: ``infra/grafana/alerts.yml``.

| Rule                          | Threshold                              | Severity | For   |
|-------------------------------|----------------------------------------|----------|-------|
| ``SwarmUnitsOffline``         | ``units_online`` dropped by > 1        | warning  | 5m    |
| ``SwarmAnomaliesPendingTooHigh`` | ``anomalies_pending > 5``          | warning  | 10m   |
| ``SwarmLinkHealthDegraded``   | online/online-10m < 0.5                | critical | 5m    |
| ``SwarmAuthFailureRateHigh``  | ``rate(auth_failures_total[5m]) > 0.5``| warning  | 5m    |
| ``SwarmDockWeatherLockLong``  | units stuck at zero for > 1h           | warning  | 1h    |
| ``SwarmRequestLatencyHigh``   | p95 latency > 500 ms                   | warning  | 5m    |
| ``SwarmReadinessProbeFailing``| blackbox-exporter ``probe_success==0`` | critical | 2m    |

Severity convention: only ``warning`` and ``critical``. **No red
band** (design system §5.2 — escalation is amber, never red).

## 7. Dashboards

Source of truth: ``infra/grafana/dashboards/swarmos-overview.json``.

Panel layout:

| Position    | Panel                            |
|-------------|----------------------------------|
| Row 1, cols 0–6  | Units online (stat)         |
| Row 1, cols 6–12 | Anomalies pending (stat)    |
| Row 1, cols 12–18| Link health proxy (stat)    |
| Row 1, cols 18–24| REST p95 (stat)             |
| Row 2, cols 0–12 | Operator actions / sec      |
| Row 2, cols 12–24| REST latency by route       |
| Row 3, cols 0–12 | WebSocket clients           |
| Row 3, cols 12–24| Auth failures / sec         |

Datasource is parameterised by ``${DS_PROMETHEUS}`` — provision via
``infra/grafana/datasource.yaml`` (drone-day §2.D) or pick at import
time.

## 8. Runbook

### runbook-units-offline

1. Inspect ``swarm_units_online`` and the per-unit FSM via the Console
   or ``GET /units``.
2. Cross-reference with the dock weather lock state — a sudden drop
   right after weather lock starts is normal recovery on the dock side.
3. If the link is degraded (``link_quality < 0.5``), trigger the
   radio fallback runbook (TBD in 6.E).

### runbook-anomaly-backlog

1. Check operator capacity via ``swarm_actions_total{action="verify"}``.
2. Inspect the auto-scheduler: ``GET /missions`` filtered by
   ``kind="verify"``.
3. If the scheduler is not dispatching, examine the policy engine
   logs (``backend.app.policy`` logger) for ``policy_deny``
   reasons.

### runbook-link-degraded

1. Compare ``units_online`` vs the offset by 10m — a near-zero ratio
   confirms a fleet-wide drop.
2. Check Redis health (``/ready`` ``redis`` field).
3. Check the adapter runner logs (``backend.bus`` logger) for
   sustained "telemetry over backend cap" warnings.

### runbook-auth-failures

1. Inspect ``swarm_auth_failures_total`` by ``reason`` label.
2. ``bad_password`` spike with a single operator id → likely a
   misconfigured client or a script using the wrong secret.
3. ``bad_password`` spike across many operator ids → likely a
   brute-force; raise the rate-limit floor and notify SecOps.
4. ``bad_totp`` spike → recheck NTP sync on the operator devices.

### runbook-weather-lock

1. Check the dock weather provider config in
   ``infra/config/sites/<site_id>.yaml``.
2. Inspect ``GET /docks`` for ``weather_lock=true`` rows.
3. If the lock is stale (provider hasn't refreshed), check the
   provider's last-tick timestamp in the policy logger.

### runbook-rest-latency

1. Identify the slow route via the per-route histogram panel.
2. Check DB latency (``/ready`` returns 200 but slow → look at the
   sessionmaker pool stats).
3. Check Redis pubsub backpressure (high ``swarm_ws_clients`` count
   with no new events broadcasting → suspect a slow subscriber).

### runbook-readiness

1. Curl ``/ready`` and read the ``checks`` body.
2. ``db: down`` → check ``DATABASE_URL`` env + Postgres pod health.
3. ``redis: down`` → check ``REDIS_URL`` + Redis pod health + mTLS
   cert expiry.
4. ``auth: down`` → check ``SWARM_JWT_SECRET`` + operator store path.

## 9. Drone-day items

Catalogued in
[`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md)
§2.D: Prometheus scrape config, Grafana datasource provisioning,
Loki/Vector endpoint, Alertmanager routes.

## 10. Decisions taken (and not taken)

- **OpenTelemetry**: shipped as an optional extra (``[otel]``), not
  default. The roadmap calls traces "opzionale" and we keep the
  audit surface flat by default. Activated only if
  ``SWARM_OTLP_ENDPOINT`` is set.
- **Dock weather-lock alert**: implemented as a proxy on
  ``units_online`` stagnation. A dedicated
  ``swarm_dock_weather_lock_seconds`` gauge is queued for 6.D.bis
  when the live weather provider is wired (drone-day §2.A/§2.B).
- **DB lag alert**: not in this rule set. We rely on
  ``SwarmReadinessProbeFailing`` (which catches DB unreachable) and
  the slow-query monitor on the managed Postgres service.
- **Per-route status code labels**: included because Prometheus
  rate(...) by ``status`` is the cheapest way to track 4xx/5xx
  spikes per endpoint.
