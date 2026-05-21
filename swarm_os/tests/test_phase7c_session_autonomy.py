"""Phase 7.C — Session.autonomy_enabled boot-time gate.

Covers the three paths the Console reads to render the inline
``autonomy baseline`` chip on the HeadBar:

1. Default — neither the env var nor the scenario opt-in is set ⇒
   ``session.autonomy_enabled = False``.
2. Env var — ``SWARM_AUTONOMY_BASELINE=1`` flips both
   ``state.autonomy_enabled`` and ``session.autonomy_enabled`` at
   construction (mirrors the backend lifespan in ``main.py``).
3. Scenario YAML — the sim runner calls
   ``state.set_autonomy_enabled(True)`` when the scenario carries
   ``autonomy_baseline: true``; the helper propagates onto
   ``session.autonomy_enabled`` in lockstep.
"""

from __future__ import annotations

import pytest

from swarm_os.state import AUTONOMY_ENV, SwarmState


def test_session_autonomy_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env, no scenario ⇒ session.autonomy_enabled stays False."""

    monkeypatch.delenv(AUTONOMY_ENV, raising=False)
    state = SwarmState.vineyard()
    assert state.autonomy_enabled is False
    assert state.session.autonomy_enabled is False


def test_session_autonomy_env_var_flips_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """SWARM_AUTONOMY_BASELINE=1 ⇒ session.autonomy_enabled True at construction."""

    monkeypatch.setenv(AUTONOMY_ENV, "1")
    state = SwarmState.vineyard()
    assert state.autonomy_enabled is True
    assert state.session.autonomy_enabled is True


def test_session_autonomy_scenario_stamp_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sim runner path: set_autonomy_enabled mirrors onto session."""

    monkeypatch.delenv(AUTONOMY_ENV, raising=False)
    state = SwarmState.vineyard()
    assert state.session.autonomy_enabled is False

    state.set_autonomy_enabled(True)
    assert state.autonomy_enabled is True
    assert state.session.autonomy_enabled is True

    # The helper is bidirectional; an admin toggle (Phase 8.C) must also
    # be able to flip it back without leaving the session stale.
    state.set_autonomy_enabled(False)
    assert state.autonomy_enabled is False
    assert state.session.autonomy_enabled is False
