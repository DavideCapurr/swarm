"""Root conftest — ensures every package under the monorepo is importable when
running `pytest` from the repo root, even before `pip install -e .` has run.

In production (CI, `make setup`), the editable install in `pyproject.toml`
makes this redundant — but having it here means contributors can `pytest`
straight after clone with zero ceremony.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent

for sub in ("core", "adapters", "orchestrator", "sim", "backend"):
    p = ROOT / sub
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
