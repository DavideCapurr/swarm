"""Run the conformance suite against every stub adapter.

Stubs are expected to skip the I/O-bearing scenarios but still satisfy the
structural Protocol check. This catches the day someone changes the Protocol
shape and forgets to update a stub.
"""

from __future__ import annotations

from adapters.autel import AutelAdapter
from adapters.dji_psdk import DJIPSDKAdapter
from adapters.parrot import ParrotAdapter
from adapters.skydio import SkydioAdapter
from adapters.tests.conformance import AdapterConformanceTests


class TestDJIPSDKConformance(AdapterConformanceTests):
    adapter_factory = staticmethod(lambda: DJIPSDKAdapter(agent_id="psdk-1"))
    is_stub = True


class TestAutelConformance(AdapterConformanceTests):
    adapter_factory = staticmethod(lambda: AutelAdapter(agent_id="autel-1"))
    is_stub = True


class TestParrotConformance(AdapterConformanceTests):
    adapter_factory = staticmethod(lambda: ParrotAdapter(agent_id="parrot-1"))
    is_stub = True


class TestSkydioConformance(AdapterConformanceTests):
    adapter_factory = staticmethod(lambda: SkydioAdapter(agent_id="skydio-1"))
    is_stub = True
