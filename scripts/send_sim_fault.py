"""Publish one simulation-only executor failure fact.

This script does not choose a replacement or trigger any recovery method. It
only tells the simulated world that one physical executor failed; SwarmOS must
observe the resulting FAILED mission progress and decide what happens next.
"""

from __future__ import annotations

import argparse
import asyncio

from orchestrator.swarm_orchestrator.bus import (
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
)
from sim.swarm_sim.faults import ExecutorFault


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inject one external simulator executor fault")
    parser.add_argument("--agent", required=True, help="physical simulated executor that fails")
    parser.add_argument("--reason", default="SIMULATED_EXECUTOR_FAILURE")
    return parser


async def _main() -> None:
    args = _parser().parse_args()
    redis_url = redis_url_from_env()
    if not redis_url:
        raise InsecureBusConfiguration(
            "send_sim_fault requires the shared Redis bus used by the simulator"
        )
    bus = RedisBus(redis_url)
    await bus.connect()
    try:
        fault = ExecutorFault(agent_id=args.agent, reason=args.reason)
        await bus.publish("swarm:sim:faults", fault.model_dump_json())
        print(f"published simulated fault agent={fault.agent_id} reason={fault.reason}")
    finally:
        await bus.close()


if __name__ == "__main__":
    asyncio.run(_main())
