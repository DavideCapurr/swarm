"""Tests for the Phase 6.A safety primitives + site config loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from swarm_core.messages import RejectedReason

from swarm_os.safety import (
    BatteryThresholds,
    LinkThresholds,
    LocalStubWeatherProvider,
    PolicyDecision,
    SafetyAction,
    SafetyActionKind,
    WeatherProvider,
    WeatherThresholds,
)
from swarm_os.sites import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_SITE_ID,
    SiteConfig,
    SiteConfigNotFound,
    load_site_config,
)

# ── safety primitives ───────────────────────────────────────────────────────


def test_battery_thresholds_required_for_known_kinds() -> None:
    t = BatteryThresholds()
    assert t.required_for("PATROL") == 30.0
    assert t.required_for("VERIFY") == 40.0
    assert t.required_for("RTL_DOCK") == 15.0
    # unknown kinds default to the highest non-RTL bar
    assert t.required_for("COVER") == 40.0
    assert t.required_for("RELAY") == 40.0


def test_battery_thresholds_kind_is_case_insensitive() -> None:
    t = BatteryThresholds()
    assert t.required_for("patrol") == t.required_for("PATROL")


def test_battery_thresholds_validation_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        BatteryThresholds(patrol_min_pct=-1.0)


def test_link_thresholds_validation_clamps_zero_one() -> None:
    LinkThresholds(min_quality_for_mission=0.0, rtl_below_quality=0.0)
    LinkThresholds(min_quality_for_mission=1.0, rtl_below_quality=1.0)
    with pytest.raises(ValidationError):
        LinkThresholds(min_quality_for_mission=1.5)


def test_weather_thresholds_defaults() -> None:
    t = WeatherThresholds()
    assert t.max_wind_mps == 12.0
    assert t.min_visibility_km == 3.0


def test_policy_decision_helpers() -> None:
    ok = PolicyDecision.ok()
    assert ok.allowed is True
    assert ok.reason is None
    deny = PolicyDecision.deny(RejectedReason.OUTSIDE_GEOFENCE, "leg 2 exits")
    assert deny.allowed is False
    assert deny.reason is RejectedReason.OUTSIDE_GEOFENCE
    assert "leg 2" in deny.detail


def test_safety_action_dataclass_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    action = SafetyAction(
        agent_id="unit-001",
        kind=SafetyActionKind.AUTO_RTL,
        reason=RejectedReason.BATTERY_TOO_LOW,
        detail="battery 18%",
    )
    with pytest.raises(FrozenInstanceError):
        action.agent_id = "unit-002"  # type: ignore[misc]


async def test_local_stub_weather_provider_returns_benign_snapshot() -> None:
    provider = LocalStubWeatherProvider()
    snap = await provider.current("vineyard-01")
    assert snap.source == "stub"
    assert snap.wind_mps < 12.0
    assert snap.visibility_km > 3.0
    assert isinstance(provider, WeatherProvider)


# ── site config loader ─────────────────────────────────────────────────────


def test_load_site_config_default_when_yaml_missing(tmp_path: Path) -> None:
    cfg = load_site_config(DEFAULT_SITE_ID, config_dir=tmp_path)
    assert cfg.site_id == DEFAULT_SITE_ID
    assert len(cfg.geofence.polygon) >= 3
    assert any(d.primary for d in cfg.docks)


def test_load_site_config_unknown_site_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(SiteConfigNotFound):
        load_site_config("does-not-exist", config_dir=tmp_path)


def test_load_site_config_real_yaml_file_validates() -> None:
    """The committed vineyard-01.yaml must round-trip into SiteConfig."""
    cfg = load_site_config(DEFAULT_SITE_ID, config_dir=DEFAULT_CONFIG_DIR)
    assert cfg.site_id == DEFAULT_SITE_ID
    assert cfg.geofence.max_alt_m == 120.0
    assert cfg.thresholds.battery.patrol_min_pct == 30.0
    assert cfg.weather_provider.kind == "stub"
    assert cfg.docks[0].dock_id == "dock-langhe-01"


def test_load_site_config_rejects_extra_keys(tmp_path: Path) -> None:
    raw = {
        "site_id": "vineyard-01",
        "center": {"lat": 44.7, "lon": 8.03, "alt_m": 0.0},
        "geofence": {
            "polygon": [
                {"lat": 44.69, "lon": 8.02},
                {"lat": 44.69, "lon": 8.04},
                {"lat": 44.71, "lon": 8.04},
            ],
            "max_alt_m": 120.0,
        },
        "stowaway_key": "should_fail",  # not allowed by extra=forbid
    }
    yaml_path = tmp_path / "vineyard-01.yaml"
    yaml_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_site_config(DEFAULT_SITE_ID, config_dir=tmp_path)


def test_load_site_config_rejects_degenerate_polygon(tmp_path: Path) -> None:
    raw = {
        "site_id": "vineyard-01",
        "center": {"lat": 44.7, "lon": 8.03, "alt_m": 0.0},
        "geofence": {
            "polygon": [{"lat": 44.69, "lon": 8.02}, {"lat": 44.69, "lon": 8.04}],
            "max_alt_m": 120.0,
        },
    }
    yaml_path = tmp_path / "vineyard-01.yaml"
    yaml_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_site_config(DEFAULT_SITE_ID, config_dir=tmp_path)


def test_site_config_pydantic_frozen() -> None:
    """SiteConfig is loaded once at boot and treated as read-only at runtime."""
    cfg = load_site_config(DEFAULT_SITE_ID, config_dir=DEFAULT_CONFIG_DIR)
    assert isinstance(cfg, SiteConfig)
    with pytest.raises(ValidationError):
        cfg.site_id = "other"  # type: ignore[misc]
