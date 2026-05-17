"""Phase 6.D — observability stack.

Public surface, imported as ``from backend.app.observability import …``:

  - ``configure_logging()`` — structlog + stdlib JSON formatter (call
    once at process boot).
  - ``get_logger(name)`` — return a structlog-bound logger.
  - ``get_metrics()`` — Prometheus registry singleton.

The route and middleware modules are *not* re-exported here on purpose:
they import from ``backend.app.auth.deps`` (for the commander
gate on ``/metrics``), and auth submodules in turn import
``get_logger`` from this package. Re-exporting routes would create an
import cycle. ``main.py`` imports ``backend.app.observability.routes``
and ``backend.app.observability.middleware`` directly instead.
"""

from __future__ import annotations

from backend.app.observability.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from backend.app.observability.metrics import (
    CONTENT_TYPE_LATEST,
    MetricsRegistry,
    get_metrics,
    reset_for_tests,
)

__all__ = (
    "CONTENT_TYPE_LATEST",
    "MetricsRegistry",
    "bind_request_context",
    "clear_request_context",
    "configure_logging",
    "get_logger",
    "get_metrics",
    "reset_for_tests",
)
