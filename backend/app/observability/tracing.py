"""Phase 6.D — optional OpenTelemetry tracing.

Activated only when ``SWARM_OTLP_ENDPOINT`` is set. If the env var is
absent or empty, every function here is a no-op — including ``init`` —
so the audit surface and the import time stay flat for the default
deploy.

If the env var is set but the ``[otel]`` extra was not installed, the
import will raise inside ``init`` (not at module import time) and the
caller can choose to fail closed or warn. We choose to log a warning
and skip — tracing is non-essential to operation; metrics + structured
logs are the primary telemetry pipe.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("backend.observability.tracing")


def _endpoint() -> str | None:
    raw = (os.getenv("SWARM_OTLP_ENDPOINT") or "").strip()
    return raw or None


def is_enabled() -> bool:
    return _endpoint() is not None


def init(app: Any) -> bool:
    """Initialise tracing if ``SWARM_OTLP_ENDPOINT`` is set.

    Returns True when tracing was wired, False otherwise. The function
    never raises; a missing ``[otel]`` extra is logged and ignored.
    """

    endpoint = _endpoint()
    if endpoint is None:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:  # pragma: no cover — exercised via the otel extra
        logger.warning(
            "SWARM_OTLP_ENDPOINT set but opentelemetry extra missing: %s", exc
        )
        return False

    resource = Resource.create({
        "service.name": os.getenv("SWARM_OTLP_SERVICE_NAME", "swarmos-backend"),
        "service.version": "0.1.0",
        "deployment.environment": os.getenv("SWARM_ENV", "dev"),
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info("opentelemetry tracing initialised", extra={"otlp_endpoint": endpoint})
    return True


__all__ = ("init", "is_enabled")
