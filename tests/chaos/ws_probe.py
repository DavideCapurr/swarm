"""WS reconnect probe — measures close-to-open recovery delta.

Usage::

    python -m tests.chaos.ws_probe \\
        --url ws://localhost:8765/ws/telemetry \\
        --token "$JWT" \\
        --deadline 10

The probe opens an initial connection, waits for the snapshot frame,
then prints ``initial-connect OK``. If invoked with ``--watch`` it then
holds the connection open and prints ``close detected at <ts>`` when
the peer closes; otherwise it exits immediately after the first
snapshot.

For the backend-kill drill the wrapper script in
``scripts/chaos/backend_kill.sh`` runs two probes in sequence: one
``--watch`` to detect the close, then a tight reconnect loop until a
successful open. The reconnect delta is printed as
``RECONNECT_MS=<int>`` so the wrapper can grep + threshold against the
6 s SLO from the plan.

Exit code: 0 on success, 1 on threshold breach, 2 on argument error.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from contextlib import suppress

import websockets

DEFAULT_DEADLINE_S = 10.0
DEFAULT_SLO_MS = 6000  # Phase 6.F: frontend reconnects within 6 s


async def _open_once(url: str, token: str | None, *, snapshot_timeout_s: float) -> None:
    """Open the WS, wait for a frame, then close. Raises on any failure."""

    if token:
        url = f"{url}?token={token}"
    async with websockets.connect(url, max_size=2**20) as ws:
        # Snapshot frame should arrive within the timeout once the
        # backend is fully ready. We do not require any specific shape
        # — the goal is to prove the upgrade + first frame round-trip.
        await asyncio.wait_for(ws.recv(), timeout=snapshot_timeout_s)


async def measure_reconnect(
    url: str,
    token: str | None,
    *,
    deadline_s: float,
    poll_interval_s: float = 0.2,
    snapshot_timeout_s: float = 5.0,
) -> tuple[bool, float]:
    """Loop ``_open_once`` until success or deadline. Returns ``(ok, elapsed_s)``."""

    start = time.monotonic()
    last_error: BaseException | None = None
    while True:
        elapsed = time.monotonic() - start
        if elapsed > deadline_s:
            sys.stderr.write(
                f"reconnect deadline elapsed: {elapsed:.2f}s "
                f"last_error={last_error!r}\n"
            )
            return False, elapsed
        try:
            await _open_once(url, token, snapshot_timeout_s=snapshot_timeout_s)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(poll_interval_s)
            continue
        return True, time.monotonic() - start


async def _watch_for_close(
    url: str,
    token: str | None,
    *,
    deadline_s: float,
) -> tuple[bool, float]:
    """Hold the WS open until the peer closes. Returns ``(closed, elapsed_s)``."""

    full_url = f"{url}?token={token}" if token else url
    start = time.monotonic()
    try:
        async with websockets.connect(full_url, max_size=2**20) as ws:
            try:
                # First frame: prove we're really connected.
                await asyncio.wait_for(ws.recv(), timeout=5.0)
            except TimeoutError:
                sys.stderr.write("watch: no snapshot frame within 5 s\n")
                return False, time.monotonic() - start
            print("watch: connected, awaiting close", flush=True)
            deadline = start + deadline_s
            while time.monotonic() < deadline:
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(ws.recv(), timeout=0.5)
            sys.stderr.write("watch: deadline exceeded without close\n")
            return False, time.monotonic() - start
    except websockets.exceptions.ConnectionClosed:
        return True, time.monotonic() - start
    except Exception as exc:
        sys.stderr.write(f"watch: error {exc!r}\n")
        return False, time.monotonic() - start


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="WS reconnect probe (Phase 6.F)")
    p.add_argument("--url", required=True, help="ws[s]://host:port/ws/telemetry")
    p.add_argument("--token", help="JWT access token (passed as ?token=)")
    p.add_argument(
        "--mode",
        choices=("connect", "reconnect", "watch"),
        default="reconnect",
        help=(
            "connect: open once, exit. "
            "reconnect: loop until a successful open. "
            "watch: hold open until close detected."
        ),
    )
    p.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE_S)
    p.add_argument(
        "--slo-ms",
        type=int,
        default=DEFAULT_SLO_MS,
        help="Fail with exit code 1 if elapsed exceeds this threshold.",
    )
    args = p.parse_args(argv)

    if args.mode == "connect":
        try:
            asyncio.run(_open_once(args.url, args.token, snapshot_timeout_s=5.0))
        except Exception as exc:
            sys.stderr.write(f"connect failed: {exc!r}\n")
            return 1
        print("CONNECT_OK")
        return 0

    if args.mode == "watch":
        ok, elapsed = asyncio.run(
            _watch_for_close(args.url, args.token, deadline_s=args.deadline)
        )
        print(f"CLOSE_DETECTED={int(ok)} ELAPSED_MS={int(elapsed * 1000)}")
        return 0 if ok else 1

    # reconnect mode (default)
    ok, elapsed = asyncio.run(
        measure_reconnect(args.url, args.token, deadline_s=args.deadline)
    )
    print(f"RECONNECT_OK={int(ok)} RECONNECT_MS={int(elapsed * 1000)}")
    if not ok:
        return 1
    if elapsed * 1000 > args.slo_ms:
        sys.stderr.write(
            f"SLO breach: reconnect {int(elapsed * 1000)} ms > {args.slo_ms} ms\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
