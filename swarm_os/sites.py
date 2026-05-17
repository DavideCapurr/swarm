"""Site configuration loader for the Phase 6.A policy engine.

A `SiteConfig` is the per-site source of operational truth: geofence
polygon, max altitude, battery / link / weather thresholds, weather
provider selection. It is loaded from
`infra/config/sites/<site_id>.yaml` once at startup. Multi-site
routing + hot reload + audit log of config changes are Phase 6.B —
this module only loads, validates, and falls back to the in-code
default for the legacy `vineyard-01` site so the system remains
bootable in CI without any YAML on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from swarm_core.messages import Geo

from swarm_os.safety import BatteryThresholds, LinkThresholds, WeatherThresholds

DEFAULT_SITE_ID = "vineyard-01"
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "infra" / "config" / "sites"

_STRICT = ConfigDict(extra="forbid", frozen=True)


class GeofenceConfig(BaseModel):
    """The polygon SwarmOS will enforce per mission, plus the altitude cap."""

    model_config = _STRICT
    polygon: list[Geo] = Field(..., min_length=3)
    max_alt_m: float = Field(120.0, gt=0.0)


class ThresholdConfig(BaseModel):
    model_config = _STRICT
    battery: BatteryThresholds = Field(default_factory=BatteryThresholds)
    link: LinkThresholds = Field(default_factory=LinkThresholds)
    weather: WeatherThresholds = Field(default_factory=WeatherThresholds)


class WeatherProviderConfig(BaseModel):
    """Selects the runtime weather source. `kind='stub'` is the CI default
    and is wired to `LocalStubWeatherProvider`. Real providers (OpenWeather,
    Aviationweather) are bound on hardware day per
    `docs/ops/drone-day-checklist.md` §2.A.
    """

    model_config = _STRICT
    kind: str = Field("stub")
    refresh_interval_s: int = Field(300, ge=30)
    api_key_env: str | None = None


class DockConfigEntry(BaseModel):
    model_config = _STRICT
    dock_id: str
    primary: bool = False


class SiteConfig(BaseModel):
    """Per-site policy + topology, loaded from YAML or the built-in default."""

    model_config = _STRICT
    site_id: str
    name: str = ""
    center: Geo
    geofence: GeofenceConfig
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    weather_provider: WeatherProviderConfig = Field(
        default_factory=WeatherProviderConfig
    )
    docks: list[DockConfigEntry] = Field(default_factory=list)


class SiteConfigNotFound(LookupError):
    """Raised when a non-default site_id is requested without a YAML file
    on disk. The built-in fallback is intentionally narrow to
    `vineyard-01` so production deployments fail closed on misconfig."""


def _builtin_vineyard_config() -> SiteConfig:
    """In-code default that matches the legacy hardcoded vineyard.

    Keeps CI green when `infra/config/sites/vineyard-01.yaml` is absent
    (e.g. unit tests, a fresh clone before someone provisions the site).
    """

    center = Geo(lat=44.7000, lon=8.0300, alt_m=0.0)
    half_lat = 0.0090  # ≈ 1 km
    half_lon = 0.0120  # ≈ 1 km at this latitude
    polygon = [
        Geo(lat=center.lat - half_lat, lon=center.lon - half_lon),
        Geo(lat=center.lat - half_lat, lon=center.lon + half_lon),
        Geo(lat=center.lat + half_lat, lon=center.lon + half_lon),
        Geo(lat=center.lat + half_lat, lon=center.lon - half_lon),
    ]
    return SiteConfig(
        site_id=DEFAULT_SITE_ID,
        name="Vineyard (built-in default)",
        center=center,
        geofence=GeofenceConfig(polygon=polygon, max_alt_m=120.0),
        thresholds=ThresholdConfig(),
        weather_provider=WeatherProviderConfig(kind="stub"),
        docks=[DockConfigEntry(dock_id="dock-langhe-01", primary=True)],
    )


def load_site_config(
    site_id: str = DEFAULT_SITE_ID,
    *,
    config_dir: Path | None = None,
) -> SiteConfig:
    """Load `<config_dir>/<site_id>.yaml` and validate to `SiteConfig`.

    If the file is absent and `site_id == DEFAULT_SITE_ID`, returns the
    built-in `_builtin_vineyard_config()` so a fresh clone can boot. Any
    other missing site raises `SiteConfigNotFound`; YAML parse errors
    raise `yaml.YAMLError`; schema errors raise `pydantic.ValidationError`.
    """

    config_dir = config_dir or DEFAULT_CONFIG_DIR
    path = config_dir / f"{site_id}.yaml"
    if path.is_file():
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return SiteConfig.model_validate(raw)
    if site_id == DEFAULT_SITE_ID:
        return _builtin_vineyard_config()
    raise SiteConfigNotFound(f"site config not found: {path}")


__all__ = (
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_SITE_ID",
    "DockConfigEntry",
    "GeofenceConfig",
    "SiteConfig",
    "SiteConfigNotFound",
    "ThresholdConfig",
    "WeatherProviderConfig",
    "load_site_config",
)
