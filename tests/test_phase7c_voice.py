"""Phase 7.C — voice audit across the new copy.

CLAUDE.md §5.2 forbids `Intruder`/`Manual`/`fly drone`/`alarm`/`red*`
across every operator-facing surface. The voice audit greps the new
backend body strings and the new frontend chip strings to make sure
the AUTO eyebrow + the autonomy event copy stay inside the band.
"""

from __future__ import annotations

import re
from pathlib import Path

from swarm_core.voice import FORBIDDEN_WORDS, has_forbidden

ROOT = Path(__file__).resolve().parents[1]

# Files the Phase 7.C plan touches or creates with new operator-facing copy.
_TARGETED_FILES = (
    "swarm_os/event_detector.py",
    "swarm_os/autonomy.py",
    "frontend/components/HeadBar.tsx",
    "frontend/components/CommandTimeline.tsx",
    "frontend/components/EventFeed.tsx",
    "frontend/components/AnomalySummary.tsx",
    "frontend/components/MobileAnomalyScreen.tsx",
    "frontend/app/(console)/verify/[id]/page.tsx",
    "frontend/lib/autonomy.ts",
    "frontend/lib/state.tsx",
)


def test_phase7c_targeted_files_voice_clean() -> None:
    """Each file we touched in 7.C is voice-clean per FORBIDDEN_WORDS."""

    offences: list[tuple[str, int, str, str]] = []
    for rel in _TARGETED_FILES:
        path = ROOT / rel
        assert path.is_file(), f"missing 7.C file: {rel}"
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            hit = has_forbidden(line)
            if hit is not None:
                offences.append((rel, lineno, hit, line.strip()))
    assert offences == [], offences


def test_phase7c_autonomy_event_copy_strings_are_clean() -> None:
    """Spot-check the canonical event bodies the EventDetector emits."""

    bodies = [
        "autonomy verify dispatched · R1",
        "autonomy escalate dispatched · R2",
        "autonomy dismiss dispatched · R3",
        "autonomy verify completed · R1",
        "autonomy verify timed out · R1",
        "autonomy rejected · verify · battery_too_low · R1",
    ]
    for body in bodies:
        assert has_forbidden(body) is None, body


def test_phase7c_no_red_state_chip() -> None:
    """The AUTO chip is Orbital Blue; assert no `text-red` class slipped in."""

    red_marker = re.compile(r"\btext-red\b|\bbg-red\b|\bborder-red\b")
    for rel in _TARGETED_FILES:
        path = ROOT / rel
        if path.suffix not in {".tsx", ".ts"}:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            assert red_marker.search(line) is None, f"{rel}:{lineno} {line!r}"


def test_forbidden_words_constant_is_unchanged() -> None:
    """Defensive: the FORBIDDEN_WORDS tuple must keep the Phase 0 baseline."""

    assert "Intruder" in FORBIDDEN_WORDS
    assert "Manual" in FORBIDDEN_WORDS
    assert "alarm" in FORBIDDEN_WORDS
    assert "red-alert" in FORBIDDEN_WORDS
