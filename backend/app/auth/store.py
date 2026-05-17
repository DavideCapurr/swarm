"""Operator identity store — YAML-backed for Phase 6.C.

Schema::

    operators:
      - operator_id: op-alice01
        password_hash: "pbkdf2_sha256$600000$<salt>$<hash>"
        role: commander
        mfa_secret: "BASE32SECRET..."   # required for role=commander
        disabled: false                  # optional

The file location defaults to ``infra/config/operators.yaml``; the env
var ``SWARM_OPERATORS_CONFIG`` overrides the path. A missing file is a
hard error in prod (caller hands the resulting ``OperatorStoreNotConfigured``
to FastAPI as a 503), so a misconfigured deploy fails closed.

The store is a swappable module-level singleton so tests can replace it
with an in-memory copy and the FastAPI lifespan can install the live one
from disk.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from backend.app.observability.logging import get_logger

logger = get_logger("backend.auth.store")

DEFAULT_OPERATORS_PATH = Path("infra/config/operators.yaml")
OPERATORS_CONFIG_ENV = "SWARM_OPERATORS_CONFIG"


class OperatorRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    COMMANDER = "commander"


# Strict hierarchy: a commander outranks an operator outranks a viewer.
# `require_role(role)` accepts the request iff the principal's rank is >=
# the required role's rank.
_ROLE_RANK: dict[OperatorRole, int] = {
    OperatorRole.VIEWER: 0,
    OperatorRole.OPERATOR: 1,
    OperatorRole.COMMANDER: 2,
}


def role_rank(role: OperatorRole) -> int:
    return _ROLE_RANK[role]


@dataclass(frozen=True)
class Operator:
    """One row of the identity store. ``password_hash`` and ``mfa_secret``
    never escape this module — only the API layer's ``Principal`` does."""

    operator_id: str
    password_hash: str
    role: OperatorRole
    mfa_secret: str | None = None
    disabled: bool = False


class OperatorStoreError(ValueError):
    """Raised when the YAML config is malformed."""


class OperatorStoreNotConfigured(RuntimeError):
    """Raised when no operator config is reachable and the store is queried."""


@dataclass
class OperatorStore:
    """Thread-safe in-memory store. Construct via `load_operator_store(...)`
    or by passing an explicit `operators=` dict for tests."""

    operators: dict[str, Operator] = field(default_factory=dict)
    path: Path | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ── Read API ───────────────────────────────────────────────────────────

    def get(self, operator_id: str) -> Operator | None:
        with self._lock:
            return self.operators.get(operator_id)

    def all(self) -> list[Operator]:
        with self._lock:
            return list(self.operators.values())

    # ── Mutators (tests + future admin tooling) ────────────────────────────

    def upsert(self, operator: Operator) -> None:
        with self._lock:
            self.operators[operator.operator_id] = operator

    def remove(self, operator_id: str) -> None:
        with self._lock:
            self.operators.pop(operator_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self.operators)


# ── YAML loader ────────────────────────────────────────────────────────────────


def _parse_operator(raw: Any, *, idx: int) -> Operator:
    if not isinstance(raw, dict):
        raise OperatorStoreError(f"operators[{idx}] is not a mapping")
    op_id = raw.get("operator_id")
    if not isinstance(op_id, str) or not op_id:
        raise OperatorStoreError(f"operators[{idx}].operator_id missing or empty")
    pw_hash = raw.get("password_hash")
    if not isinstance(pw_hash, str) or not pw_hash:
        raise OperatorStoreError(
            f"operators[{idx}].password_hash missing for operator {op_id!r}"
        )
    role_str = raw.get("role")
    if not isinstance(role_str, str):
        raise OperatorStoreError(
            f"operators[{idx}].role missing for operator {op_id!r}"
        )
    try:
        role = OperatorRole(role_str)
    except ValueError as exc:
        raise OperatorStoreError(
            f"operators[{idx}].role invalid for {op_id!r}: {role_str!r}"
        ) from exc
    mfa_secret = raw.get("mfa_secret")
    if mfa_secret is not None and not isinstance(mfa_secret, str):
        raise OperatorStoreError(
            f"operators[{idx}].mfa_secret must be a string for {op_id!r}"
        )
    if role is OperatorRole.COMMANDER and not mfa_secret:
        # Fail closed: a commander without TOTP would otherwise bypass MFA.
        raise OperatorStoreError(
            f"operators[{idx}] role=commander requires mfa_secret ({op_id!r})"
        )
    disabled_raw = raw.get("disabled", False)
    if not isinstance(disabled_raw, bool):
        raise OperatorStoreError(
            f"operators[{idx}].disabled must be a boolean for {op_id!r}"
        )

    # Reject any unexpected keys so a typo doesn't silently bypass a control.
    allowed = {"operator_id", "password_hash", "role", "mfa_secret", "disabled"}
    extras = set(raw.keys()) - allowed
    if extras:
        raise OperatorStoreError(
            f"operators[{idx}] has unsupported keys {sorted(extras)!r} ({op_id!r})"
        )

    return Operator(
        operator_id=op_id,
        password_hash=pw_hash,
        role=role,
        mfa_secret=mfa_secret,
        disabled=disabled_raw,
    )


def _read_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OperatorStoreError(f"cannot read operator config {path}: {exc}") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise OperatorStoreError(f"invalid YAML in {path}: {exc}") from exc


def load_operator_store(path: Path | str | None = None) -> OperatorStore:
    """Read + parse the operator YAML. ``path=None`` honours the env var.

    Returns an `OperatorStore` ready to install via ``set_operator_store``.
    Duplicate operator_ids are an error — the first occurrence is not
    silently overwritten."""

    if path is None:
        env_path = os.getenv(OPERATORS_CONFIG_ENV)
        resolved = Path(env_path) if env_path else DEFAULT_OPERATORS_PATH
    else:
        resolved = Path(path)
    if not resolved.exists():
        raise OperatorStoreError(f"operator config not found: {resolved}")
    raw = _read_yaml(resolved)
    if raw is None:
        raise OperatorStoreError(f"operator config is empty: {resolved}")
    if not isinstance(raw, dict):
        raise OperatorStoreError(
            f"operator config root must be a mapping in {resolved}"
        )
    rows = raw.get("operators")
    if not isinstance(rows, list):
        raise OperatorStoreError(
            f"operator config missing top-level 'operators' list in {resolved}"
        )
    out: dict[str, Operator] = {}
    for idx, row in enumerate(rows):
        op = _parse_operator(row, idx=idx)
        if op.operator_id in out:
            raise OperatorStoreError(
                f"duplicate operator_id {op.operator_id!r} in {resolved}"
            )
        out[op.operator_id] = op
    logger.info("operator store loaded: %d operator(s) from %s", len(out), resolved)
    return OperatorStore(operators=out, path=resolved)


# ── Module-level swappable singleton ───────────────────────────────────────────

_STORE: OperatorStore | None = None
_STORE_LOCK = threading.RLock()


def set_operator_store(store: OperatorStore | None) -> None:
    """Replace the active store. Pass ``None`` to disable auth (tests only)."""

    global _STORE
    with _STORE_LOCK:
        _STORE = store


def get_operator_store() -> OperatorStore:
    """Return the active store; raise ``OperatorStoreNotConfigured`` if unset."""

    with _STORE_LOCK:
        if _STORE is None:
            raise OperatorStoreNotConfigured(
                "operator store not configured — set SWARM_OPERATORS_CONFIG"
            )
        return _STORE


__all__ = (
    "DEFAULT_OPERATORS_PATH",
    "OPERATORS_CONFIG_ENV",
    "Operator",
    "OperatorRole",
    "OperatorStore",
    "OperatorStoreError",
    "OperatorStoreNotConfigured",
    "get_operator_store",
    "load_operator_store",
    "role_rank",
    "set_operator_store",
)
