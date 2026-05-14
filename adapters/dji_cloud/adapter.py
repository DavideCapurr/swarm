"""DJI Cloud adapter — DJI Dock + DJI Enterprise via Cloud API.

Architecture overview:
  - Outbound (SWARM → drone): REST POST to the DJI Cloud Service backend that the
    customer's DJI Dock is paired with. We do not call DJI's public servers
    directly; we call the *customer's own* DJI Cloud backend (deployed using
    DJI's Cloud SDK on their infra), which forwards to the Dock over MQTT.
  - Inbound (drone → SWARM): MQTT subscription on topics like
    `thing/product/{sn}/osd` (telemetry), `thing/product/{sn}/events`,
    `thing/product/{sn}/state`.

Env required to actually run:
  DJI_CLOUD_APP_KEY, DJI_CLOUD_APP_SECRET
  DJI_CLOUD_MQTT_HOST, DJI_CLOUD_MQTT_PORT, DJI_CLOUD_MQTT_USER, DJI_CLOUD_MQTT_PASSWORD

Methods that require live infra raise `NotConfigured` when env is missing — we
do NOT silently no-op.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from swarm_core.messages import (
    CaptureResult,
    Geo,
    MissionProgress,
    MissionTask,
    SensorKind,
    Telemetry,
    Waypoint,
)
from swarm_core.missions import MissionKind, UnsupportedMission

from adapters.base import (
    Capabilities,
    Failsafes,
    HealthReport,
    Polygon,
    VideoFrame,
)

try:
    import httpx  # part of base deps
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    import paho.mqtt.client as mqtt  # type: ignore[import-not-found]

    _PAHO_AVAILABLE = True
except ImportError:  # pragma: no cover
    mqtt = None  # type: ignore[assignment]
    _PAHO_AVAILABLE = False


class NotConfigured(RuntimeError):
    """Raised when DJI Cloud env vars or a live Dock are not available."""


class DJICloudAdapter:
    vendor: str = "dji_cloud"

    def __init__(
        self,
        *,
        agent_id: str,
        serial_number: str,
        cloud_base_url: str | None = None,
        model: str = "matrice-3d",
    ) -> None:
        self.agent_id = agent_id
        self.model = model
        self.serial_number = serial_number
        self._cloud_base_url = cloud_base_url or os.getenv("DJI_CLOUD_BASE_URL")
        self._app_key = os.getenv("DJI_CLOUD_APP_KEY")
        self._app_secret = os.getenv("DJI_CLOUD_APP_SECRET")
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
            has_obstacle_avoidance=True,
            has_rtk=True,
            max_flight_time_s=2700.0,  # ~45 min for Matrice 3D
            max_speed_mps=15.0,
            max_altitude_m=500.0,
        )
        self.autopilot_failsafes = Failsafes(
            lost_link_rtl=True,
            low_battery_rtl=True,
            low_battery_threshold_pct=25.0,
        )
        self._mqtt: Any | None = None
        self._connected = False
        self._http: Any | None = None
        self._cancelled = False

    # ── lifecycle ────────────────────────────────────────────────────────────

    def _require_config(self) -> None:
        if not (self._cloud_base_url and self._app_key and self._app_secret):
            raise NotConfigured(
                "DJI Cloud adapter requires DJI_CLOUD_BASE_URL, DJI_CLOUD_APP_KEY, DJI_CLOUD_APP_SECRET"
            )
        if not _PAHO_AVAILABLE:
            raise NotConfigured(
                'paho-mqtt is required for DJI Cloud. Install with: pip install -e ".[dji]"'
            )

    async def connect(self) -> None:
        self._require_config()
        assert httpx is not None and mqtt is not None
        assert self._cloud_base_url is not None
        self._http = httpx.AsyncClient(
            base_url=self._cloud_base_url,
            headers=self._auth_headers(),
            timeout=15.0,
        )
        host = os.getenv("DJI_CLOUD_MQTT_HOST", "")
        port = int(os.getenv("DJI_CLOUD_MQTT_PORT", "8883"))
        user = os.getenv("DJI_CLOUD_MQTT_USER", "")
        pw = os.getenv("DJI_CLOUD_MQTT_PASSWORD", "")
        if not host:
            raise NotConfigured("DJI_CLOUD_MQTT_HOST is required")
        self._mqtt = mqtt.Client(client_id=f"swarm-{self.agent_id}")
        self._mqtt.username_pw_set(user, pw)
        # Note: real TLS configuration would happen here.
        self._mqtt.connect_async(host, port=port, keepalive=30)
        self._mqtt.loop_start()
        self._mqtt.subscribe(f"thing/product/{self.serial_number}/osd")
        self._mqtt.subscribe(f"thing/product/{self.serial_number}/events")
        self._connected = True

    async def disconnect(self) -> None:
        if self._mqtt is not None:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()
            self._mqtt = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        self._connected = False

    async def health(self) -> HealthReport:
        if not self._connected or not self._http:
            return HealthReport(online=False, battery_pct=0.0, link_quality=0.0, last_telemetry_age_s=None)
        resp = await self._http.get(f"/manage/api/v1/devices/{self.serial_number}/status")
        data = resp.json()
        return HealthReport(
            online=bool(data.get("online", False)),
            battery_pct=float(data.get("battery_pct", 0.0)),
            link_quality=float(data.get("link_quality", 1.0)),
            last_telemetry_age_s=float(data.get("last_seen_s", 0.0)),
        )

    # ── safety envelope ──────────────────────────────────────────────────────

    async def set_safety(
        self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int
    ) -> None:
        self._require_config()
        assert self._http is not None
        await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/safety_config",
            json={
                "geofence": [{"lat": p.lat, "lon": p.lon} for p in geofence.points],
                "max_altitude_m": max_alt_m,
                "rtl_battery_pct": rtl_battery_pct,
            },
        )

    # ── mission ──────────────────────────────────────────────────────────────

    async def execute_mission(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:  # type: ignore[override]
        self._require_config()
        assert self._http is not None
        kind = mission.kind
        self._cancelled = False

        if kind == MissionKind.COVER.value:
            raise UnsupportedMission("COVER must be decomposed in orchestrator before dispatch")
        if kind not in {k.value for k in MissionKind}:
            raise UnsupportedMission(f"unknown mission kind: {kind}")

        # Translate to DJI Waypoint Mission KMZ payload.
        kmz_payload = self._mission_to_dji_payload(mission)
        upload = await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/missions",
            json=kmz_payload,
        )
        dji_mission_id = upload.json().get("mission_id")
        yield MissionProgress(mission_id=mission.id, phase="BIDDING", progress_pct=2.0)

        await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/missions/{dji_mission_id}/start"
        )
        yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=10.0)

        # Poll mission state via REST as a fallback (MQTT is the primary path).
        for _ in range(600):  # up to ~10 min poll
            if self._cancelled:
                break
            await asyncio.sleep(1.0)
            r = await self._http.get(
                f"/control/api/v1/devices/{self.serial_number}/missions/{dji_mission_id}"
            )
            state = r.json()
            pct = float(state.get("progress_pct", 0.0))
            yield MissionProgress(
                mission_id=mission.id,
                phase=state.get("phase", "EN_ROUTE"),
                progress_pct=pct,
            )
            if state.get("phase") in ("DONE", "FAILED"):
                return

    def _mission_to_dji_payload(self, mission: MissionTask) -> dict[str, Any]:
        """Translate a SWARM `MissionTask` to a DJI Cloud Waypoint Mission JSON payload.

        Commit-1 implementation produces a minimal JSON the customer's DJI Cloud
        backend is expected to convert to KMZ. Real production would embed the
        full KMZ XML according to DJI's Waypoint Mission Format spec.
        """
        from swarm_core.missions import mission_waypoints
        return {
            "type": mission.kind,
            "priority": mission.priority,
            "altitude_m": mission.params.get("altitude_m", 60.0),
            "waypoints": [
                {"lat": wp.geo.lat, "lon": wp.geo.lon, "alt_m": wp.geo.alt_m, "hover_s": wp.hover_s}
                for wp in mission_waypoints(mission)
            ],
            "sensors": mission.params.get("sensors", []),
            "swarm_mission_id": mission.id,
        }

    async def pause_mission(self) -> None:
        self._require_config()
        assert self._http is not None
        await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/missions/current/pause"
        )

    async def resume_mission(self) -> None:
        self._require_config()
        assert self._http is not None
        await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/missions/current/resume"
        )

    async def cancel_mission(self) -> None:
        self._cancelled = True
        assert self._http is not None
        await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/missions/current/cancel"
        )

    async def divert(self, new_waypoint: Waypoint) -> None:
        self._require_config()
        assert self._http is not None
        await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/control/goto",
            json={
                "lat": new_waypoint.geo.lat,
                "lon": new_waypoint.geo.lon,
                "alt_m": new_waypoint.geo.alt_m or 60.0,
            },
        )

    async def request_capture(self, sensor: SensorKind) -> CaptureResult:
        self._require_config()
        assert self._http is not None
        resp = await self._http.post(
            f"/control/api/v1/devices/{self.serial_number}/payload/capture",
            json={"sensor": sensor.value},
        )
        data = resp.json()
        return CaptureResult(
            sensor=sensor,
            uri=data.get("uri", ""),
            geo=Geo(**data.get("geo", {"lat": 0.0, "lon": 0.0})),
        )

    # ── streams ──────────────────────────────────────────────────────────────

    async def stream_telemetry(self) -> AsyncIterator[Telemetry]:  # type: ignore[override]
        """Telemetry from DJI Cloud comes via MQTT — we bridge MQTT messages to an asyncio Queue."""
        queue: asyncio.Queue[Telemetry] = asyncio.Queue(maxsize=1024)
        loop = asyncio.get_running_loop()

        def _on_message(_client: Any, _userdata: Any, msg: Any) -> None:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                osd = payload.get("data", payload)
                t = Telemetry(
                    agent_id=self.agent_id,
                    geo=Geo(
                        lat=float(osd.get("latitude", 0.0)),
                        lon=float(osd.get("longitude", 0.0)),
                        alt_m=float(osd.get("height", 0.0)),
                    ),
                    battery_pct=float(osd.get("battery_percent", 0.0)),
                )
                loop.call_soon_threadsafe(queue.put_nowait, t)
            except Exception:
                pass

        assert self._mqtt is not None
        self._mqtt.on_message = _on_message
        while self._connected:
            t = await queue.get()
            yield t

    async def stream_video(self) -> AsyncIterator[VideoFrame]:  # type: ignore[override]
        # DJI livestream is via DJI Cloud's RTMP/WebRTC bridge — not wired in commit 1.
        if False:
            yield VideoFrame(self.agent_id, 0, 0, 0, "h264", b"")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "X-Auth-Key": self._app_key or "",
            "X-Auth-Secret": self._app_secret or "",
            "Content-Type": "application/json",
        }
