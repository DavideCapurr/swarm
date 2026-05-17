"""Phase 6.B — admin reload endpoint tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.admin import (
    ADMIN_TOKEN_ENV,
    ADMIN_TOKEN_HEADER,
)
from backend.app.api.admin import (
    router as admin_router,
)
from swarm_os import SWARM_STATE


@pytest.fixture()
def site_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Lay down two site configs in a temp dir and point the loader at it.

    The default loader reads `infra/config/sites/<id>.yaml`; tests override
    DEFAULT_CONFIG_DIR by monkeypatching the env or the constant. The
    cleanest path is to write the YAMLs in the canonical repo location via
    a monkeypatch on the module constant.
    """

    site_dir = tmp_path / "sites"
    site_dir.mkdir()
    (site_dir / "vineyard-01.yaml").write_text(
        """
site_id: vineyard-01
name: "Vineyard (test override)"
center: {lat: 44.7, lon: 8.03, alt_m: 0.0}
geofence:
  polygon:
    - {lat: 44.69, lon: 8.02}
    - {lat: 44.69, lon: 8.04}
    - {lat: 44.71, lon: 8.04}
    - {lat: 44.71, lon: 8.02}
  max_alt_m: 120.0
weather_provider:
  kind: stub
  refresh_interval_s: 300
docks:
  - dock_id: dock-langhe-01
    primary: true
""",
        encoding="utf-8",
    )
    (site_dir / "ranch-02.yaml").write_text(
        """
site_id: ranch-02
name: "Ranch 02 (test)"
center: {lat: 40.0, lon: -3.0, alt_m: 0.0}
geofence:
  polygon:
    - {lat: 39.99, lon: -3.01}
    - {lat: 39.99, lon: -2.99}
    - {lat: 40.01, lon: -2.99}
    - {lat: 40.01, lon: -3.01}
  max_alt_m: 90.0
weather_provider:
  kind: stub
  refresh_interval_s: 300
docks:
  - dock_id: dock-ranch-a
    primary: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("swarm_os.sites.DEFAULT_CONFIG_DIR", site_dir)
    return site_dir


def _client() -> TestClient:
    SWARM_STATE.events.clear()
    app = FastAPI()
    app.include_router(admin_router)
    return TestClient(app)


def test_reload_returns_503_when_admin_disabled(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ADMIN_TOKEN_ENV, raising=False)
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "admin_disabled"


def test_reload_returns_503_when_admin_token_empty(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers={ADMIN_TOKEN_HEADER: "anything"},
    )
    assert resp.status_code == 503


def test_reload_returns_401_on_missing_token(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_admin_token"


def test_reload_returns_401_on_wrong_token(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers={ADMIN_TOKEN_HEADER: "wrong"},
    )
    assert resp.status_code == 401


def test_reload_returns_404_on_unknown_site(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "does-not-exist"},
        headers={ADMIN_TOKEN_HEADER: "s3cret"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "site_config_not_found"


def test_reload_rejects_invalid_site_id_pattern(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`extra="forbid"` blocks malformed bodies; the regex rejects path-traversal
    attempts before the loader sees a tainted string."""

    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "../etc/passwd"},
        headers={ADMIN_TOKEN_HEADER: "s3cret"},
    )
    assert resp.status_code == 422


def test_reload_succeeds_and_swaps_policy(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "ranch-02"},
        headers={ADMIN_TOKEN_HEADER: "s3cret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["site_id"] == "ranch-02"
    assert body["previous_site_id"] != "ranch-02"
    # The policy engine on the shared state must be bound to the new site.
    assert SWARM_STATE.policy.site.site_id == "ranch-02"
    assert SWARM_STATE.session.site_id == "ranch-02"
    # An audit event was appended.
    event_ids = [e.id for e in SWARM_STATE.events]
    assert body["event_id"] in event_ids


def test_reload_back_to_same_site_keeps_sectors_intact(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reloading the current site is a refresh, not a relocation — the
    sector grid must remain in place so coverage history is preserved."""

    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    # Force the state to vineyard-01 first.
    client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers={ADMIN_TOKEN_HEADER: "s3cret"},
    )
    before_sectors = set(SWARM_STATE.sectors)
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers={ADMIN_TOKEN_HEADER: "s3cret"},
    )
    assert resp.status_code == 200
    assert set(SWARM_STATE.sectors) == before_sectors


def test_reload_preserves_weather_provider_binding(
    site_yaml: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reload swaps SiteConfig, not the WeatherProvider. A site-specific
    provider plugged in at boot must survive a config reload — otherwise
    every reload would regress to the stub."""

    class _Marker:
        async def current(self, site_id: str) -> object:  # pragma: no cover
            raise RuntimeError("marker should never be called by these tests")

    marker = _Marker()
    SWARM_STATE.policy.weather_provider = marker  # type: ignore[assignment]
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "s3cret")
    client = _client()
    resp = client.post(
        "/admin/reload-site-config",
        json={"site_id": "ranch-02"},
        headers={ADMIN_TOKEN_HEADER: "s3cret"},
    )
    assert resp.status_code == 200
    assert SWARM_STATE.policy.weather_provider is marker  # type: ignore[comparison-overlap]


def teardown_module(module: object) -> None:
    """Restore the global SWARM_STATE to a vineyard-01 default so the rest
    of the suite (which assumes that baseline) is not poisoned."""

    from swarm_os.policy import PolicyEngine
    from swarm_os.safety import LocalStubWeatherProvider
    from swarm_os.sectors import default_sector_grid
    from swarm_os.sites import load_site_config
    from swarm_os.state import VINEYARD_CENTER

    cfg = load_site_config("vineyard-01")
    SWARM_STATE.policy = PolicyEngine(cfg, LocalStubWeatherProvider())
    SWARM_STATE.session = SWARM_STATE.session.model_copy(
        update={"site_id": "vineyard-01"}
    )
    SWARM_STATE.sectors = {
        s.id: s for s in default_sector_grid(VINEYARD_CENTER)
    }
    SWARM_STATE.events.clear()
