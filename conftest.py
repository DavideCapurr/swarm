"""Root conftest — ensures every package under the monorepo is importable when
running `pytest` from the repo root, even before `pip install -e .` has run.

In production (CI, `make setup`), the editable install in `pyproject.toml`
makes this redundant — but having it here means contributors can `pytest`
straight after clone with zero ceremony.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).parent

for sub in ("core", "adapters", "orchestrator", "sim", "backend", "."):
    p = ROOT / sub
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_configure(config: object) -> None:
    """Register local marks used by tests when external plugins are unavailable."""
    if hasattr(config, "addinivalue_line"):
        config.addinivalue_line("markers", "asyncio: mark test as async")


def pytest_pyfunc_call(pyfuncitem: object) -> bool | None:
    """Run async tests without requiring pytest-asyncio in constrained envs."""
    obj = getattr(pyfuncitem, "obj", None)
    if obj is None or not inspect.iscoroutinefunction(obj):
        return None

    funcargs = getattr(pyfuncitem, "funcargs", {})
    names = pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
    kwargs = {name: funcargs[name] for name in names}
    asyncio.run(obj(**kwargs))
    return True
