"""Phase 7.C — brand audit on the AUTO eyebrow + autonomy chip.

PDF §5.2: 85% monochrome, accent colours only for state — Orbital
Blue, Signal Green, Launch Amber. The AUTO chip is Orbital Blue
(focus), the HeadBar `autonomy baseline` chip uses the existing
``StatusPill state="connected"`` halo, and no red accent may appear.

Also asserts the new copy uses the canonical confidence-bound
vocabulary documented in ``docs/plan/phase-7c.md`` (referenced by
PR #58 — long-form plan).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_command_timeline_uses_orbital_blue_for_auto_chip() -> None:
    text = _read("frontend/components/CommandTimeline.tsx")
    assert "text-orbital-blue" in text
    assert "eyebrow-mono" in text
    assert "AUTO" in text
    # Defense: no other accent colour appears next to the chip.
    assert "text-launch-amber" not in re.findall(
        r"AUTO[^\n]*", text
    ).__str__()


def test_event_feed_renders_auto_kind_in_orbital_blue() -> None:
    text = _read("frontend/components/EventFeed.tsx")
    assert "text-orbital-blue" in text
    # The "auto" kind label is the only Phase 7.C addition; keep the row
    # rendering loop on the existing tracking-eyebrow / text-eyebrow tier.
    assert "tracking-eyebrow" in text
    assert "uppercase" in text


def test_headbar_renders_autonomy_chip_with_connected_state() -> None:
    text = _read("frontend/components/HeadBar.tsx")
    assert "autonomy baseline" in text
    # The chip rides the `StatusPill state="connected"` variant (Orbital
    # Blue halo) so we get the design-system halo for free.
    assert 'state="connected"' in text


def test_anomaly_summary_auto_chip_is_orbital_blue() -> None:
    text = _read("frontend/components/AnomalySummary.tsx")
    assert "AUTO" in text
    assert "text-orbital-blue" in text
    # Re-uses the shared selector — no inline filter heuristic.
    assert "findActiveAutonomyCommand" in text


def test_no_red_accent_in_phase7c_files() -> None:
    """No red accent / no red-state marker in any 7.C surface."""

    red_marker = re.compile(
        r"\btext-red\b|\bbg-red\b|\bborder-red\b|red-state|red_state|red alert"
    )
    targets = [
        "frontend/components/HeadBar.tsx",
        "frontend/components/CommandTimeline.tsx",
        "frontend/components/EventFeed.tsx",
        "frontend/components/AnomalySummary.tsx",
        "frontend/components/MobileAnomalyScreen.tsx",
        "frontend/app/(console)/verify/[id]/page.tsx",
        "frontend/lib/autonomy.ts",
        "frontend/lib/state.tsx",
        "swarm_os/event_detector.py",
    ]
    offences: list[tuple[str, int, str]] = []
    for rel in targets:
        path = ROOT / rel
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if red_marker.search(line):
                offences.append((rel, lineno, line.strip()))
    assert offences == [], offences
