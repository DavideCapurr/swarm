#!/usr/bin/env python3
"""Phase 7.E — baseline metrics collector for the `make demo-*` scenarios.

Logs in as a viewer (read-only), waits for the scenario to run for a
configurable window, then snapshots the SwarmOS audit log into a JSON
artifact under ``docs/bench/artifacts/``. The artifact is the evidence
piece for the Phase 7 gate "ogni decisione autonoma è loggata,
metriche baseline raccolte".

What gets counted (honest numbers only — no derivations):

  * autonomy decisions per rule (R1 / R2 / R3) from the
    ``OperatorCommand`` audit log (``source == "autonomy"``).
  * autonomy decisions by status (completed / rejected / timed_out).
  * events emitted with ``source == "autonomy"`` and the EventKind tally.
  * the wall-clock window covered.

The collector reads only existing endpoints (Phase 4 + 7.C). No new
backend surface. No /metrics (commander+MFA gated; out of scope here).

Usage::

    python scripts/scenario_metrics.py \\
        --scenario wildfire_owner_land \\
        --duration 60 \\
        --backend http://localhost:8765
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = REPO_ROOT / "docs" / "bench" / "artifacts"

DEFAULT_USER = "op-viewer01"
DEFAULT_PASSWORD = "swarm-dev"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _login(backend: str, user: str, password: str) -> str:
    body: dict[str, str] = {"operator_id": user, "password": password}
    r = httpx.post(f"{backend}/auth/login", json=body, timeout=10.0)
    if r.status_code != 200:
        raise SystemExit(
            f"[scenario_metrics] login failed: HTTP {r.status_code} {r.text[:200]}"
        )
    token = r.json().get("access_token")
    if not token:
        raise SystemExit(f"[scenario_metrics] login response missing access_token: {r.json()}")
    return str(token)


def _wait_for_backend(backend: str, timeout_s: float = 60.0) -> None:
    """Poll /health until 200 or timeout. The collector launches alongside
    dev_up.sh — backend boot takes a few seconds, so we give it room."""

    deadline = time.monotonic() + timeout_s
    last_err = ""
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{backend}/health", timeout=2.0)
            if r.status_code == 200:
                return
            last_err = f"HTTP {r.status_code}"
        except httpx.HTTPError as exc:
            last_err = str(exc)
        time.sleep(1.0)
    raise SystemExit(
        f"[scenario_metrics] backend never became healthy at {backend}: {last_err}"
    )


def _fetch(backend: str, path: str, token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{backend}{path}", headers=headers, timeout=10.0)
    if r.status_code != 200:
        raise SystemExit(
            f"[scenario_metrics] GET {path} failed: HTTP {r.status_code} {r.text[:200]}"
        )
    return r.json()


def collect(backend: str, token: str) -> dict[str, Any]:
    commands_payload = _fetch(backend, "/commands?limit=500", token)
    events_payload = _fetch(backend, "/events?limit=500", token)

    commands: list[dict[str, Any]] = commands_payload.get("commands", [])
    events: list[dict[str, Any]] = events_payload.get("events", [])

    auto_cmds = [c for c in commands if c.get("source") == "autonomy"]
    operator_cmds = [c for c in commands if c.get("source") != "autonomy"]
    rule_counts: Counter[str] = Counter(c.get("rule") or "unspecified" for c in auto_cmds)
    status_counts: Counter[str] = Counter(
        str(c.get("status") or "unknown") for c in auto_cmds
    )

    auto_events = [e for e in events if e.get("source") == "autonomy"]
    event_kind_counts: Counter[str] = Counter(str(e.get("kind")) for e in events)
    auto_event_kind_counts: Counter[str] = Counter(
        str(e.get("kind")) for e in auto_events
    )

    return {
        "commands_total": len(commands),
        "auto_commands_total": len(auto_cmds),
        "operator_commands_total": len(operator_cmds),
        "auto_decisions": {
            "by_rule": dict(rule_counts),
            "by_status": dict(status_counts),
        },
        "events_total": len(events),
        "auto_events_total": len(auto_events),
        "events_by_kind": dict(event_kind_counts),
        "auto_events_by_kind": dict(auto_event_kind_counts),
    }


def write_artifact(scenario: str, payload: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = ARTIFACT_DIR / f"phase-7e-{scenario}-{ts}.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 7.E baseline metrics collector")
    parser.add_argument("--scenario", required=True, help="scenario id (no .yaml suffix)")
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="seconds to let the scenario run before snapshotting (default 60)",
    )
    parser.add_argument(
        "--backend",
        default="http://localhost:8765",
        help="backend base URL (default http://localhost:8765)",
    )
    parser.add_argument("--user", default=DEFAULT_USER, help="viewer operator id")
    parser.add_argument(
        "--password", default=DEFAULT_PASSWORD, help="viewer password"
    )
    args = parser.parse_args(argv)

    started_at = _utc_iso()
    print(f"[scenario_metrics] waiting for backend at {args.backend} …", flush=True)
    _wait_for_backend(args.backend)
    print(f"[scenario_metrics] backend healthy — login as {args.user}", flush=True)
    token = _login(args.backend, args.user, args.password)
    print(
        f"[scenario_metrics] letting {args.scenario} run for {args.duration}s …",
        flush=True,
    )
    time.sleep(args.duration)

    snapshot = collect(args.backend, token)
    payload: dict[str, Any] = {
        "scenario": args.scenario,
        "backend": args.backend,
        "started_at": started_at,
        "snapshot_at": _utc_iso(),
        "duration_s": args.duration,
        **snapshot,
    }
    out_path = write_artifact(args.scenario, payload)
    print(f"[scenario_metrics] wrote {out_path}", flush=True)
    print(
        f"[scenario_metrics] auto_decisions.by_rule={payload['auto_decisions']['by_rule']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
