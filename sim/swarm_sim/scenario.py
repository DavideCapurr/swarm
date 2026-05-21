"""Scenario loader for Phase 7.A — three MVP scenarios in `sim/scenarios/`.

A scenario YAML declares an anchor (WGS84), a rectangular plot, the fleet
size, the perception territory, and a list of scripted CV-style anomalies
emitted at scheduled times. `load_scenario()` parses + validates the YAML
into a frozen `Scenario` Pydantic model; `Scenario.build_world()` returns a
`World` ready for the sim runner.

The schema is deterministic: same YAML in → same `World` out (no random in
the loader). This is the contract Phase 8.B-bis "modalità ombra" depends
on. Future phases extend the schema via top-level fields (`media`,
`iot_events`, `user_app_events`); `extra="forbid"` makes each extension
explicit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field
from swarm_core.messages import AnomalyKind, Geo

from sim.swarm_sim.drone import Drone
from sim.swarm_sim.perception import IgnitionEvent, MockPerception
from sim.swarm_sim.world import World

_STRICT = ConfigDict(extra="forbid", frozen=True)
_M_PER_DEG = 111_000.0


class AnchorCfg(BaseModel):
    model_config = _STRICT
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    alt_m: float = 0.0


class PlotCfg(BaseModel):
    model_config = _STRICT
    shape: Literal["rectangle"] = "rectangle"
    width_m: float = Field(..., gt=0.0)
    height_m: float = Field(..., gt=0.0)


class DockOffsetCfg(BaseModel):
    model_config = _STRICT
    east: float = 0.0
    north: float = 0.0


class FleetCfg(BaseModel):
    model_config = _STRICT
    n_drones: int = Field(..., ge=1, le=20)
    dock_offset_m: DockOffsetCfg = Field(default_factory=DockOffsetCfg)


class PerceptionCfg(BaseModel):
    model_config = _STRICT
    territory_radius_m: float = Field(..., gt=0.0)
    # Phase 7.D — opt-in CV baseline. Default off so legacy scenarios
    # (and every existing test) keep the deterministic MockPerception.
    # When true, `Scenario.build_world()` returns a World whose
    # perception runs YOLOv8 pretrained inference on committed smoke
    # fixtures (or downloaded reference samples) at every scheduled
    # ignition. The geo + kind stay scripted (sim has no geo-localized
    # frames); only `confidence` is derived from the real model output.
    cv_enabled: bool = False


class AnomalyPositionCfg(BaseModel):
    model_config = _STRICT
    mode: Literal["offset_m", "absolute"]
    east: float | None = None
    north: float | None = None
    lat: float | None = None
    lon: float | None = None


class ScriptedAnomalyCfg(BaseModel):
    model_config = _STRICT
    after_s: float = Field(..., ge=0.0)
    kind: AnomalyKind
    position: AnomalyPositionCfg
    confidence: float = Field(..., ge=0.0, le=1.0)


class Scenario(BaseModel):
    model_config = _STRICT
    id: str
    name: str
    description: str
    tick_hz: float = Field(10.0, gt=0.0)
    # Phase 7.B — flips the deterministic autonomy baseline on when this
    # scenario is loaded by `sim/swarm_sim/runner.py`. Default False so
    # legacy scenarios (and every existing test) keep operator-only flow.
    autonomy_baseline: bool = False
    anchor: AnchorCfg
    plot: PlotCfg
    fleet: FleetCfg
    perception: PerceptionCfg
    anomalies: list[ScriptedAnomalyCfg] = Field(default_factory=list)

    def resolve_geo(self, pos: AnomalyPositionCfg) -> Geo:
        if pos.mode == "absolute":
            if pos.lat is None or pos.lon is None:
                raise ValueError("position.mode='absolute' requires lat and lon")
            return Geo(lat=pos.lat, lon=pos.lon)
        if pos.east is None or pos.north is None:
            raise ValueError("position.mode='offset_m' requires east and north")
        dlat = pos.north / _M_PER_DEG
        dlon = pos.east / _M_PER_DEG
        return Geo(lat=self.anchor.lat + dlat, lon=self.anchor.lon + dlon)

    def build_world(self) -> World:
        dock = Geo(
            lat=self.anchor.lat + self.fleet.dock_offset_m.north / _M_PER_DEG,
            lon=self.anchor.lon + self.fleet.dock_offset_m.east / _M_PER_DEG,
            alt_m=self.anchor.alt_m,
        )
        drones = [
            Drone(agent_id=f"sim-{i + 1}", dock=dock)
            for i in range(self.fleet.n_drones)
        ]
        ignitions = [
            IgnitionEvent(
                after_s=a.after_s,
                geo=self.resolve_geo(a.position),
                kind=a.kind,
                confidence=a.confidence,
            )
            for a in self.anomalies
        ]
        if self.perception.cv_enabled:
            # Lazy import — keeps the `cv` extra opt-in and the import
            # path off the default sim boot. The module raises an actionable
            # error if `ultralytics`/`torch` aren't installed.
            from sim.swarm_sim.cv.perception_cv import CVPerception

            cv_perception = CVPerception(
                territory_center=dock,
                territory_radius_m=self.perception.territory_radius_m,
                ignitions=ignitions,
                scenario_id=self.id,
            )
            return World(dock=dock, drones=drones, perception=cv_perception)
        mock_perception = MockPerception(
            territory_center=dock,
            territory_radius_m=self.perception.territory_radius_m,
            ignitions=ignitions,
        )
        return World(dock=dock, drones=drones, perception=mock_perception)


def load_scenario(path: Path) -> Scenario:
    """Parse + validate a scenario YAML; raises FileNotFoundError or
    pydantic.ValidationError on malformed input — both are intentionally
    loud (CLAUDE.md regola 3: no silent failure-swallowing)."""
    data = yaml.safe_load(path.read_text())
    return Scenario.model_validate(data)
