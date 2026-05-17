"""Stream descriptors for adapter-provided live feeds.

Phase 5 introduces a typed `StreamDescriptor` so the Console can render a real
`<video>` element when an adapter exposes an RTSP / HLS stream, and fall back to
the honest `VIEWPORT PENDING / STREAM OFFLINE` placeholder otherwise.

Design constraints (PDF §5.2 + threat-model §S6, "A10 SSRF"):
- URL **must** carry an allowlisted scheme — only `rtsps://` and `https://`. We
  reject `http://`, `file://`, `javascript:`, `data:`, etc.
- Mixed-content downgrades (HTTPS dashboard → HTTP stream) are rejected at the
  type level rather than relying on the browser to enforce it.
- The descriptor is strict-mode: extra keys cannot be smuggled past validation.
- When `available=False` the URL must be `None` — a descriptor cannot
  simultaneously claim "no stream" and carry a URL.

The Console double-checks the same allowlist on the client side as a defense
in depth measure — but the server is the source of truth.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swarm_core.messages import _now

# ── Allowlist ──────────────────────────────────────────────────────────────────

#: The only URL schemes a `StreamDescriptor` may carry. Anything else is
#: rejected by `validate_stream_url`. Both schemes are TLS-bearing; we
#: deliberately exclude `rtsp://` (plaintext) and `rtmp://` (plaintext).
ALLOWED_STREAM_SCHEMES: frozenset[str] = frozenset({"rtsps", "https"})

#: Codec hints we accept. The adapter is free to leave the codec as `None` if
#: it does not know — the Console then falls back to media-type negotiation.
ALLOWED_CODECS: frozenset[str] = frozenset({"h264", "h265", "av1", "mjpeg"})


class InvalidStreamURL(ValueError):
    """Raised when a stream URL is missing, malformed, or not allowlisted."""


def validate_stream_url(url: str) -> str:
    """Return the URL if it is syntactically valid and uses an allowed scheme.

    Centralized here so both the adapter side (publishing a descriptor on the
    bus) and the backend WS side (re-validating before broadcast) share a
    single canonical implementation. The Console mirrors the same check.
    """

    if not isinstance(url, str) or not url:
        raise InvalidStreamURL("empty stream url")
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_STREAM_SCHEMES:
        raise InvalidStreamURL(
            f"stream url scheme not allowed: {scheme!r} "
            f"(allowed: {sorted(ALLOWED_STREAM_SCHEMES)})"
        )
    if not parsed.netloc:
        raise InvalidStreamURL(f"stream url missing host: {url!r}")
    # Reject CRLF / NUL injection in URLs (a header-splitting vector).
    if any(ch in url for ch in ("\r", "\n", "\x00")):
        raise InvalidStreamURL("stream url contains control characters")
    return url


# ── Model ──────────────────────────────────────────────────────────────────────


class StreamDescriptor(BaseModel):
    """Where the operator can pick up live video for a given agent.

    The adapter publishes one of these per agent on each fleet tick. When
    `available=True` the URL must be an `rtsps://` or `https://` stream the
    operator's browser can subscribe to. When `available=False` the Console
    renders the honest viewport placard ("UNIT NNN VIEWPORT PENDING / STREAM
    OFFLINE") — never a stock clip.
    """

    model_config = ConfigDict(extra="forbid", strict=False, frozen=False)

    agent_id: str = Field(..., min_length=1, max_length=64)
    available: bool = False
    url: str | None = None
    protocol: Literal["rtsps", "https"] | None = None
    codec: str | None = None
    ts: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _check_url_and_protocol(self) -> StreamDescriptor:
        if self.available:
            if not self.url:
                raise InvalidStreamURL("available=True requires a url")
            validate_stream_url(self.url)
            parsed_scheme = urlparse(self.url).scheme.lower()
            if self.protocol is not None and self.protocol != parsed_scheme:
                raise InvalidStreamURL(
                    f"protocol {self.protocol!r} disagrees with url scheme "
                    f"{parsed_scheme!r}"
                )
        else:
            if self.url is not None:
                raise InvalidStreamURL("available=False forbids a url")
            if self.protocol is not None:
                raise InvalidStreamURL("available=False forbids a protocol")
        if self.codec is not None and self.codec.lower() not in ALLOWED_CODECS:
            raise InvalidStreamURL(
                f"codec {self.codec!r} not allowed (allowed: {sorted(ALLOWED_CODECS)})"
            )
        return self

    @classmethod
    def offline(cls, agent_id: str) -> StreamDescriptor:
        """Convenience for the common "no stream" case."""
        return cls(agent_id=agent_id, available=False)


__all__ = (
    "ALLOWED_CODECS",
    "ALLOWED_STREAM_SCHEMES",
    "InvalidStreamURL",
    "StreamDescriptor",
    "validate_stream_url",
)
