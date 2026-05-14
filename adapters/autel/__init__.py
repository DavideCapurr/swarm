"""Autel Robotics adapter — STUB.

Autel exposes an SDK for the EVO Max / EVO II Dual; integration uses Autel's
proprietary Cloud + on-aircraft API. Some Autel models also expose limited
MAVLink — for those, the `mavlink` adapter may apply.
"""

from adapters.autel.adapter import AutelAdapter

__all__ = ["AutelAdapter"]
