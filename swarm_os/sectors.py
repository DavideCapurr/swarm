"""Sector generation and confidence scoring."""

from __future__ import annotations

from datetime import datetime

from swarm_core.geometry import centroid, closest_sector, point_in_polygon, sector_grid
from swarm_core.messages import Geo, RiskBand, Sector, SectorState, UnitState

STALE_AFTER_S = 180.0
BLIND_CONFIDENCE = 0.0


def default_sector_grid(center: Geo, *, half_extent_m: float = 600.0, n: int = 3) -> list[Sector]:
    """Generate the Langhe demo grid with stable human-readable ids."""

    row_names = ["south", "center", "north"]
    col_names = ["a", "b", "c"]
    polygons = sector_grid(center, half_extent_m=half_extent_m, n=n)
    sectors: list[Sector] = []
    for idx, polygon in enumerate(polygons):
        row = idx // n
        col = idx % n
        label = f"{row_names[row]}-{col_names[col]}"
        sectors.append(
            Sector(
                id=label,
                label=label,
                polygon=polygon,
                centroid=centroid(polygon),
                state=SectorState.BLIND,
                confidence=BLIND_CONFIDENCE,
            )
        )
    return sectors


def sector_for_geo(geo: Geo, sectors: dict[str, Sector]) -> str | None:
    """Return containing sector id, falling back to nearest centroid."""

    values = list(sectors.values())
    for sector in values:
        if point_in_polygon(geo, sector.polygon):
            return sector.id
    idx = closest_sector(geo, [s.polygon for s in values])
    if idx is None:
        return None
    return values[idx].id


def refresh_visits(
    sectors: dict[str, Sector], units: dict[str, UnitState], now: datetime
) -> dict[str, Sector]:
    """Mark sectors visited by current unit positions."""

    updated = dict(sectors)
    for unit in units.values():
        sector_id = sector_for_geo(unit.geo, updated)
        if sector_id is None:
            continue
        current = updated[sector_id]
        updated[sector_id] = current.model_copy(
            update={
                "last_visited_at": now,
                "last_visited_by": unit.agent_id,
                "confidence": 1.0,
                "state": SectorState.COVERED
                if not current.pending_anomaly_ids
                else SectorState.ANOMALY,
                "ts": now,
            }
        )
    return updated


def score_sectors(sectors: dict[str, Sector], now: datetime) -> dict[str, Sector]:
    """Apply linear confidence decay and state/risk labels."""

    scored: dict[str, Sector] = {}
    for sector_id, sector in sectors.items():
        if sector.pending_anomaly_ids:
            scored[sector_id] = sector.model_copy(
                update={
                    "state": SectorState.ANOMALY,
                    "risk_band": RiskBand.ELEVATED,
                    "confidence": max(sector.confidence, 0.6),
                    "ts": now,
                }
            )
            continue

        if sector.last_visited_at is None:
            scored[sector_id] = sector.model_copy(
                update={
                    "state": SectorState.BLIND,
                    "risk_band": RiskBand.HIGH,
                    "confidence": BLIND_CONFIDENCE,
                    "ts": now,
                }
            )
            continue

        age_s = max(0.0, (now - sector.last_visited_at).total_seconds())
        confidence = max(0.0, 1.0 - age_s / STALE_AFTER_S)
        state = SectorState.STALE if confidence < 0.35 else SectorState.COVERED
        risk = RiskBand.ELEVATED if state == SectorState.STALE else RiskBand.LOW
        scored[sector_id] = sector.model_copy(
            update={
                "state": state,
                "risk_band": risk,
                "confidence": confidence,
                "ts": now,
            }
        )
    return scored
