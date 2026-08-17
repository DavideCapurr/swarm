#!/usr/bin/env python3
"""YC recording scenario using the validated final-demo truth probe.

This is a presentation scenario, not the authoritative rehearsal artifact.
It reuses `final_demo_rehearsal_probe.run` unchanged so allocation, BUSY
exclusion, mission ownership, PX4 SITL execution evidence, payload truth and
RTL acknowledgement are checked by the same gates as the validated rehearsal.

The only intentional scenario change is event 2 geometry. The validated
rehearsal placed HEAT_SPOT about 2.1 m from mav-001's SITL home, which makes the
second physical execution hard to see in a screen recording. For the YC
recording, event 2 is placed 20 m south and 15 m west of the recorded mav-001
home: 25 m straight-line displacement on a distinct axis from event 1.

`/dev/replay` and `docs/bench/artifacts/final-demo-rehearsal-2026-08-15.json`
remain the source of truth for the original recorded rehearsal geometry.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from final_demo_rehearsal_probe import run

# Same event 1 as the authoritative final rehearsal.
EVENT_A_LAT = 47.3980
EVENT_A_LON = 8.5460
EVENT_A_CONFIDENCE = 0.95

# Presentation-only event 2 geometry.
# Reference mav-001 SITL home from the validated rehearsal:
#   47.3977687, 8.5455943
# Local offset: 15 m west, 20 m south -> 25 m straight-line distance.
EVENT_B_LAT = 47.39758883567882
EVENT_B_LON = 8.54539501307857
EVENT_B_CONFIDENCE = 0.99

SCENARIO_LABEL = "PX4 SITL · SIMULATED OPERATING SCENARIO"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    parser.add_argument("--expected-agents", default="mav-001,mav-002")
    parser.add_argument("--timeout-s", type=float, default=220.0)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    # `run()` intentionally receives the exact argument surface used by the
    # authoritative rehearsal probe. We change only event-b lat/lon defaults.
    args.event_a_lat = EVENT_A_LAT
    args.event_a_lon = EVENT_A_LON
    args.event_a_confidence = EVENT_A_CONFIDENCE
    args.event_b_lat = EVENT_B_LAT
    args.event_b_lon = EVENT_B_LON
    args.event_b_confidence = EVENT_B_CONFIDENCE
    return args


def main() -> int:
    args = parse_args()
    code, report = asyncio.run(run(args))
    report["recording_scenario"] = {
        "label": SCENARIO_LABEL,
        "authoritative_rehearsal_geometry_unchanged": True,
        "event_2": {
            "kind": "HEAT_SPOT",
            "lat": EVENT_B_LAT,
            "lon": EVENT_B_LON,
            "reference_offset_m": {"east": -15.0, "north": -20.0, "distance": 25.0},
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
