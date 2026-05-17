"""Phase 6.D — structlog redactor processor tests.

Goal: a /auth/login call (or any code path) that logs a body containing
``password="secret123"`` must NOT produce a JSON line carrying the raw
``"secret123"`` string. The redactor is wired *as a structlog
processor*, so the renderer never sees the secret.
"""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog

from backend.app.observability.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
    redactor,
)


def _drain_stdlib_to_string(stream: io.StringIO) -> str:
    for h in logging.getLogger().handlers:
        h.flush()
    return stream.getvalue()


def test_redactor_scrubs_sensitive_keys() -> None:
    event = {
        "event": "auth attempt",
        "password": "secret123",
        "totp_code": "987654",
        "refresh_token": "fixture-refresh-token",
        "operator_id": "op-alice01",
    }
    out = redactor(None, "info", event.copy())
    assert out["password"] == "<redacted>"
    assert out["totp_code"] == "<redacted>"
    assert out["refresh_token"] == "<redacted>"
    # Non-sensitive keys passthrough.
    assert out["operator_id"] == "op-alice01"
    assert "secret123" not in json.dumps(out)


def test_redactor_strips_jwt_lookalike_from_strings() -> None:
    event = {
        "event": "incoming request",
        "auth_header_preview": "Bearer eyJhbGciOiJIUzI1NiJ9.AAAAAAAA.BBBBBBBB",
    }
    out = redactor(None, "info", event.copy())
    assert "eyJhbGciOiJIUzI1NiJ9" not in json.dumps(out)
    # Bearer keyword still present (we only scrub the JWT body).
    assert "Bearer" in out["auth_header_preview"]


def test_redactor_recurses_into_nested_dicts_and_lists() -> None:
    event = {
        "event": "structured body",
        "body": {
            "password": "secret123",
            "nested": [{"token": "abc.def.ghi"}, {"safe": "ok"}],
        },
    }
    out = redactor(None, "info", event.copy())
    rendered = json.dumps(out)
    assert "secret123" not in rendered
    assert "abc.def.ghi" not in rendered
    assert "ok" in rendered  # non-sensitive keys are preserved


def test_login_simulation_does_not_leak_password_to_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end: configure structlog, log a /auth/login body as kv
    pairs (the structured idiom), parse the rendered JSON, assert the
    password value is gone. Free-form `%s` interpolation is an author
    discipline issue the redactor can't fully solve — the structured
    path is the one ``backend/app/api/auth_routes.py`` uses."""

    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                redactor,
            ],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    configure_logging(force=True)
    root = logging.getLogger()
    root.addHandler(handler)

    bind_request_context(request_id="rid-login-1", path="/auth/login", method="POST")
    try:
        # Native structlog path
        logger = get_logger("backend.auth.routes")
        logger.info(
            "login attempt",
            operator_id="op-alice01",
            password="secret123",
            totp_code="123456",
        )

        # Stdlib path — kv-style via `extra=` carrying the body dict.
        stdlib_logger = logging.getLogger("test.stdlib")
        stdlib_logger.info(
            "login attempt",
            extra={"body": {"operator_id": "op-alice01", "password": "secret123"}},
        )
    finally:
        clear_request_context()

    # Drain both stdout (structlog native) and the stdlib handler buffer.
    import sys
    sys.stdout.flush()
    rendered = _drain_stdlib_to_string(buffer)
    captured = capsys.readouterr()
    combined = rendered + "\n" + captured.out
    assert "secret123" not in combined, combined
    assert "<redacted>" in combined


def test_jwt_pattern_scrubbed_from_freeform_message() -> None:
    """If a logger accidentally interpolates an access token into the
    message itself, the redactor still strips it."""

    fake_jwt = (
        "eyJhbGciOiJIUzI1NiJ9."
        "AAAAAAAAAAAAAA.BBBBBBBBBBBB"
    )
    event = {"event": f"observed token {fake_jwt} from client"}
    out = redactor(None, "info", event.copy())
    rendered = json.dumps(out)
    assert "AAAAAAAAAAAAAA" not in rendered
    assert "<redacted>" in rendered
