"""Project the causal simulator capture through the server-owned truth layer.

The underlying scenario and SwarmOS decisions come from
``capture_causal_take_c._capture``. This wrapper does not add behavior. It
replays captured anomaly/group truth through ``SwarmCoordinator`` so the
recorded Console artifact carries the same PENDING -> VERIFYING -> VERIFIED
anomaly projection as the live backend.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from swarm_core.execution_groups import ExecutionGroup
from swarm_core.messages import Anomaly, AnomalyState, AnomalyView

from scripts.capture_causal_take_c import _capture
from swarm_os.coordinator import SwarmCoordinator
from swarm_os.state import SwarmState


def _source_anomaly(view: AnomalyView) -> Anomaly:
    return Anomaly(
        id=view.id,
        kind=view.kind,
        geo=view.geo,
        confidence=view.confidence,
        source_agent=view.detected_by,
        ts=view.detected_at,
        verified=view.state is AnomalyState.VERIFIED,
        evidence=view.evidence,
    )


async def _project_truth(capture: dict[str, Any]) -> dict[str, Any]:
    coordinator = SwarmCoordinator(SwarmState.vineyard())
    projected_frames: list[dict[str, Any]] = []

    for frame in capture["frames"]:
        kind = frame["kind"]
        at = frame["at"]

        if kind == "anomaly":
            # Replace the harness-created seed view with the exact server-owned
            # anomaly projection. This is a truth projection, not presentation
            # synthesis.
            view = AnomalyView.model_validate(frame["data"])
            server_frames = await coordinator.apply_anomaly(_source_anomaly(view))
            for server_frame in server_frames:
                if server_frame["kind"] == "anomaly_view":
                    projected_frames.append(
                        {"at": at, "kind": "anomaly", "data": server_frame["data"]}
                    )
            continue

        projected_frames.append(frame)

        if kind != "group":
            continue

        group = ExecutionGroup.model_validate(frame["data"])
        server_frames = await coordinator.apply_execution_group(group)
        for server_frame in server_frames:
            if server_frame["kind"] == "anomaly_view":
                projected_frames.append(
                    {"at": at, "kind": "anomaly", "data": server_frame["data"]}
                )

    anomaly_states = [
        AnomalyView.model_validate(frame["data"]).state
        for frame in projected_frames
        if frame["kind"] == "anomaly"
    ]
    if not anomaly_states or anomaly_states[-1] is not AnomalyState.VERIFIED:
        raise RuntimeError("causal Take C capture did not end with a verified anomaly")

    capture["frames"] = projected_frames
    capture["proof_scope"]["anomaly_lifecycle"] = (
        "SwarmCoordinator projection from captured execution-group truth"
    )
    capture["milestones"]["anomaly_verified_at_ms"] = next(
        frame["at"]
        for frame in projected_frames
        if frame["kind"] == "anomaly"
        and frame["data"]["state"] == AnomalyState.VERIFIED.value
    )
    return capture


async def _main() -> None:
    destination = Path(
        sys.argv[1] if len(sys.argv) > 1 else "artifacts/take-c-causal-sim.json"
    )
    capture = await _project_truth(await _capture())
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(capture, indent=2) + "\n"
    await asyncio.to_thread(destination.write_text, payload, encoding="utf-8")
    anomaly_frames = sum(frame["kind"] == "anomaly" for frame in capture["frames"])
    print(
        "TAKE_C_TRUTH_CAPTURE "
        f"frames={len(capture['frames'])} "
        f"anomaly_frames={anomaly_frames} "
        f"verified_at_ms={capture['milestones']['anomaly_verified_at_ms']} "
        f"revisions={capture['milestones']['composition_revision']}"
        f"->{capture['milestones']['reinforcement_revision']}"
        f"->{capture['milestones']['replacement_revision']}"
    )
    print(f"TAKE_C_CAPTURE_PATH {destination}")


if __name__ == "__main__":
    asyncio.run(_main())
