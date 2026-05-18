"""Phase 6.F — chaos probes.

These probes drive an external dependency (Redis, backend process) and
measure the recovery delta. They are not run by the default test suite;
they are invoked by ``scripts/chaos/*`` and by the ``make chaos-*``
targets so the operator can run them as a drone-day checklist item.
"""
