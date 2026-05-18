"""Phase 6.F — load + scale tests.

Two layers:
  - ``test_load_inproc.py`` runs entirely in-process against the real
    ``BusConsumer`` + ``InMemoryBus`` + a fake WS hub. Cheap, deterministic,
    runs on every push as a smoke (``-m load_smoke``).
  - ``driver.py`` is a stand-alone client (``python -m tests.load.driver``)
    that hits a live backend over REST + WS. Used by ``make load-soak``
    and the weekly CI workflow.

No new dependencies. ``httpx`` + ``websockets`` are already core deps in
``pyproject.toml`` (see Phase 6.F plan §Decisioni chiave #1).
"""
