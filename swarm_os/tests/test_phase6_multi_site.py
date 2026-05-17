"""Phase 6.B — site-aware bootstrap tests.

Cover SwarmState.from_site_config wiring, SWARM_SITE_ID env handling, and
the docks-from-config materialization. Hot-reload + admin endpoint tests
live alongside the backend in `backend/tests/test_phase6_admin.py`.
"""

from __future__ import annotations

import os

import pytest
from swarm_core.messages import Geo

from swarm_os.policy import PolicyEngine
from swarm_os.sites import (
    DockConfigEntry,
    GeofenceConfig,
    SiteConfig,
    ThresholdConfig,
    WeatherProviderConfig,
    load_site_config,
)
from swarm_os.state import SITE_ID_ENV, SwarmState


def _custom_site(
    *, site_id: str, primary_dock: str, secondary_dock: str | None = None
) -> SiteConfig:
    polygon = [
        Geo(lat=40.0, lon=-3.0),
        Geo(lat=40.0, lon=-2.9),
        Geo(lat=40.1, lon=-2.9),
        Geo(lat=40.1, lon=-3.0),
    ]
    docks = [DockConfigEntry(dock_id=primary_dock, primary=True)]
    if secondary_dock is not None:
        docks.append(DockConfigEntry(dock_id=secondary_dock, primary=False))
    return SiteConfig(
        site_id=site_id,
        name="custom",
        center=Geo(lat=40.05, lon=-2.95, alt_m=0.0),
        geofence=GeofenceConfig(polygon=polygon, max_alt_m=80.0),
        thresholds=ThresholdConfig(),
        weather_provider=WeatherProviderConfig(kind="stub"),
        docks=docks,
    )


def test_from_site_config_propagates_site_id() -> None:
    cfg = _custom_site(site_id="ranch-01", primary_dock="dock-ranch-a")
    state = SwarmState.from_site_config(cfg)
    assert state.session.site_id == "ranch-01"


def test_from_site_config_materializes_docks_from_config() -> None:
    cfg = _custom_site(
        site_id="ranch-01",
        primary_dock="dock-ranch-a",
        secondary_dock="dock-ranch-b",
    )
    state = SwarmState.from_site_config(cfg)
    assert set(state.docks) == {"dock-ranch-a", "dock-ranch-b"}
    assert state.docks["dock-ranch-a"].primary is True
    assert state.docks["dock-ranch-b"].primary is False
    # The primary dock keeps the legacy default capacity. A secondary dock
    # starts empty until units are assigned at runtime.
    assert state.docks["dock-ranch-a"].units_total == 3
    assert state.docks["dock-ranch-b"].units_total == 0


def test_from_site_config_binds_policy_to_site() -> None:
    cfg = _custom_site(site_id="ranch-01", primary_dock="dock-ranch-a")
    state = SwarmState.from_site_config(cfg)
    assert isinstance(state.policy, PolicyEngine)
    assert state.policy.site.site_id == "ranch-01"
    assert state.policy.site.geofence.max_alt_m == 80.0


def test_from_site_config_grid_uses_site_center() -> None:
    cfg = _custom_site(site_id="ranch-01", primary_dock="dock-ranch-a")
    state = SwarmState.from_site_config(cfg)
    # Sector centroids are bounded by ±half_extent_m (≈600 m) of center; check
    # that they're at least near the ranch lat instead of the vineyard 44.7.
    centroids = [s.centroid for s in state.sectors.values()]
    assert all(39.99 < c.lat < 40.11 for c in centroids)


def test_vineyard_legacy_factory_still_returns_vineyard_site() -> None:
    """Backward-compat smoke test — Phase 1+ tests rely on this default."""

    state = SwarmState.vineyard()
    assert state.session.site_id == "vineyard-01"
    assert "dock-langhe-01" in state.docks


@pytest.fixture()
def restore_site_env() -> None:
    """Tests that touch SWARM_SITE_ID must clean up so others stay stable."""

    return None  # pytest's monkeypatch handles teardown


def test_vineyard_factory_honours_swarm_site_id_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """SWARM_SITE_ID=missing-site must reach load_site_config and raise.

    This is the actual contract: SWARM_SITE_ID is parsed by vineyard() and
    handed to load_site_config(); if the file isn't on disk and the id is
    not the default, the loader fails closed. We exercise the
    bootstrap-time selection path without polluting the working dir.
    """

    monkeypatch.setenv(SITE_ID_ENV, "no-such-site")
    with pytest.raises(LookupError):
        SwarmState.vineyard()


def test_vineyard_factory_uses_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(SITE_ID_ENV, raising=False)
    state = SwarmState.vineyard()
    assert state.session.site_id == "vineyard-01"


def test_vineyard_factory_uses_default_when_env_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty SWARM_SITE_ID must not silently load the wrong site."""

    monkeypatch.setenv(SITE_ID_ENV, "")
    # os.getenv returns "" → load_site_config("") tries to load <dir>/.yaml,
    # finds nothing, and falls back only for the literal default. Empty
    # string is NOT the default, so this raises.
    with pytest.raises(LookupError):
        SwarmState.vineyard()


def test_site_id_env_constant_matches_documented_name() -> None:
    """The drone-day checklist references SWARM_SITE_ID — keep them in sync."""

    assert SITE_ID_ENV == "SWARM_SITE_ID"


def test_load_site_config_with_custom_dir(tmp_path: object) -> None:
    """Phase 6.B will let ops drop a new YAML into infra/config/sites/;
    the loader must read from any directory the admin endpoint hands it."""

    from pathlib import Path

    site_dir = Path(str(tmp_path)) / "sites"
    site_dir.mkdir()
    (site_dir / "ranch-99.yaml").write_text(
        """
site_id: ranch-99
name: "Test Ranch"
center: {lat: 40.0, lon: -3.0, alt_m: 0.0}
geofence:
  polygon:
    - {lat: 40.0, lon: -3.0}
    - {lat: 40.1, lon: -3.0}
    - {lat: 40.1, lon: -2.9}
  max_alt_m: 80.0
""",
        encoding="utf-8",
    )
    cfg = load_site_config("ranch-99", config_dir=site_dir)
    assert cfg.site_id == "ranch-99"
    assert cfg.geofence.max_alt_m == 80.0


def teardown_module(module: object) -> None:
    """If a test forgot to clean up SWARM_SITE_ID, restore the env so the
    rest of the suite (which reads the var via swarm_os.__init__) is not
    poisoned. monkeypatch normally handles this; this is belt-and-suspenders.
    """

    os.environ.pop(SITE_ID_ENV, None)
