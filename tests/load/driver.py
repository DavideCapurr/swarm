"""Out-of-process load driver for Phase 6.F soak runs.

Usage::

    python -m tests.load.driver \\
        --rate 500 --duration 300 \\
        --backend http://localhost:8765 \\
        --ws ws://localhost:8765/ws/telemetry \\
        --redis redis://localhost:6379/0

Auth: the driver POSTs to ``/auth/login`` with credentials read from
``SWARM_LOAD_USER`` / ``SWARM_LOAD_PASSWORD`` (defaults
``op-operator01`` / ``swarm-dev`` — what ``make bootstrap-auth-dev``
provisions) and uses the access token for REST + WS. The operator must
exist server-side; the driver fails closed on 4xx login.

Telemetry publish goes over Redis directly because the backend has no
"publish telemetry" REST verb — that surface only exists for adapters.
The driver re-creates a real adapter publish path: ``redis.asyncio``
``publish("swarm:telemetry:<aid>", json)`` at the configured rate, with
``--agents`` distinct agent ids so the per-agent
``TelemetryRateLimiter`` never trips on legitimate soak traffic.

Threshold gates (Phase 6.F SLO):
  - WS broadcast latency p95 < 200 ms
  - REST latency p95 < 100 ms

Exit code is non-zero on any breach. The full sample distribution
(p50/p95/p99 + counts) is written to ``tests/load/results/last.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import websockets

# Default REST endpoints exercised by the poller. Keep this list aligned
# with the Phase 6.F gate in ``docs/plan/archive/phase-6f.md`` so the SLO is
# evaluated against the same surfaces the Console reads.
DEFAULT_REST_PATHS = ("/awareness", "/units", "/anomalies", "/missions")

# Latency thresholds in seconds. Mirror the plan's "threshold di pass
# numerici" — a breach exits non-zero so CI can fail the soak job.
WS_P95_TARGET_S = 0.200
REST_P95_TARGET_S = 0.100


@dataclass
class DriverConfig:
    backend: str
    ws_url: str
    redis_url: str
    rate: int            # aggregate publishes per second across all agents
    duration_s: float
    agents: int
    ws_clients: int
    rest_concurrency: int
    user: str
    password: str
    totp: str | None
    results_path: Path


@dataclass
class Results:
    ws_latencies_s: list[float] = field(default_factory=list)
    rest_latencies_s: list[float] = field(default_factory=list)
    rest_errors: int = 0
    publishes: int = 0
    received: int = 0


# ── Auth ─────────────────────────────────────────────────────────────────────


async def _login(cfg: DriverConfig, client: httpx.AsyncClient) -> str:
    """POST /auth/login → access token. Fail closed on any 4xx."""

    body: dict[str, str] = {
        "operator_id": cfg.user,
        "password": cfg.password,
    }
    if cfg.totp:
        body["totp"] = cfg.totp
    r = await client.post(f"{cfg.backend}/auth/login", json=body, timeout=10.0)
    if r.status_code != 200:
        raise SystemExit(
            f"login failed: HTTP {r.status_code} {r.text[:200]}"
        )
    token = r.json().get("access_token")
    if not token:
        raise SystemExit(f"login response missing access_token: {r.json()}")
    return str(token)


# ── Publishers ───────────────────────────────────────────────────────────────


async def _publisher(
    cfg: DriverConfig,
    started_at: float,
    results: Results,
    stop: asyncio.Event,
) -> None:
    """Publish telemetry to Redis at ``cfg.rate`` aggregate Hz.

    Each tick distributes ``cfg.rate / cfg.agents`` publishes among the
    agent ids. Latency is *not* measured here — the WS listener records
    the receipt timestamps and matches against the in-band ``ts`` field.
    """

    from redis.asyncio import from_url  # local import keeps the module light

    redis = from_url(cfg.redis_url, decode_responses=True)
    try:
        await redis.ping()
        period = 1.0 / cfg.rate
        agent_ids = [f"loadgen-{i:03d}" for i in range(cfg.agents)]
        tick = 0
        next_wake = time.monotonic()
        while not stop.is_set():
            aid = agent_ids[tick % cfg.agents]
            ts_pub = time.monotonic()
            payload = json.dumps(
                {
                    "agent_id": aid,
                    "ts": _utcnow(),
                    "geo": {"lat": 44.7000, "lon": 8.0300, "alt_m": 12.0},
                    "attitude": {"roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 0.0},
                    "velocity_mps": 0.0,
                    "battery_pct": 88.0,
                    "link_quality": 0.95,
                    # Driver-only field: not part of Telemetry but Pydantic
                    # ignores unknown keys → safe to round-trip.
                    "__loadgen_ts_mono__": ts_pub,
                }
            )
            await redis.publish(f"swarm:telemetry:{aid}", payload)
            results.publishes += 1
            tick += 1
            next_wake += period
            slack = next_wake - time.monotonic()
            if slack > 0:
                await asyncio.sleep(slack)
            else:
                # Behind schedule — yield once so we don't starve the loop.
                await asyncio.sleep(0)
            if time.monotonic() - started_at >= cfg.duration_s:
                stop.set()
    finally:
        await redis.aclose()


def _utcnow() -> str:
    # ISO-8601 with 'Z' suffix matches the Pydantic datetime serializer.
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ── WS listener ──────────────────────────────────────────────────────────────


async def _ws_listener(
    cfg: DriverConfig,
    token: str,
    results: Results,
    stop: asyncio.Event,
) -> None:
    """One WS subscriber. Records receipt-to-publish latency per unit frame.

    Matches by ``__loadgen_ts_mono__`` if the projection happened to
    pass it through (it doesn't — Pydantic strips unknown fields), so
    instead we measure WS frame inter-arrival under sustained publish:
    the time from the most recent publish for an agent to the first
    ``unit`` frame for the same agent. The publisher records its
    monotonic timestamp in a per-agent shared map below.
    """

    url = f"{cfg.ws_url}?token={token}"
    try:
        async with websockets.connect(url, max_size=2**20) as ws:
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except TimeoutError:
                    continue
                results.received += 1
                # The first frames are the snapshot — no publish to match.
                # We use the in-band ``ts`` from the telemetry projection
                # (Pydantic preserves it as the unit's ``ts``).
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("kind") != "unit":
                    continue
                ts_iso = (msg.get("data") or {}).get("ts")
                if not ts_iso:
                    continue
                # Compare wall-clock ts (publisher ISO ts vs now) for the
                # ws-frame latency sample. Both ends rely on NTP-disciplined
                # clocks; the in-process tests are the authoritative source
                # for sub-50ms regression catching.
                from datetime import datetime

                ts_iso_clean = ts_iso.replace("Z", "+00:00")
                try:
                    ts_pub = datetime.fromisoformat(ts_iso_clean).timestamp()
                except ValueError:
                    continue
                now = time.time()
                latency = now - ts_pub
                if 0.0 <= latency < 10.0:  # ignore clock-skew artefacts
                    results.ws_latencies_s.append(latency)
    except Exception as exc:
        print(f"[driver] ws listener error: {exc}", file=sys.stderr)


# ── REST poller ──────────────────────────────────────────────────────────────


async def _rest_poller(
    cfg: DriverConfig,
    token: str,
    client: httpx.AsyncClient,
    results: Results,
    stop: asyncio.Event,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    paths = DEFAULT_REST_PATHS
    idx = 0
    while not stop.is_set():
        path = paths[idx % len(paths)]
        idx += 1
        t0 = time.monotonic()
        try:
            r = await client.get(f"{cfg.backend}{path}", headers=headers, timeout=5.0)
            elapsed = time.monotonic() - t0
            if r.status_code >= 500:
                results.rest_errors += 1
            else:
                results.rest_latencies_s.append(elapsed)
        except httpx.HTTPError:
            results.rest_errors += 1
        # No sleep — REST concurrency is bounded by ``rest_concurrency`` tasks.


# ── Orchestration ────────────────────────────────────────────────────────────


async def run(cfg: DriverConfig) -> Results:
    started = time.monotonic()
    results = Results()
    stop = asyncio.Event()

    async with httpx.AsyncClient(http2=False) as client:
        token = await _login(cfg, client)
        tasks: list[asyncio.Task[None]] = []
        tasks.append(asyncio.create_task(_publisher(cfg, started, results, stop)))
        for _ in range(cfg.ws_clients):
            tasks.append(asyncio.create_task(_ws_listener(cfg, token, results, stop)))
        for _ in range(cfg.rest_concurrency):
            tasks.append(asyncio.create_task(_rest_poller(cfg, token, client, results, stop)))
        try:
            await asyncio.sleep(cfg.duration_s)
        finally:
            stop.set()
            for t in tasks:
                t.cancel()
            for t in tasks:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
    return results


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return float("inf")
    s = sorted(samples)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _summary(results: Results) -> dict[str, object]:
    ws = results.ws_latencies_s
    rest = results.rest_latencies_s
    return {
        "publishes": results.publishes,
        "received_ws_frames": results.received,
        "ws_samples": len(ws),
        "ws_p50_ms": round(_percentile(ws, 50) * 1000.0, 2),
        "ws_p95_ms": round(_percentile(ws, 95) * 1000.0, 2),
        "ws_p99_ms": round(_percentile(ws, 99) * 1000.0, 2),
        "ws_mean_ms": round((statistics.mean(ws) if ws else float("inf")) * 1000.0, 2),
        "rest_samples": len(rest),
        "rest_p50_ms": round(_percentile(rest, 50) * 1000.0, 2),
        "rest_p95_ms": round(_percentile(rest, 95) * 1000.0, 2),
        "rest_p99_ms": round(_percentile(rest, 99) * 1000.0, 2),
        "rest_errors": results.rest_errors,
        "ws_p95_target_ms": int(WS_P95_TARGET_S * 1000),
        "rest_p95_target_ms": int(REST_P95_TARGET_S * 1000),
    }


def _check_breach(summary: dict[str, object]) -> list[str]:
    out: list[str] = []
    ws_p95 = summary["ws_p95_ms"]
    rest_p95 = summary["rest_p95_ms"]
    if isinstance(ws_p95, (int, float)) and ws_p95 > WS_P95_TARGET_S * 1000:
        out.append(f"WS p95 {ws_p95} ms > {int(WS_P95_TARGET_S * 1000)} ms")
    if isinstance(rest_p95, (int, float)) and rest_p95 > REST_P95_TARGET_S * 1000:
        out.append(f"REST p95 {rest_p95} ms > {int(REST_P95_TARGET_S * 1000)} ms")
    rest_errors = summary["rest_errors"]
    if isinstance(rest_errors, int) and rest_errors > 0:
        out.append(f"REST 5xx errors observed: {rest_errors}")
    return out


def _build_config(argv: list[str] | None = None) -> DriverConfig:
    p = argparse.ArgumentParser(description="SwarmOS Phase 6.F load driver")
    p.add_argument("--backend", default=os.getenv("SWARM_LOAD_BACKEND", "http://localhost:8765"))
    p.add_argument("--ws", dest="ws_url", default=os.getenv("SWARM_LOAD_WS", "ws://localhost:8765/ws/telemetry"))
    p.add_argument("--redis", default=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    p.add_argument("--rate", type=int, default=500, help="aggregate publishes/sec")
    p.add_argument("--duration", type=float, default=300.0, help="seconds")
    p.add_argument("--agents", type=int, default=50)
    p.add_argument("--ws-clients", type=int, default=4)
    p.add_argument("--rest-concurrency", type=int, default=8)
    p.add_argument("--user", default=os.getenv("SWARM_LOAD_USER", "op-operator01"))
    p.add_argument("--password", default=os.getenv("SWARM_LOAD_PASSWORD", "swarm-dev"))
    p.add_argument("--totp", default=os.getenv("SWARM_LOAD_TOTP"))
    p.add_argument(
        "--results",
        default="tests/load/results/last.json",
        help="path to write the JSON summary",
    )
    args = p.parse_args(argv)
    return DriverConfig(
        backend=args.backend.rstrip("/"),
        ws_url=args.ws_url,
        redis_url=args.redis,
        rate=args.rate,
        duration_s=args.duration,
        agents=args.agents,
        ws_clients=args.ws_clients,
        rest_concurrency=args.rest_concurrency,
        user=args.user,
        password=args.password,
        totp=args.totp,
        results_path=Path(args.results),
    )


def main(argv: list[str] | None = None) -> int:
    cfg = _build_config(argv)
    results = asyncio.run(run(cfg))
    summary = _summary(results)
    cfg.results_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.results_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))
    breaches = _check_breach(summary)
    if breaches:
        print("[driver] SLO breach:", file=sys.stderr)
        for b in breaches:
            print(f"  - {b}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
