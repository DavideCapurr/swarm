from __future__ import annotations

import pytest
from pydantic import ValidationError

from sim.swarm_sim.external_events import CapacityAvailable
from sim.swarm_sim.faults import ExecutorFault


def test_capacity_available_cannot_name_a_response() -> None:
    with pytest.raises(ValidationError):
        CapacityAvailable.model_validate(
            {
                "agent_id": "sim-5",
                "role": "OVERWATCH",
                "reinforces_group_id": "group-1",
            }
        )


def test_executor_fault_cannot_name_recovery() -> None:
    with pytest.raises(ValidationError):
        ExecutorFault.model_validate(
            {
                "agent_id": "sim-2",
                "replacement_agent_id": "sim-5",
                "replacement_role": "PRIMARY_OBSERVER",
                "formation_radius_m": 30,
            }
        )
