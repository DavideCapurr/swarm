"""Reach-aware MAVLink mission execution for the backend fleet runtime.

The original Phase 5 adapter tracked ``MISSION_CURRENT`` as its mission cursor.
That is useful for progress, but it does **not** prove a waypoint was reached:
for a one-item mission PX4 can report item 0 as current immediately after the
mission starts. Treating that as completion causes VERIFY to RTL before the
vehicle reaches the target.

This subclass keeps the existing wire/upload/command implementation and makes
completion semantics strict:

- ``MISSION_CURRENT`` = progress only;
- ``MISSION_ITEM_REACHED`` = waypoint completion proof;
- the final VERIFY ``ON_STATION`` frame is emitted only after the last item is
  reached;
- deadline expiry always triggers RTL + ``FAILED`` rather than ``DONE``.

It is used by the backend's MAVLink fleet composition. Keeping this correction
narrow avoids rewriting the mature connection/upload/safety code while the
live multi-SITL acceptance gate verifies the behavior against PX4.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from pymavlink import mavutil
from swarm_core.messages import MissionProgress, MissionTask
from swarm_core.missions import MissionKind, mission_waypoints

from adapters.mavlink.adapter import MAVLinkAdapter


class ReachAwareMAVLinkAdapter(MAVLinkAdapter):
    """MAVLink adapter that requires ``MISSION_ITEM_REACHED`` for completion."""

    _mission_reached: int = -1

    def _dispatch(self, msg: object) -> None:
        get_type = getattr(msg, "get_type", None)
        if callable(get_type) and get_type() == "MISSION_ITEM_REACHED":
            self._mission_reached = int(getattr(msg, "seq", -1))
        super()._dispatch(msg)

    async def _fly_waypoints(  # type: ignore[override]
        self,
        mission: MissionTask,
    ) -> AsyncIterator[MissionProgress]:
        waypoints = mission_waypoints(mission)
        if not waypoints:
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=0.0,
                error="empty mission",
            )
            return

        default_alt = float(mission.params.get("altitude_m", 60.0))
        self._validate_waypoints_against_safety(waypoints, default_alt)
        timeout_s = self._mission_deadline_s(mission, waypoints)

        # Reset mission-observation state before upload/start so an old cursor
        # or reached frame from the previous mission can never complete this one.
        self._mission_total = len(waypoints)
        self._mission_current = -1
        self._mission_reached = -1

        await self._upload_mission(waypoints, default_alt)
        await self._send_command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=1.0,
        )
        await self._set_mode_auto_mission()
        await self._send_command_long(mavutil.mavlink.MAV_CMD_MISSION_START)
        yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=5.0)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        last_current = -1
        last_reached = -1
        completed = False

        while loop.time() < deadline:
            if self._cancelled:
                await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
                yield MissionProgress(
                    mission_id=mission.id,
                    phase="FAILED",
                    progress_pct=0.0,
                    error="cancelled",
                )
                return

            if self._paused:
                deadline += 0.05
                await asyncio.sleep(0.05)
                continue

            # MISSION_CURRENT says which item PX4 is working on. Surface it as
            # travel progress, never as proof that the item has been reached.
            if self._mission_current >= 0 and self._mission_current != last_current:
                last_current = self._mission_current
                if mission.kind != MissionKind.VERIFY.value or self._mission_total > 1:
                    pct = min(
                        85.0,
                        5.0
                        + self._mission_current
                        / max(self._mission_total, 1)
                        * 80.0,
                    )
                    yield MissionProgress(
                        mission_id=mission.id,
                        phase="EN_ROUTE",
                        progress_pct=pct,
                    )

            if self._mission_reached >= 0 and self._mission_reached != last_reached:
                last_reached = self._mission_reached
                if self._mission_reached >= self._mission_total - 1:
                    completed = True
                    if mission.kind == MissionKind.VERIFY.value:
                        yield MissionProgress(
                            mission_id=mission.id,
                            phase="ON_STATION",
                            progress_pct=95.0,
                        )
                    break

                pct = min(
                    90.0,
                    10.0
                    + (self._mission_reached + 1)
                    / max(self._mission_total, 1)
                    * 80.0,
                )
                yield MissionProgress(
                    mission_id=mission.id,
                    phase="EN_ROUTE",
                    progress_pct=pct,
                )

            await asyncio.sleep(0.05)

        if not completed:
            await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=0.0,
                error="mission deadline exceeded before final waypoint reached",
            )
            return

        await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
        yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)


__all__ = ("ReachAwareMAVLinkAdapter",)
