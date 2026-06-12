"""Phase 6.C — in-process JTI revocation list."""

from __future__ import annotations

import time

from backend.app.auth.revocation import (
    RevocationStore,
    get_revocation_store,
    set_revocation_store,
)


def test_revoked_jti_reported() -> None:
    store = RevocationStore()
    store.revoke("abc", expires_at=int(time.time()) + 3600)
    assert store.is_revoked("abc") is True


def test_unknown_jti_not_revoked() -> None:
    store = RevocationStore()
    assert store.is_revoked("never-seen") is False


def test_expired_revocation_is_swept() -> None:
    """An expired entry must not keep returning ``True`` — and we
    proactively delete it so the dict doesn't grow unbounded."""

    store = RevocationStore()
    store.revoke("dead", expires_at=int(time.time()) - 60)
    assert store.is_revoked("dead") is False
    assert len(store) == 0


def test_empty_jti_is_no_op() -> None:
    store = RevocationStore()
    store.revoke("", expires_at=int(time.time()) + 60)
    assert store.is_revoked("") is False
    assert len(store) == 0


def test_clear_drops_all() -> None:
    store = RevocationStore()
    store.revoke("a", expires_at=int(time.time()) + 60)
    store.revoke("b", expires_at=int(time.time()) + 60)
    store.clear()
    assert len(store) == 0


def test_gc_sweep_runs_periodically() -> None:
    """Hot path: revoke a lot of long-dead entries with a tiny GC interval
    so the periodic sweep happens during writes."""

    store = RevocationStore(gc_interval_s=0.0)
    for i in range(50):
        store.revoke(f"j-{i}", expires_at=int(time.time()) - 1)
    # GC has fired during the revokes; the dict is empty.
    assert len(store) == 0


def test_gc_sweeps_on_read_path() -> None:
    """A backend that stops issuing new revocations must still shed
    expired JTIs — reads trigger the periodic sweep too."""

    store = RevocationStore(gc_interval_s=0.0)
    # Inject directly: revoke() would sweep the expired entry on write.
    store._jtis["long-dead"] = time.time() - 60.0
    assert store.is_revoked("some-other-jti") is False
    assert len(store) == 0


def test_module_singleton_default_install() -> None:
    """`get_revocation_store()` lazily installs an in-memory store if none
    has been set explicitly."""

    set_revocation_store(None)
    s = get_revocation_store()
    assert isinstance(s, RevocationStore)
    # Same instance on subsequent calls.
    assert get_revocation_store() is s
