"""DJI Payload SDK (PSDK) adapter — STUB.

PSDK runs on an onboard SoC connected to the drone's E-Port or PSDK port. It is
the right interface when SWARM wants to ship its OWN compute/sensor payload
on top of a DJI airframe (e.g. an NVIDIA Jetson running smoke detection at the
edge).

Wiring this for real requires:
  - Onboard hardware (Jetson Nano/Orin or RPi CM4) with PSDK cable.
  - DJI PSDK 3.x C++ library cross-compiled for the SoC.
  - A Python ↔ PSDK bridge over IPC.

Commit-1: stub with the right shape. Methods raise NotImplementedError.
"""

from adapters.dji_psdk.adapter import DJIPSDKAdapter

__all__ = ["DJIPSDKAdapter"]
