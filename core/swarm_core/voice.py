"""Confidence-bound voice helpers.

PDF §5.2 defines the Console's wording rules: never panic language, never
"intruder detected", always confidence-bounded. This module produces those
strings server-side so the audit grep that enforces the rule has a single
file to inspect, and so the Console can render copy directly from API
responses without re-implementing the rule in TypeScript.

Bands match `ConfidenceBand` in messages.py:
  - 0.00 to 0.59 -> low-confidence
  - 0.60 to 0.84 -> elevated
  - 0.85 to 1.00 -> verified
"""

from __future__ import annotations

import re

from swarm_core.messages import (
    AnomalyView,
    ConfidenceBand,
    OperatingMode,
    Sector,
    SectorState,
)

# ── Bands ──────────────────────────────────────────────────────────────────────

LOW_THRESHOLD = 0.60
VERIFIED_THRESHOLD = 0.85


def band(confidence: float) -> ConfidenceBand:
    """Map a [0,1] confidence to its band."""
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError(f"confidence must be in [0, 1], got {confidence}")
    if confidence >= VERIFIED_THRESHOLD:
        return ConfidenceBand.VERIFIED
    if confidence >= LOW_THRESHOLD:
        return ConfidenceBand.ELEVATED
    return ConfidenceBand.LOW_CONFIDENCE


# ── Copy generators ────────────────────────────────────────────────────────────


def describe_anomaly(a: AnomalyView) -> str:
    """Return a confidence-bound human-readable description.

    Forbidden words like "Intruder", "alarm", "red-alert" must never appear in
    the output, regardless of `AnomalyKind`. Tests in `tests/test_voice.py`
    enforce this for the full Cartesian of bands x kinds.
    """
    pct = round(a.confidence * 100)
    sector_part = f" in sector {a.sector_id}" if a.sector_id else ""
    if a.band == ConfidenceBand.VERIFIED:
        return f"verified hotspot{sector_part} · confidence {pct:03d}%"
    if a.band == ConfidenceBand.ELEVATED:
        return f"elevated anomaly{sector_part} · confidence {pct:03d}%"
    return f"low-confidence anomaly{sector_part} · confidence {pct:03d}%"


def describe_sector(s: Sector) -> str:
    """Coverage-aware sector copy. No panic words."""
    confidence_pct = round(s.confidence * 100)
    if s.state == SectorState.ANOMALY:
        return f"sector {s.label} requires verification · confidence {confidence_pct:03d}%"
    if s.state == SectorState.BLIND:
        return f"sector {s.label} blind spot · awareness deferred"
    if s.state == SectorState.STALE:
        return f"sector {s.label} awareness stale · scan recommended"
    if s.state == SectorState.COVERED:
        return f"sector {s.label} covered · confidence {confidence_pct:03d}%"
    return f"sector {s.label} idle · confidence {confidence_pct:03d}%"


def describe_mode(mode: OperatingMode) -> str:
    """Long-form operating mode line for the Control surface bottom-left."""
    return {
        OperatingMode.REST: "territory under awareness · system at rest",
        OperatingMode.PATROL: "patrol in progress · coverage refreshing",
        OperatingMode.VERIFICATION: "anomaly verifying · awaiting confidence",
        OperatingMode.ESCALATION: "event verified · operator decision required",
        OperatingMode.MAINTENANCE: "unit attention required · routing adjusted",
    }[mode]


# ── Audit ──────────────────────────────────────────────────────────────────────

#: Tokens the Console / SwarmOS must never emit. CI greps for these too, but
#: keeping them codified server-side lets us assert on production responses.
FORBIDDEN_WORDS: tuple[str, ...] = (
    "Intruder",
    "intruder",
    "Manual",
    "manual control",
    "fly drone",
    "alarm",
    "red-alert",
    "red alert",
    "red state",
    "red-state",
)

_FORBIDDEN_RE = re.compile("|".join(re.escape(w) for w in FORBIDDEN_WORDS))


def has_forbidden(text: str) -> str | None:
    """Return the first forbidden token found, or None.

    Substring match is intentional: "Intruder" inside a longer word is still
    a red flag we want to surface during tests.
    """
    m = _FORBIDDEN_RE.search(text)
    return m.group(0) if m else None


def assert_no_forbidden(text: str) -> None:
    """Raise `ValueError` if `text` contains any forbidden token."""
    hit = has_forbidden(text)
    if hit is not None:
        raise ValueError(f"forbidden voice token in copy: {hit!r} in {text!r}")
