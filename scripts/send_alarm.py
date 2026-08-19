"""Publish one external alarm to SwarmOS.

This script deliberately knows nothing about response aircraft, groups,
reinforcement or replacement. It is the demo's external world input.

Example:

    python scripts/send_alarm.py --lat 47.3979 --lon 8.5457 --confidence 0.97
"""

from __future__ import annotations

import argparse
import asyncio

from swarm_core.messages import Anomaly, AnomalyKind, Geo

from orchestrator.swarm_orchestrator.bus import (
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish one external SwarmOS alarm")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--confidence", type=float, default=0.97)
    parser.add_argument(
        "--kind",
        choices=[kind.value for kind in AnomalyKind],
        default=AnomalyKind.INTRUSION.value,
    )
    parser.add_argument("--id", dest="alarm_id", default=None)
    return parser


async def _main() -> None:
    args = _parser().parse_args()
    redis_url = redis_url_from_env()
    if not redis_url:
        raise InsecureBusConfiguration(
            "send_alarm requires the shared Redis bus used by backend + demo runner"
        )
    bus = RedisBus(redis_url)
    await bus.connect()
    try:
        kwargs: dict[str, object] = {
            "kind": AnomalyKind(args.kind),
            "geo": Geo(lat=args.lat, lon=args.lon),
            "confidence": args.confidence,
        }
        if args.alarm_id:
            kwargs["id"] = args.alarm_id
        alarm = Anomaly(**kwargs)  # type: ignore[arg-type]
        await bus.publish("swarm:anomalies", alarm.model_dump_json())
        print(
            f"published alarm {alarm.id} kind={alarm.kind.value} "
            f"confidence={alarm.confidence:.2f} @ {alarm.geo.lat:.6f},{alarm.geo.lon:.6f}"
        )
    finally:
        await bus.close()


if __name__ == "__main__":
    asyncio.run(_main())
