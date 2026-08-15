"""Optional on-station presence response for the investor/demo path.

The base ``Orchestrator`` remains unchanged. This subclass adds one narrow,
explicit policy: when a sufficiently confident restricted-area presence
(``AnomalyKind.INTRUSION``) reaches a capture-ready point in the VERIFY
mission, SwarmOS may activate a non-force payload response while the mission
generator is paused at that exact point.

Pausing at the async-generator yield is important: the underlying autopilot
has reached the verification waypoint, and the base mission cannot advance to
RTL until this method returns. That removes the race that a separate bus
consumer would introduce.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from swarm_core.messages import Anomaly, AnomalyKind, Event, EventKind, MissionTask
from swarm_core.missions import VERIFY
from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionResult,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.payload import PayloadController, PayloadControllerRegistry
from orchestrator.swarm_orchestrator.service import Orchestrator

logger = logging.getLogger("swarm.orchestrator.presence")


@dataclass
class PresenceResponseOrchestrator(Orchestrator):
    """Orchestrator with an opt-in light + speaker presence response."""

    payload_registry: PayloadControllerRegistry = field(default_factory=PayloadControllerRegistry)
    presence_min_confidence: float = 0.75
    # The simulated VERIFY path emits ON_STATION once on arrival (~80%) and
    # again after its capture pass (85%). Waiting for the latter prevents a
    # physical-response action from firing merely because the unit arrived.
    presence_ready_progress_pct: float = 85.0
    presence_hold_s: float = 5.0
    presence_message: PayloadMessage = PayloadMessage.RESTRICTED_AREA
    _mission_anomalies: dict[str, Anomaly] = field(default_factory=dict)
    _presence_started: set[str] = field(default_factory=set)

    async def _anomaly_loop(self) -> None:
        """Base anomaly loop plus mission→anomaly provenance for payload policy."""

        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                anomaly = Anomaly.model_validate_json(payload)
            except Exception as exc:
                logger.warning("invalid anomaly payload: %s", exc)
                continue
            logger.info(
                "anomaly received: %s @ (%.5f, %.5f)",
                anomaly.kind.value,
                anomaly.geo.lat,
                anomaly.geo.lon,
            )
            mission = VERIFY(
                geo=anomaly.geo,
                hover_s=self.verify_hover_s,
                priority=80 + int(anomaly.confidence * 20),
            )
            self._mission_anomalies[mission.id] = anomaly
            await self._auction_and_dispatch(mission)
            # If allocation failed, do not retain provenance forever.
            if mission.assigned_agent is None:
                self._mission_anomalies.pop(mission.id, None)

    async def _run_mission(
        self, agent_id: str, adapter: object, mission: MissionTask, *, is_verify: bool
    ) -> None:
        """Drive the base mission loop and intercept capture-ready ON_STATION."""

        try:
            async for progress in adapter.execute_mission(mission):  # type: ignore[attr-defined]
                if (
                    is_verify
                    and progress.phase == "ON_STATION"
                    and progress.progress_pct >= self.presence_ready_progress_pct
                    and mission.id not in self._presence_started
                ):
                    self._presence_started.add(mission.id)
                    await self._maybe_presence_response(agent_id, mission)

                if not is_verify:
                    continue
                await self.bus.publish(
                    f"swarm:missions:progress:{mission.id}",
                    progress.model_dump_json(),
                )
                if progress.phase in ("DONE", "FAILED"):
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("mission %s failed: %s", mission.id, exc)
        finally:
            self._busy.discard(agent_id)
            self._verifying.discard(agent_id)
            self._mission_anomalies.pop(mission.id, None)
            self._presence_started.discard(mission.id)
            if self._agent_tasks.get(agent_id) is asyncio.current_task():
                self._agent_tasks.pop(agent_id, None)

    async def _maybe_presence_response(self, agent_id: str, mission: MissionTask) -> None:
        anomaly = self._mission_anomalies.get(mission.id)
        if anomaly is None:
            return
        if anomaly.kind is not AnomalyKind.INTRUSION:
            return
        if anomaly.confidence < self.presence_min_confidence:
            return

        controller = self.payload_registry.get_optional(agent_id)
        if controller is None:
            await self._publish_payload_event(
                mission=mission,
                anomaly=anomaly,
                agent_id=agent_id,
                body=f"{agent_id} presence response unavailable · no payload controller",
            )
            return

        try:
            await self._execute_if_supported(
                controller=controller,
                mission=mission,
                anomaly=anomaly,
                action=PayloadAction(agent_id=agent_id, kind=PayloadActionKind.LIGHT_ON),
            )
            await self._execute_if_supported(
                controller=controller,
                mission=mission,
                anomaly=anomaly,
                action=PayloadAction(
                    agent_id=agent_id,
                    kind=PayloadActionKind.PLAY_MESSAGE,
                    message=self.presence_message,
                ),
            )

            # The mission async generator is suspended on ON_STATION while
            # this sleep runs. It therefore cannot advance to its RTL branch.
            await asyncio.sleep(max(0.0, self.presence_hold_s))
        finally:
            # Fail-safe cleanup: cancellation or an exception must not leave a
            # payload logically active. Unsupported capabilities are skipped.
            await self._execute_if_supported(
                controller=controller,
                mission=mission,
                anomaly=anomaly,
                action=PayloadAction(agent_id=agent_id, kind=PayloadActionKind.STOP_MESSAGE),
            )
            await self._execute_if_supported(
                controller=controller,
                mission=mission,
                anomaly=anomaly,
                action=PayloadAction(agent_id=agent_id, kind=PayloadActionKind.LIGHT_OFF),
            )

    async def _execute_if_supported(
        self,
        *,
        controller: PayloadController,
        mission: MissionTask,
        anomaly: Anomaly,
        action: PayloadAction,
    ) -> None:
        if action.kind not in controller.capabilities:
            return
        try:
            result = await controller.execute(action)
        except Exception:
            logger.exception(
                "payload action %s failed for %s", action.kind.value, action.agent_id
            )
            await self._publish_payload_event(
                mission=mission,
                anomaly=anomaly,
                agent_id=action.agent_id,
                body=f"{action.agent_id} payload action {action.kind.value} failed",
            )
            return
        await self._publish_result(mission=mission, anomaly=anomaly, result=result)

    async def _publish_result(
        self,
        *,
        mission: MissionTask,
        anomaly: Anomaly,
        result: PayloadActionResult,
    ) -> None:
        mode = (
            "MAVLink ACK"
            if result.execution_mode is PayloadExecutionMode.MAVLINK_ACK
            else "SIMULATED PAYLOAD"
        )
        label = {
            PayloadActionKind.LIGHT_ON: "light on",
            PayloadActionKind.LIGHT_OFF: "light off",
            PayloadActionKind.PLAY_MESSAGE: "restricted-area message active",
            PayloadActionKind.STOP_MESSAGE: "restricted-area message stopped",
        }[result.kind]
        await self._publish_payload_event(
            mission=mission,
            anomaly=anomaly,
            agent_id=result.agent_id,
            body=f"{result.agent_id} {label} · {mode}",
        )

    async def _publish_payload_event(
        self,
        *,
        mission: MissionTask,
        anomaly: Anomaly,
        agent_id: str,
        body: str,
    ) -> None:
        event = Event(
            kind=EventKind.MISSION,
            agent_id=agent_id,
            mission_id=mission.id,
            anomaly_id=anomaly.id,
            body=body,
            action_label="presence response",
            source="autonomy",
        )
        await self.bus.publish("swarm:events:payload", event.model_dump_json())
