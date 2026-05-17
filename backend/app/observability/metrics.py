"""Phase 6.D — Prometheus metrics.

The metrics live in a private ``CollectorRegistry`` (not the global one)
so the test suite can build / reset metrics per test without leaking
counters between cases and so a misconfigured deploy can't silently
re-register a collector at startup.

Exposed shape mirrors the roadmap §6.D bullets:

  - ``swarm_units_online``                 Gauge
  - ``swarm_anomalies_pending``            Gauge
  - ``swarm_actions_total{action,outcome}`` Counter
  - ``swarm_ws_clients``                   Gauge
  - ``swarm_mission_duration_seconds``     Histogram
  - ``swarm_http_request_duration_seconds`` Histogram (route + method + code)

The ``MetricsRegistry`` is intentionally a thin container: the HTTP
middleware, action endpoint, and WS hub call helpers on it rather than
talking to ``prometheus_client`` directly. That gives a single place to
add labels later without touching the call sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import CONTENT_TYPE_LATEST

# Histogram buckets in seconds. Bound on the upper end at the request
# timeout (30 s) so anything that hits the ceiling lands in the +Inf
# overflow bucket — those are the requests the timeout middleware
# eventually 504s.
_HTTP_BUCKETS: Final[tuple[float, ...]] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0,
)
# Mission durations are minute-scale; the buckets stretch out accordingly.
_MISSION_BUCKETS: Final[tuple[float, ...]] = (
    10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0,
)


@dataclass
class MetricsRegistry:
    """A bundle of Prometheus collectors bound to a single registry.

    Keeping this in a dataclass (rather than module-level globals) means
    tests can instantiate a fresh one per case and the production app
    builds exactly one at startup.
    """

    registry: CollectorRegistry
    units_online: Gauge
    anomalies_pending: Gauge
    actions_total: Counter
    ws_clients: Gauge
    mission_duration_seconds: Histogram
    http_request_duration_seconds: Histogram
    auth_failures_total: Counter

    @classmethod
    def build(cls) -> MetricsRegistry:
        registry = CollectorRegistry()
        return cls(
            registry=registry,
            units_online=Gauge(
                "swarm_units_online",
                "Number of fleet units currently reporting telemetry.",
                registry=registry,
            ),
            anomalies_pending=Gauge(
                "swarm_anomalies_pending",
                "Anomalies awaiting verification or dismissal.",
                registry=registry,
            ),
            actions_total=Counter(
                "swarm_actions_total",
                "Operator action dispatches, labelled by action and outcome.",
                labelnames=("action", "outcome"),
                registry=registry,
            ),
            ws_clients=Gauge(
                "swarm_ws_clients",
                "WebSocket clients currently subscribed to the broadcast hub.",
                registry=registry,
            ),
            mission_duration_seconds=Histogram(
                "swarm_mission_duration_seconds",
                "End-to-end mission duration in seconds.",
                buckets=_MISSION_BUCKETS,
                registry=registry,
            ),
            http_request_duration_seconds=Histogram(
                "swarm_http_request_duration_seconds",
                "HTTP request latency in seconds, by route + method + status.",
                labelnames=("route", "method", "status"),
                buckets=_HTTP_BUCKETS,
                registry=registry,
            ),
            auth_failures_total=Counter(
                "swarm_auth_failures_total",
                "Authentication / authorization failures by reason.",
                labelnames=("reason",),
                registry=registry,
            ),
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)


# ── Module-level singleton ────────────────────────────────────────────────────
#
# Built exactly once at import time. If the build raises (collector name
# collision is the only realistic case), the import fails — that's the
# fail-fast the task asked for ("niente try/except: pass per swallow-are
# errori di metrica — se Prometheus client fallisce a startup, è un
# errore di config, deve farlo notare").

_METRICS: MetricsRegistry = MetricsRegistry.build()


def get_metrics() -> MetricsRegistry:
    return _METRICS


def reset_for_tests() -> MetricsRegistry:
    """Drop and rebuild the singleton — tests only."""
    global _METRICS
    _METRICS = MetricsRegistry.build()
    return _METRICS


__all__ = (
    "CONTENT_TYPE_LATEST",
    "MetricsRegistry",
    "get_metrics",
    "reset_for_tests",
)
