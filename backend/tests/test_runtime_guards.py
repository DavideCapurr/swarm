"""Fail-closed runtime environment guards."""

from __future__ import annotations

import pytest

from backend.app.main import _apply_autonomy_baseline_from_env, _init_auth
from swarm_os import COORDINATOR


@pytest.mark.parametrize("env", ["prod", "production", "staging", "bench"])
def test_auth_disabled_rejected_in_prod_like_envs(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("SWARM_ENV", env)
    monkeypatch.setenv("SWARM_AUTH_DISABLED", "1")

    with pytest.raises(RuntimeError, match="SWARM_AUTH_DISABLED"):
        _init_auth()


def test_auth_disabled_still_allowed_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ENV", "dev")
    monkeypatch.setenv("SWARM_AUTH_DISABLED", "1")

    _init_auth()


@pytest.mark.parametrize("env", ["prod", "staging", "bench"])
def test_autonomy_baseline_rejected_outside_dev_like_envs(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("SWARM_ENV", env)
    monkeypatch.setenv("SWARM_AUTONOMY_BASELINE", "true")

    with pytest.raises(RuntimeError, match="SWARM_AUTONOMY_BASELINE"):
        _apply_autonomy_baseline_from_env()


def test_autonomy_baseline_allowed_in_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ENV", "test")
    monkeypatch.setenv("SWARM_AUTONOMY_BASELINE", "true")
    COORDINATOR.state.set_autonomy_enabled(False)

    _apply_autonomy_baseline_from_env()

    assert COORDINATOR.state.session.autonomy_enabled is True
    COORDINATOR.state.set_autonomy_enabled(False)
