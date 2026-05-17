"""Phase 6.C — operator store loader unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.auth.passwords import hash_password
from backend.app.auth.store import (
    Operator,
    OperatorRole,
    OperatorStore,
    OperatorStoreError,
    OperatorStoreNotConfigured,
    get_operator_store,
    load_operator_store,
    role_rank,
    set_operator_store,
)


@pytest.fixture()
def pw_hash() -> str:
    return hash_password("test-password", iterations=1_000)


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_role_hierarchy_is_strict() -> None:
    assert role_rank(OperatorRole.VIEWER) < role_rank(OperatorRole.OPERATOR)
    assert role_rank(OperatorRole.OPERATOR) < role_rank(OperatorRole.COMMANDER)


def test_load_three_role_store(tmp_path: Path, pw_hash: str) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-vw01
    password_hash: "{pw_hash}"
    role: viewer
  - operator_id: op-op01
    password_hash: "{pw_hash}"
    role: operator
  - operator_id: op-cm01
    password_hash: "{pw_hash}"
    role: commander
    mfa_secret: JBSWY3DPEHPK3PXP
""",
    )
    store = load_operator_store(yaml_path)
    assert len(store) == 3
    cm = store.get("op-cm01")
    assert cm is not None
    assert cm.role is OperatorRole.COMMANDER
    assert cm.mfa_secret == "JBSWY3DPEHPK3PXP"


def test_commander_without_mfa_secret_rejected(tmp_path: Path, pw_hash: str) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-cm01
    password_hash: "{pw_hash}"
    role: commander
""",
    )
    with pytest.raises(OperatorStoreError, match="mfa_secret"):
        load_operator_store(yaml_path)


def test_unknown_role_rejected(tmp_path: Path, pw_hash: str) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-x01
    password_hash: "{pw_hash}"
    role: god-mode
""",
    )
    with pytest.raises(OperatorStoreError):
        load_operator_store(yaml_path)


def test_duplicate_operator_id_rejected(tmp_path: Path, pw_hash: str) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-dup
    password_hash: "{pw_hash}"
    role: viewer
  - operator_id: op-dup
    password_hash: "{pw_hash}"
    role: operator
""",
    )
    with pytest.raises(OperatorStoreError, match="duplicate"):
        load_operator_store(yaml_path)


def test_unknown_keys_rejected(tmp_path: Path, pw_hash: str) -> None:
    """A typo'd key (e.g. `priviledges` instead of `role`) is a hard error
    so a control isn't silently dropped."""

    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-typo
    password_hash: "{pw_hash}"
    role: viewer
    priviledges: super
""",
    )
    with pytest.raises(OperatorStoreError, match="unsupported keys"):
        load_operator_store(yaml_path)


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(OperatorStoreError, match="not found"):
        load_operator_store(tmp_path / "missing.yaml")


def test_empty_file_rejected(tmp_path: Path) -> None:
    yaml_path = _write(tmp_path / "operators.yaml", "")
    with pytest.raises(OperatorStoreError):
        load_operator_store(yaml_path)


def test_malformed_top_level_rejected(tmp_path: Path) -> None:
    yaml_path = _write(tmp_path / "operators.yaml", "- not_a_mapping")
    with pytest.raises(OperatorStoreError, match="mapping"):
        load_operator_store(yaml_path)


def test_disabled_operator_flag(tmp_path: Path, pw_hash: str) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-disabled
    password_hash: "{pw_hash}"
    role: operator
    disabled: true
""",
    )
    store = load_operator_store(yaml_path)
    op = store.get("op-disabled")
    assert op is not None
    assert op.disabled is True


def test_disabled_must_be_boolean(tmp_path: Path, pw_hash: str) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-x
    password_hash: "{pw_hash}"
    role: operator
    disabled: "yes-please"
""",
    )
    with pytest.raises(OperatorStoreError):
        load_operator_store(yaml_path)


def test_get_operator_store_raises_when_unset() -> None:
    set_operator_store(None)
    with pytest.raises(OperatorStoreNotConfigured):
        get_operator_store()


def test_in_memory_store_upsert_and_remove() -> None:
    store = OperatorStore()
    op = Operator(
        operator_id="op-a",
        password_hash=hash_password("p", iterations=1_000),
        role=OperatorRole.OPERATOR,
    )
    store.upsert(op)
    assert store.get("op-a") is op
    store.remove("op-a")
    assert store.get("op-a") is None


def test_env_var_override(tmp_path: Path, pw_hash: str, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = tmp_path / "operators.yaml"
    _write(
        yaml_path,
        f"""
operators:
  - operator_id: op-vw01
    password_hash: "{pw_hash}"
    role: viewer
""",
    )
    monkeypatch.setenv("SWARM_OPERATORS_CONFIG", str(yaml_path))
    store = load_operator_store()  # no explicit path
    assert store.get("op-vw01") is not None
