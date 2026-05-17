"""Phase 6.D — structlog JSON logging.

What this module does:

  1. Wires structlog with a JSON ``ProcessorFormatter`` so every log
     entry (including stdlib ``logging.getLogger(...).info(...)`` calls
     from third-party libs like ``uvicorn``) is emitted as a single
     JSON line.
  2. Adds a redactor processor that scrubs known-sensitive keys
     (password, totp, jwt body, refresh token, mfa secret, etc.) before
     they reach the renderer — so accidental leakage in a future log
     line is blocked at the processor chain, not just by author
     discipline.
  3. Exposes ``request_context`` for the request-id middleware to
     bind/clear context.

Why a custom redactor: the task is explicit that "structlog JSON: zero
PII nei log" and that "I redactor pattern devono essere wired nel
processor chain". A logger that re-formats a dict at the call site is
trivial to bypass; chaining the redactor as a structlog processor means
every event-dict the renderer ever sees has already been scrubbed.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any, Final

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.types import EventDict, Processor

# Keys that may carry a secret. Match is case-insensitive and substring
# (so e.g. ``refresh_token`` and ``RefreshToken`` are both caught).
_SENSITIVE_KEYS: Final[tuple[str, ...]] = (
    "password",
    "passcode",
    "totp",
    "otp_code",
    "secret",
    "mfa_secret",
    "token",
    "refresh_token",
    "access_token",
    "id_token",
    "authorization",
    "cookie",
    "x-refresh-token",
    "api_key",
    "private_key",
)

# Values that look like a JWT (three dot-separated base64url segments,
# minimum size to dodge false-positives on natural prose). Catches the
# case where someone interpolates an entire token into a free-text
# message instead of as a structured key. The replacement is the
# literal string ``"<redacted>"``.
_JWT_RE: Final[re.Pattern[str]] = re.compile(
    r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"
)
_BEARER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]+"
)


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in _SENSITIVE_KEYS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        redacted = _JWT_RE.sub("<redacted>", value)
        redacted = _BEARER_RE.sub("Bearer <redacted>", redacted)
        return redacted
    if isinstance(value, (bytes, bytearray)):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: ("<redacted>" if _is_sensitive_key(k) else _redact_value(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(v) for v in value)
    return value


def redactor(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """structlog processor: scrub sensitive keys + JWT-looking strings.

    Runs before the renderer so the JSON output never carries the raw
    secret. Both keyed values (``event_dict["password"]``) and the
    free-text ``event`` message are scrubbed.
    """

    out: EventDict = {}
    for key, value in event_dict.items():
        if _is_sensitive_key(key):
            out[key] = "<redacted>"
            continue
        out[key] = _redact_value(value)
    return out


def _log_level_from_env() -> int:
    raw = os.getenv("SWARM_LOG_LEVEL", "INFO").upper().strip()
    return getattr(logging, raw, logging.INFO)


def _shared_processors() -> list[Processor]:
    """Processors shared between structlog-native and stdlib-routed entries.

    The redactor sits at the end so prior processors (timestamper, level,
    contextvar binders) all run on the unredacted dict and only the
    renderer sees scrubbed values.
    """

    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redactor,
    ]


def configure_logging(*, force: bool = False) -> None:
    """Install the JSON formatter on stdlib + structlog.

    Idempotent — calling twice in the same process is safe so tests
    that re-import the module don't double-format. Pass ``force=True``
    to wipe handlers and reattach.
    """

    shared = _shared_processors()

    # Native structlog path: feed through the same processors and render
    # JSON. Anything that uses ``structlog.get_logger(...)`` lands here.
    structlog.configure(
        processors=[
            *shared,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_log_level_from_env()),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Stdlib path: anything that imports ``logging.getLogger(...)``
    # (uvicorn access logs, third-party libs, our own legacy modules)
    # gets routed through the same JSON renderer via
    # ``ProcessorFormatter``.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    if force or not getattr(root, "_swarm_obs_configured", False):
        for h in list(root.handlers):
            root.removeHandler(h)
        root.addHandler(handler)
        root.setLevel(_log_level_from_env())
        # Silence the noisy access logger from uvicorn (we have our own
        # request-latency histogram + structured access log via the
        # request-id middleware).
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        # Sentinel so a second import doesn't double-attach handlers.
        root._swarm_obs_configured = True  # type: ignore[attr-defined]


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger bound to ``name`` (or the caller's module).

    Typed as ``Any`` because structlog's runtime logger types depend on
    the wrapper configuration installed by ``configure_logging`` and
    aren't statically tractable without a per-call cast. Call sites use
    the standard ``.info(...)``, ``.warning(...)``, ``.exception(...)``
    methods.
    """

    return structlog.get_logger(name) if name else structlog.get_logger()


# Re-exports for the middleware ────────────────────────────────────────────────


def bind_request_context(**values: Any) -> None:
    """Bind contextvars for the lifetime of the request."""

    bind_contextvars(**values)


def clear_request_context() -> None:
    clear_contextvars()


__all__ = (
    "bind_request_context",
    "clear_request_context",
    "configure_logging",
    "get_logger",
    "redactor",
)
