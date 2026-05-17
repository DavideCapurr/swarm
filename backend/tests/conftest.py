"""Shared backend test fixtures.

Phase 4 introduces an aiosqlite-backed persistence fixture so the repository
+ history endpoints can be exercised without a Postgres daemon.

Phase 6.C adds JWT + operator-store fixtures: ``auth_env`` installs a
short-lived JWT service and a three-row in-memory operator store
(viewer / operator / commander) into the auth singletons, and the
``viewer_headers`` / ``operator_headers`` / ``commander_headers``
fixtures hand back ``Authorization: Bearer …`` headers ready for the
TestClient.

Every backend test imports these fixtures via this conftest by default;
the auth fixture is autouse so a stray ``Depends(require_role)`` in the
route under test always has a working JWT service to talk to.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.auth import (
    JWTService,
    Operator,
    OperatorRole,
    OperatorStore,
    RevocationStore,
    TokenType,
    generate_totp_secret,
    hash_password,
    set_jwt_service,
    set_operator_store,
    set_revocation_store,
)
from backend.app.db.models import Base
from backend.app.db.repository import Repository

TEST_JWT_SECRET = b"swarm-test-jwt-secret-not-for-prod-32+"
TEST_VIEWER_ID = "op-viewer01"
TEST_OPERATOR_ID = "op-operator01"
TEST_COMMANDER_ID = "op-commander01"
TEST_PASSWORD = "swarm-test-password-1234"


@pytest_asyncio.fixture
async def memory_repository() -> AsyncIterator[Repository]:
    """Repository bound to an in-memory aiosqlite engine.

    Each test gets its own engine so writes never leak between tests.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield Repository(sm)
    await engine.dispose()


@pytest.fixture
def disabled_repository() -> Repository:
    """Repository with no sessionmaker — every write becomes a no-op."""
    return Repository(None)


# ── Phase 6.C — auth fixtures ──────────────────────────────────────────────────


@pytest.fixture
def test_totp_secret() -> str:
    """Stable per-test TOTP secret so commander login tests can mint codes."""
    return generate_totp_secret()


@pytest.fixture(autouse=True)
def auth_env(test_totp_secret: str) -> Iterator[dict[str, Any]]:
    """Install a JWT service + operator store + revocation list for every test.

    The store has three operators: viewer / operator / commander. The
    commander row carries an MFA secret so commander-only tests can
    exercise the TOTP path. The revocation list is fresh per-test.
    """

    service = JWTService(secret=TEST_JWT_SECRET)
    set_jwt_service(service)
    pw_hash = hash_password(TEST_PASSWORD, iterations=1_000)
    operators = {
        TEST_VIEWER_ID: Operator(
            operator_id=TEST_VIEWER_ID,
            password_hash=pw_hash,
            role=OperatorRole.VIEWER,
        ),
        TEST_OPERATOR_ID: Operator(
            operator_id=TEST_OPERATOR_ID,
            password_hash=pw_hash,
            role=OperatorRole.OPERATOR,
        ),
        TEST_COMMANDER_ID: Operator(
            operator_id=TEST_COMMANDER_ID,
            password_hash=pw_hash,
            role=OperatorRole.COMMANDER,
            mfa_secret=test_totp_secret,
        ),
    }
    store = OperatorStore(operators=operators)
    set_operator_store(store)
    set_revocation_store(RevocationStore())
    yield {
        "service": service,
        "store": store,
        "viewer_id": TEST_VIEWER_ID,
        "operator_id": TEST_OPERATOR_ID,
        "commander_id": TEST_COMMANDER_ID,
        "password": TEST_PASSWORD,
        "totp_secret": test_totp_secret,
    }
    # Reset for the next test.
    set_jwt_service(None)
    set_operator_store(None)
    set_revocation_store(None)


@pytest.fixture
def token_factory(
    auth_env: dict[str, Any],
) -> Callable[..., str]:
    """Return ``factory(role, operator_id=None, mfa=None, token_type=ACCESS, site_id="vineyard-01")``."""

    service: JWTService = auth_env["service"]

    def _factory(
        role: OperatorRole | str = OperatorRole.OPERATOR,
        *,
        operator_id: str | None = None,
        mfa: bool | None = None,
        token_type: TokenType = TokenType.ACCESS,
        site_id: str = "vineyard-01",
    ) -> str:
        r = OperatorRole(role) if isinstance(role, str) else role
        default_id = {
            OperatorRole.VIEWER: TEST_VIEWER_ID,
            OperatorRole.OPERATOR: TEST_OPERATOR_ID,
            OperatorRole.COMMANDER: TEST_COMMANDER_ID,
        }[r]
        op_id = operator_id or default_id
        mfa_v = mfa if mfa is not None else (r is OperatorRole.COMMANDER)
        token, _ = service.issue(
            operator_id=op_id,
            role=r,
            site_id=site_id,
            mfa=mfa_v,
            token_type=token_type,
        )
        return token

    return _factory


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers(token_factory: Callable[..., str]) -> dict[str, str]:
    return _headers(token_factory(OperatorRole.VIEWER))


@pytest.fixture
def operator_headers(token_factory: Callable[..., str]) -> dict[str, str]:
    return _headers(token_factory(OperatorRole.OPERATOR))


@pytest.fixture
def commander_headers(token_factory: Callable[..., str]) -> dict[str, str]:
    return _headers(token_factory(OperatorRole.COMMANDER, mfa=True))


@pytest.fixture
def commander_headers_no_mfa(
    token_factory: Callable[..., str],
) -> dict[str, str]:
    """Commander principal whose access token has ``mfa=False`` — the
    commander-only routes must still reject it."""
    return _headers(token_factory(OperatorRole.COMMANDER, mfa=False))
