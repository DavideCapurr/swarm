"""Bounded on-station response for the real bus-backed fleet runtime.

This payload-aware runtime supports both ordinary single-agent VERIFY and
SwarmOS-owned cooperative execution groups. For a cooperative response only the
PRIMARY_OBSERVER may execute the presence payload policy; secondary observers
and overwatch remain observation roles. Member drones never choose that policy.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from swarm_core.messages import (
    Anomaly,
    AnomalyKind,
    Event,
    EventKind,
    MissionProgress,
    MissionTask,
)
from swarm_core.missions import COOPERATIVE_VERIFY, VERIFY
from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionResult,
    PayloadActionStatus,
    PayloadEvent,
    PayloadExecutionMode,
    PayloadMessage,
)
from swarm_core.runtime_events import MissionRuntimeEvent

from adapters.payload import PayloadController, PayloadControllerRegistry
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator

logger = logging.getLogger("swarm.orchestrator.presence_bus")

PRIMARY_PRESENCE_ROLE = "PRIMARY_OBSERVER"
_MAX_GROUP_ANOMALY_HISTORY = 500


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
    _anomalies_by_id: dict[str, Anomaly] = field(default_factory=dict)
    _presence_started: set[str] = field(default_factory=set)

    async def _anomaly_loop(self) -> None:
        """Choose single or cooperative verification while retaining provenance."""

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
            self._remember_anomaly(anomaly)

            if self._should_cooperative_verify(anomaly):
                parent = COOPERATIVE_VERIFY(
                    geo=anomaly.geo,
                    team_size=self.cooperative_verify_team_size,
                    hover_s=self.cooperative_verify_hover_s,
                    priority=80 + int(anomaly.confidence * 20),
                )
                await self.dispatch_execution_group(parent, anomaly_id=anomaly.id)
                continue

            mission = VERIFY(
                geo=anomaly.geo,
                hover_s=self.verify_hover_s,
                priority=80 + int(anomaly.confidence * 20),
            )
            self._mission_anomalies[mission.id] = anomaly
            await self._auction_and_dispatch(mission, anomaly_id=anomaly.id)
            if mission.assigned_agent is None:
                self._mission_anomalies.pop(mission.id, None)

    def _remember_anomaly(self, anomaly: Anomaly) -> None:
        self._anomalies_by_id[anomaly.id] = anomaly
        while len(self._anomalies_by_id) > _MAX_GROUP_ANOMALY_HISTORY:
            oldest = next(iter(self._anomalies_by_id))
            self._anomalies_by_id.pop(oldest, None)

    def _anomaly_for_mission(self, mission: MissionTask) -> Anomaly | None:
        direct = self._mission_anomalies.get(mission.id)
        if direct is not None:
            return direct
        group_id = mission.params.get("execution_group_id")
        if not isinstance(group_id, str):
            return None
        group = self.execution_groups.get(group_id)
        if group is None or group.anomaly_id is None:
            return None
        return self._anomalies_by_id.get(group.anomaly_id)

    def _mission_may_execute_presence_payload(self, mission: MissionTask) -> bool:
        role = self.group_role_for_mission(mission.id)
        return role is None or role == PRIMARY_PRESENCE_ROLE

    async def _run_mission(
        self,
        agent_id: str,
        adapter: object,
        mission: MissionTask,
        *,
        is_verify: bool,
    ) -> None:
        """Publish normal progress and pause verified primary role for payload."""

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
                    and self._mission_may_execute_presence_payload(mission)
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

    async def _publish_runtime_event(
        self,
        *,
        agent_id: str,
        adapter: object,
        progress: MissionProgress,
    ) -> None:
        evidence = None
        evidence_for_phase = getattr(adapter, "runtime_evidence_for_phase", None)
        if callable(evidence_for_phase):
            try:
                evidence = evidence_for_phase(progress.phase)
            except Exception:
                logger.exception(
                    "runtime evidence projection failed for %s %s",
                    agent_id,
                    progress.phase,
                )
        event = MissionRuntimeEvent(
            mission_id=progress.mission_id,
            agent_id=agent_id,
            phase=progress.phase,
            progress_pct=progress.progress_pct,
            evidence=evidence,
            error=progress.error,
            ts=progress.ts,
        )
        await self.bus.publish("swarm:missions:runtime", event.model_dump_json())

    async def _maybe_presence_response(
        self, agent_id: str, mission: MissionTask
    ) -> None:
        anomaly = self._anomaly_for_mission(mission)
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
