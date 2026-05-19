#!/usr/bin/env python3
"""Phase 6.J — ZAP baseline post-step gate.

Reads a ``zap-baseline.py -J <out.json>`` report and exits non-zero
when any finding has ``riskcode >= 3`` (High). Medium / Low / Info
findings are reported but never fail the build — they live in the
artifact for triage. Confidence is ignored: a single High signal is
enough to break the build.

The script is intentionally dependency-free (stdlib only) so the
post-step doesn't have to install the project's full virtualenv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HIGH = 3


def _summarise(alerts: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
    for alert in alerts:
        try:
            risk = int(alert.get("riskcode", 0))
        except (TypeError, ValueError):
            risk = 0
        counts[risk] = counts.get(risk, 0) + 1
    return counts


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report",
        type=Path,
        help="Path to the JSON report produced by zap-baseline.py -J",
    )
    args = parser.parse_args(argv)

    if not args.report.is_file():
        print(f"[zap-fail-on-high] report not found: {args.report}", file=sys.stderr)
        return 2

    payload = json.loads(args.report.read_text())
    sites = payload.get("site") if isinstance(payload, dict) else None
    if not isinstance(sites, list):
        print(
            f"[zap-fail-on-high] unexpected report shape (no 'site' list): {args.report}",
            file=sys.stderr,
        )
        return 2

    all_alerts: list[dict] = []
    for site in sites:
        alerts = site.get("alerts") or []
        if isinstance(alerts, list):
            all_alerts.extend(alerts)

    counts = _summarise(all_alerts)
    print(
        "[zap-fail-on-high] findings — "
        f"high={counts.get(3, 0)} medium={counts.get(2, 0)} "
        f"low={counts.get(1, 0)} info={counts.get(0, 0)}"
    )

    high_findings = [a for a in all_alerts if int(a.get("riskcode", 0)) >= HIGH]
    if high_findings:
        for alert in high_findings:
            print(
                f"[zap-fail-on-high] HIGH: {alert.get('name', '?')} "
                f"({alert.get('pluginid', '?')})",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
