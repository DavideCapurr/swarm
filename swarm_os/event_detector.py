"""Raw bus topic to typed Console event projection."""

from __future__ import annotations

from swarm_core.messages import Anomaly, AnomalyView, Event, EventKind, MissionProgress
from swarm_core.voice import describe_anomaly


class EventDetector:
    """Idempotent event builder for bus-derived events."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def anomaly_event(self, anomaly: AnomalyView) -> Event | None:
        key = f"anomaly:{anomaly.id}:{anomaly.state.value}"
        if key in self._seen:
            return None
        self._seen.add(key)
        return Event(
            kind=EventKind.ANOMALY,
            sector_id=anomaly.sector_id,
            agent_id=anomaly.detected_by,
            anomaly_id=anomaly.id,
            confidence=anomaly.confidence,
            body=describe_anomaly(anomaly),
            action_label="Verify sector",
        )

    def raw_anomaly_event(self, anomaly: Anomaly) -> Event:
        return Event(
            kind=EventKind.ANOMALY,
            agent_id=anomaly.source_agent,
            anomaly_id=anomaly.id,
            confidence=anomaly.confidence,
            body="elevated anomaly · verification queued",
            action_label="Verify sector",
        )

    def mission_event(self, progress: MissionProgress, agent_id: str | None = None) -> Event | None:
        key = f"mission:{progress.mission_id}:{progress.phase}:{round(progress.progress_pct)}"
        if key in self._seen:
            return None
        self._seen.add(key)
        return Event(
            kind=EventKind.MISSION,
            mission_id=progress.mission_id,
            agent_id=agent_id,
            body=f"mission {progress.phase.lower()} · progress {round(progress.progress_pct):03d}%",
        )
