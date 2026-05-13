"""Parrot adapter — STUB.

Parrot exposes the Olympe SDK (Python-native) for ANAFI / ANAFI Ai. ANAFI Ai also
natively supports ROS2 — if SWARM ever needs ROS2 inside the loop, Parrot is
where it surfaces first.
"""

from adapters.parrot.adapter import ParrotAdapter

__all__ = ["ParrotAdapter"]
