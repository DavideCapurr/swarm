from __future__ import annotations

import pytest

from adapters.autel import AutelAdapter
from adapters.base import AdapterRegistry
from adapters.parrot import ParrotAdapter


def test_register_and_lookup_by_id() -> None:
    r = AdapterRegistry()
    a = AutelAdapter(agent_id="autel-1")
    r.register(a)
    assert len(r) == 1
    assert r.get("autel-1") is a


def test_double_register_raises() -> None:
    r = AdapterRegistry()
    r.register(AutelAdapter(agent_id="x"))
    with pytest.raises(ValueError):
        r.register(ParrotAdapter(agent_id="x"))


def test_unregister_idempotent() -> None:
    r = AdapterRegistry()
    r.register(AutelAdapter(agent_id="autel-1"))
    r.unregister("autel-1")
    r.unregister("autel-1")  # second call must not raise
    assert len(r) == 0


def test_all_returns_list() -> None:
    r = AdapterRegistry()
    r.register(AutelAdapter(agent_id="a"))
    r.register(ParrotAdapter(agent_id="b"))
    ids = sorted(a.agent_id for a in r.all())
    assert ids == ["a", "b"]
