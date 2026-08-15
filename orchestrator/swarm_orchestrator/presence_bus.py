"""Bounded on-station response for the real bus-backed fleet runtime.

This is the payload-aware variant of ``BusFleetOrchestrator``. It preserves the
same fleet auction and MAVLink mission execution path already validated against
multi-PX4 SITL, and inserts a narrow policy only after a VERIFY mission has
reached ``ON_STATION``.

For the reach-aware MAVLink adapter, ``ON_STATION`` is emitted only after PX4
reports the final ``MISSION_ITEM_REACHED``. The adapter async generator is
paused at that yield while payload actions run, so it cannot advance to its RTL
branch until the response completes.
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
    PayloadActionStatus,
    PayloadEvent,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.payload import PayloadController, PayloadControllerRegistry
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator

logger = logging.getLogger("swarm.orchestrator.presence_bus")


@dataclass
class PresenceResponseBusFleetOrchestrator(BusFleetOrchestrator):
    """Real-fleet orchestrator with an opt-in bounded presence response."""

    payload_registry: PayloadControllerRegistry = field(
        default_factory=PayloadControllerRegistry
    )
    presence_min_confidence: float = 0.85
    presence_hold_s: float = 5.0
    presence_message: PayloadMessage = PayloadMessage.RESTRICTED_AREA
    _mission_anomalies: dict[str, Anomaly] = field(default_factory=dict)
    _presence_started: set[str] = field(default_factory=set)

    async def _anomaly_loop(self) -> None:
        """Open the normal VERIFY auction while retaining anomaly provenance."""

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
            await self._auction_and_dispatch(mission, anomaly_id=anomaly.id)
            if mission.assigned_agent is None:
                self._mission_anomalies.pop(mission.id, None)

    async def _run_mission(
        self,
        agent_id: str,
        adapter: object,
        mission: MissionTask,
        *,
        is_verify: bool,
    ) -> None:
        """Publish normal progress and pause at verified ON_STATION for payload."""

        try:
            async for progress in adapter.execute_mission(mission):  # type: ignore[attr-defined]
                if not is_verify:
                    continue

                await self.bus.publish(
                    f"swarm:missions:progress:{mission.id}",
                    progress.model_dump_json(),
                )
                await self._publish_runtime_event(
                    agent_id=agent_id,
                    adapter=adapter,
                    progress=progress,
                )

                if (
                    progress.phase == "ON_STATION"
                    and mission.id not in self._presence_started
                ):
                    self._presence_started.add(mission.id)
                    await self._maybe_presence_response(agent_id, mission)

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
                self._agent_mission_ids.pop(agent_id, None)

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
                action=PayloadAction(
                    agent_id=agent_id,
                    kind=PayloadActionKind.LIGHT_ON,
                ),
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
            await asyncio.sleep(max(0.0, self.presence_hold_s))
        finally:
            await self._execute_if_supported(
                controller=controller,
                mission=mission,
                anomaly=anomaly,
                action=PayloadAction(
                    agent_id=agent_id,
                    kind=PayloadActionKind.STOP_MESSAGE,
                ),
            )
            await self._execute_if_supported(
                controller=controller,
                mission=mission,
                anomaly=anomaly,
                action=PayloadAction(
                    agent_id=agent_id,
                    kind=PayloadActionKind.LIGHT_OFF,
                ),
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
        except Exception as exc:
            logger.exception(
                "payload action %s failed for %s",
                action.kind.value,
                action.agent_id,
            )
            failed = PayloadEvent(
                mission_id=mission.id,
                anomaly_id=anomaly.id,
                action_id=action.id,
                agent_id=action.agent_id,
                kind=action.kind,
                status=PayloadActionStatus.FAILED,
                execution_mode=None,
                message=action.message,
                error_code=type(exc).__name__,
            )
            await self.bus.publish("swarm:payload:events", failed.model_dump_json())
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
        structured = PayloadEvent(
            mission_id=mission.id,
            anomaly_id=anomaly.id,
            action_id=result.action_id,
            agent_id=result.agent_id,
            kind=result.kind,
            status=result.status,
            execution_mode=result.execution_mode,
            light_on=result.light_on,
            speaker_active=result.speaker_active,
            message=result.message,
            error_code=result.error_code,
            ts=result.ts,
        )
        await self.bus.publish("swarm:payload:events", structured.model_dump_json())

        mode = {
            PayloadExecutionMode.MAVLINK_ACK: "MAVLink ACK",
            PayloadExecutionMode.MAVLINK_OUTPUT_CONFIRMED: "PX4 OUTPUT CONFIRMED",
            PayloadExecutionMode.SIMULATED: "SIMULATED PAYLOAD",
        }[result.execution_mode]
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


__all__ = ("PresenceResponseBusFleetOrchestrator",)
