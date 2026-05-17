"""JTI revocation list.

Phase 6.C ships an in-process implementation: a dict keyed by ``jti``
with a unix timestamp expiry, periodically swept. The roadmap pins the
Redis-backed implementation to 6.E together with the rest of the secure
bus rollout — same wire (``rediss://``) and same mTLS material. Until
then we keep the surface area minimal but the API stable so the swap is
contained to this module.

The store is intentionally not a global to keep tests isolated; the
FastAPI lifespan installs a process-wide instance via
``set_revocation_store``.
"""

from __future__ import annotations

import threading
import time

DEFAULT_GC_INTERVAL_S = 60.0


class RevocationStore:
    """In-memory ``jti -> expires_at`` map. Thread-safe."""

    def __init__(self, *, gc_interval_s: float = DEFAULT_GC_INTERVAL_S) -> None:
        self._jtis: dict[str, float] = {}
        self._lock = threading.RLock()
        self._last_gc: float = time.monotonic()
        self._gc_interval_s = gc_interval_s

    # ── Mutators ────────────────────────────────────────────────────────────

    def revoke(self, jti: str, *, expires_at: int) -> None:
        if not jti:
            return
        with self._lock:
            self._jtis[jti] = float(expires_at)
            self._maybe_gc_locked()

    def is_revoked(self, jti: str, *, now: float | None = None) -> bool:
        if not jti:
            return False
        wall = float(now if now is not None else time.time())
        with self._lock:
            exp = self._jtis.get(jti)
            if exp is None:
                return False
            if exp <= wall:
                # Already expired — clean it up but answer False; an expired
                # token would fail JWT verification too.
                self._jtis.pop(jti, None)
                return False
            return True

    def clear(self) -> None:
        with self._lock:
            self._jtis.clear()

    # ── Maintenance ─────────────────────────────────────────────────────────

    def _maybe_gc_locked(self) -> None:
        now_mono = time.monotonic()
        if now_mono - self._last_gc < self._gc_interval_s:
            return
        wall = time.time()
        self._jtis = {j: e for j, e in self._jtis.items() if e > wall}
        self._last_gc = now_mono

    def __len__(self) -> int:
        with self._lock:
            return len(self._jtis)


# ── Module-level swappable singleton ───────────────────────────────────────────

_STORE: RevocationStore | None = None
_STORE_LOCK = threading.RLock()


def set_revocation_store(store: RevocationStore | None) -> None:
    global _STORE
    with _STORE_LOCK:
        _STORE = store


def get_revocation_store() -> RevocationStore:
    """Return the installed store; build a fresh in-memory one if absent.

    The lazy fallback keeps test imports trivial — production code installs
    the real store explicitly at boot."""

    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = RevocationStore()
        return _STORE


__all__ = (
    "DEFAULT_GC_INTERVAL_S",
    "RevocationStore",
    "get_revocation_store",
    "set_revocation_store",
)
