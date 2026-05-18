"""Phase 6.I — compliance documentation invariants.

The retention numbers live in three places:

1. ``docs/compliance/retention.md`` (the canonical table).
2. The Phase 4 + Phase 6.I Alembic migrations.
3. The compliance endpoints (`backend/app/api/compliance.py`).

Drifting them apart is a real risk during refactors, so this test
asserts that the retention numbers stay in sync and that every new
file from §6.I is present, voice-clean, and linked from README.
"""

from __future__ import annotations

import re
from pathlib import Path

REQUIRED = [
    "docs/compliance/gdpr.md",
    "docs/compliance/retention.md",
    "docs/compliance/dpa-template.md",
    "docs/compliance/drone-regulations.md",
]
PHASE4_MIGRATION = (
    "backend/app/db/migrations/versions/20260516_0001_phase4_initial.py"
)
PHASE6I_MIGRATION = (
    "backend/app/db/migrations/versions/20260518_0002_phase6i_retention.py"
)
COMPLIANCE_ROUTER = "backend/app/api/compliance.py"

FORBIDDEN = (
    "Intruder",
    "Manual",
    "fly drone",
    "alarm",
    "red-alert",
    "red state",
)


def test_compliance_docs_exist() -> None:
    for rel in REQUIRED:
        assert Path(rel).is_file(), rel


def test_compliance_docs_are_voice_clean() -> None:
    for rel in REQUIRED:
        text = Path(rel).read_text()
        for word in FORBIDDEN:
            assert word not in text, f"forbidden word {word!r} in {rel}"


def test_retention_numbers_match_phase4_migration() -> None:
    """`telemetry` 30-day retention must appear in retention.md *and* in
    the Phase 4 migration that enforces it."""

    retention = Path("docs/compliance/retention.md").read_text()
    migration = Path(PHASE4_MIGRATION).read_text()
    # The doc lists 30 days for telemetry.
    assert re.search(r"telemetry.*30 days", retention, re.IGNORECASE)
    assert "INTERVAL '30 days'" in migration
    assert "add_retention_policy('telemetry'" in migration


def test_retention_numbers_match_phase6i_migration() -> None:
    """`events` 365-day retention must appear in retention.md *and* in
    the Phase 6.I migration that enforces it."""

    retention = Path("docs/compliance/retention.md").read_text()
    migration = Path(PHASE6I_MIGRATION).read_text()
    assert re.search(r"events.*365 days", retention, re.IGNORECASE)
    assert "365 days" in migration
    assert "add_retention_policy('events'" in migration


def test_retention_table_lists_operator_commands_7_years() -> None:
    retention = Path("docs/compliance/retention.md").read_text()
    # The phrase "7 years" must appear next to the operator_commands row.
    assert re.search(r"operator_commands.*7 years", retention, re.IGNORECASE)


def test_compliance_router_uses_canonical_phrase() -> None:
    """The double-confirmation phrase in the router matches the docs."""

    src = Path(COMPLIANCE_ROUTER).read_text()
    assert 'ERASURE_PHRASE = "ERASE OPERATOR DATA"' in src
    # Pseudonym prefix appears in retention.md *and* router.
    retention = Path("docs/compliance/retention.md").read_text()
    gdpr = Path("docs/compliance/gdpr.md").read_text()
    assert "op-erased-" in retention or "op-erased-" in gdpr
    assert 'ERASED_PREFIX = "op-erased-"' in src


def test_readme_lists_compliance_docs() -> None:
    readme = Path("README.md").read_text()
    # gdpr.md and drone-regulations.md were already listed in 6.H; the
    # two new files must be cited.
    assert "docs/compliance/retention.md" in readme
    assert "docs/compliance/dpa-template.md" in readme


def test_gdpr_doc_references_endpoints() -> None:
    """The Art. 15 / Art. 17 endpoint surface must be discoverable from
    the GDPR doc — that's how a controller wires a DSAR procedure."""

    gdpr = Path("docs/compliance/gdpr.md").read_text()
    assert "/admin/export" in gdpr
    assert "/admin/forget" in gdpr
    assert "Art. 15" in gdpr
    assert "Art. 17" in gdpr


def test_drone_regulations_doc_calls_out_responsibility() -> None:
    text = Path("docs/compliance/drone-regulations.md").read_text()
    # Responsibility split table must be there.
    assert "Operator" in text
    assert "SwarmOS" in text
    # Anti-overreach: SwarmOS does not certify the flight.
    assert "Operator is responsible" in text or "operator is responsible" in text.lower()
