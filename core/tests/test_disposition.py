from __future__ import annotations

from swarm_core.disposition import compute_disposition
from swarm_core.messages import Geo


def test_disposition_expands_and_contracts_from_active_membership() -> None:
    center = Geo(lat=45.0, lon=9.0, alt_m=40.0)

    two = compute_disposition(center, ["PRIMARY", "OVERWATCH"])
    four = compute_disposition(
        center,
        ["PRIMARY", "SECONDARY", "OVERWATCH", "RELAY"],
    )

    assert two.active_members == 2
    assert four.active_members == 4
    assert four.radius_m > two.radius_m
    assert len(two.slots) == 2
    assert len(four.slots) == 4
    assert {slot.role for slot in four.slots} == {
        "PRIMARY",
        "SECONDARY",
        "OVERWATCH",
        "RELAY",
    }


def test_disposition_is_deterministic_and_agent_id_independent() -> None:
    center = Geo(lat=45.0, lon=9.0, alt_m=40.0)
    roles = ["PRIMARY", "SECONDARY", "OVERWATCH"]

    first = compute_disposition(center, roles)
    second = compute_disposition(center, roles)

    assert first == second
    assert all("agent" not in slot.role.lower() for slot in first.slots)
