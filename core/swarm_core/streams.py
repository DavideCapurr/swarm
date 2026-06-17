"""Stream descriptors for adapter-provided live feeds.

Phase 5 introduces a typed `StreamDescriptor` so the Console can render a real
`<video>` element when an adapter exposes an RTSP / HLS stream, and fall back to
the honest `VIEWPORT PENDING / STREAM OFFLINE` placeholder otherwise.

The three-month-plan CV-live video sub-step adds a third state: a **simulated**
feed. The sim has no real camera, so for the demo viewport it serves a synthetic
SIM-labeled drone-POV clip (Blender render, CC0 assets) bundled with the Console
and stamped `SIMULATED FEED` — never a stock clip (PDF §5.2). A simulated feed
carries a same-origin **relative path** (e.g. ``/sim-feed/unit-003.mp4``), not an
external URL: it is our own bundled asset, so there is no SSRF surface to guard
at all — the path can never resolve to a remote host.

Design constraints (PDF §5.2 + threat-model §S6, "A10 SSRF"):
- External (`simulated=False`) feeds: the URL **must** carry an allowlisted
  scheme — only `rtsps://` and `https://`. We reject `http://`, `file://`,
  `javascript:`, `data:`, etc.
- Mixed-content downgrades (HTTPS dashboard → HTTP stream) are rejected at the
  type level rather than relying on the browser to enforce it.
- Simulated feeds: the URL **must** be a same-origin absolute path under
  ``/sim-feed/`` — no scheme, no host, no ``..`` traversal, no control chars.
  This is *more* restrictive than the external allowlist, not less.
- The descriptor is strict-mode: extra keys cannot be smuggled past validation.
- When `available=False` the URL must be `None` — a descriptor cannot
  simultaneously claim "no stream" and carry a URL.

The Console double-checks the same allowlists on the client side as a defense
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

#: A simulated feed must point at a same-origin asset bundled with the Console
#: under this path prefix. Constraining the prefix (rather than allowing any
#: same-origin path) means a descriptor can never address an arbitrary Console
#: route — only the synthetic clips we ship.
SIM_FEED_PREFIX: str = "/sim-feed/"


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


def validate_sim_feed_path(path: str) -> str:
    """Return the path if it is a safe same-origin reference to a bundled clip.

    A simulated feed is our own asset shipped with the Console, so the safest
    thing it can carry is a relative same-origin path — never a URL with a
    scheme or host. We require:

    - a non-empty string with no control / backslash characters;
    - no scheme and no netloc (so ``https://…`` and protocol-relative
      ``//host/…`` are both rejected — `urlparse` surfaces the host as netloc);
    - the `SIM_FEED_PREFIX` so it can only address shipped clips, not an
      arbitrary Console route;
    - no ``..`` path segment (directory traversal).
    """

    if not isinstance(path, str) or not path:
        raise InvalidStreamURL("empty sim feed path")
    if any(ch in path for ch in ("\r", "\n", "\x00", "\\")):
        raise InvalidStreamURL("sim feed path contains illegal characters")
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise InvalidStreamURL(
            f"sim feed path must be a same-origin relative path, not a url: {path!r}"
        )
    if not path.startswith(SIM_FEED_PREFIX):
        raise InvalidStreamURL(
            f"sim feed path must start with {SIM_FEED_PREFIX!r}: {path!r}"
        )
    if ".." in path.split("/"):
        raise InvalidStreamURL("sim feed path must not contain '..' traversal")
    return path


# ── Model ──────────────────────────────────────────────────────────────────────


class StreamDescriptor(BaseModel):
    """Where the operator can pick up live video for a given agent.

    The adapter publishes one of these per agent on each fleet tick. There are
    three honest states:

    - `available=True, simulated=False` — a real external feed. `url` must be an
      `rtsps://` or `https://` stream the operator's browser can subscribe to.
    - `available=True, simulated=True` — a synthetic SIM-labeled clip bundled
      with the Console. `url` is a same-origin `/sim-feed/…` path; the Console
      stamps it `SIMULATED FEED`. Used by the sim demo, which has no real camera.
    - `available=False` — the Console renders the honest viewport placard
      ("UNIT NNN VIEWPORT PENDING / STREAM OFFLINE"). Never a stock clip.
    """

    model_config = ConfigDict(extra="forbid", strict=False, frozen=False)

    agent_id: str = Field(..., min_length=1, max_length=64)
    available: bool = False
    #: A simulated feed is a synthetic clip we ship, carried as a same-origin
    #: `/sim-feed/…` path and rendered with a `SIMULATED FEED` stamp. It is
    #: never an external URL, so it has no SSRF surface.
    simulated: bool = False
    url: str | None = None
    protocol: Literal["rtsps", "https"] | None = None
    codec: str | None = None
    ts: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _check_url_and_protocol(self) -> StreamDescriptor:
        if self.simulated:
            if not self.available:
                raise InvalidStreamURL("simulated=True requires available=True")
            if not self.url:
                raise InvalidStreamURL("simulated=True requires a url")
            validate_sim_feed_path(self.url)
            # A simulated clip is a same-origin file, not a network stream, so
            # the network protocol field is meaningless here.
            if self.protocol is not None:
                raise InvalidStreamURL("simulated feed forbids a network protocol")
        elif self.available:
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

    @classmethod
    def simulated_feed(
        cls, agent_id: str, path: str, *, codec: str | None = None
    ) -> StreamDescriptor:
        """Convenience for the synthetic SIM-labeled clip case.

        `path` must be a same-origin `/sim-feed/…` reference to a bundled clip.
        """
        return cls(
            agent_id=agent_id, available=True, simulated=True, url=path, codec=codec
        )


__all__ = (
    "ALLOWED_CODECS",
    "ALLOWED_STREAM_SCHEMES",
    "SIM_FEED_PREFIX",
    "InvalidStreamURL",
    "StreamDescriptor",
    "validate_sim_feed_path",
    "validate_stream_url",
)
