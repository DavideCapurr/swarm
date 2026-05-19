"""Phase 6.J — doc / wiring parity test.

Same shape as ``tests/test_phase6h_docs.py`` and
``tests/test_phase6i_compliance_docs.py``: greps the new files for
the canonical strings the plan landed on, so a rename or accidental
deletion fails the suite instead of being noticed at drone-day.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FORBIDDEN_WORDS = (
    "Intruder",
    "fly drone",
    "alarm",
    "red-alert",
    "red state",
)


ROOT = Path(__file__).resolve().parents[1]


# ── E2E scaffold ─────────────────────────────────────────────────────────────


def test_e2e_scaffold_exists() -> None:
    assert (ROOT / "tests" / "e2e" / "__init__.py").is_file()
    assert (ROOT / "tests" / "e2e" / "conftest.py").is_file()
    assert (ROOT / "tests" / "e2e" / "test_anomaly_lifecycle.py").is_file()


def test_e2e_uses_no_internal_mocks() -> None:
    """The roadmap says "tutti via API senza mock interni". Enforce it.

    The check ignores comments + docstrings: a sentence like
    "no ``unittest.mock`` here" inside a fixture docstring is not a
    code dependency on the mock surface. We pattern-match on the real
    code shape — `import unittest.mock`, `from unittest.mock import`,
    `from mock import`, `Mock(`, `MagicMock(` — at the start of a
    stripped line so that docstrings and comments don't trip the gate.
    """

    e2e_dir = ROOT / "tests" / "e2e"
    py_files = list(e2e_dir.glob("*.py"))
    assert py_files, "tests/e2e/ must contain at least one Python file"
    patterns = (
        re.compile(r"^\s*import\s+unittest\.mock\b"),
        re.compile(r"^\s*from\s+unittest\.mock\s+import\b"),
        re.compile(r"^\s*from\s+mock\s+import\b"),
        re.compile(r"^\s*import\s+mock\b"),
        # Constructed mocks anywhere on a code line (not in a docstring).
        re.compile(r"(?<![A-Za-z_.])Mock\s*\("),
        re.compile(r"(?<![A-Za-z_.])MagicMock\s*\("),
    )

    def _strip_comments_and_docstrings(text: str) -> str:
        # Collapse triple-quoted strings to a placeholder so we don't
        # match patterns inside docstrings. The simple regex is enough
        # for the tightly-scoped tests/e2e/ files.
        text = re.sub(r'"""[\s\S]*?"""', '""""""', text)
        text = re.sub(r"'''[\s\S]*?'''", "''''''", text)
        # Drop trailing `#` comments per line.
        return "\n".join(line.split("#", 1)[0] for line in text.splitlines())

    for path in py_files:
        code = _strip_comments_and_docstrings(path.read_text())
        for pattern in patterns:
            assert not pattern.search(code), (
                f"{path.relative_to(ROOT)} imports / constructs an internal "
                f"mock surface ({pattern.pattern})"
            )


def test_e2e_marker_registered_in_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    assert "tests/e2e" in text
    assert '"e2e:' in text


# ── Backend coverage gate ────────────────────────────────────────────────────


def test_coverage_fail_under_in_makefile() -> None:
    makefile = (ROOT / "Makefile").read_text()
    assert "--cov-fail-under=80" in makefile
    assert "--cov=backend" in makefile
    # Load + chaos samples deselected so coverage instrumentation does not
    # break their p95 SLO. Pin the spelling so a typo in the marker filter
    # doesn't silently re-include them.
    assert 'not load_smoke and not chaos' in makefile


def test_coverage_fail_under_in_ci() -> None:
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text()
    assert "--cov-fail-under=80" in workflow
    assert "--cov=backend" in workflow
    assert 'not load_smoke and not chaos' in workflow


def test_coverage_excludes_unhardware_paths() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "[tool.coverage.run]" in pyproject
    # Tests + sim + migrations + optional vendor adapters that need
    # external SDKs must stay out of the SUT measurement.
    for needle in ("tests/*", "sim/*", "*/migrations/*", "adapters/mavlink/*"):
        assert needle in pyproject


# ── Frontend Vitest ──────────────────────────────────────────────────────────


def test_frontend_has_vitest() -> None:
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    dev_deps = pkg.get("devDependencies", {})
    assert "vitest" in dev_deps
    assert "@vitest/coverage-v8" in dev_deps
    assert "@testing-library/react" in dev_deps
    scripts = pkg.get("scripts", {})
    assert "test" in scripts
    assert "vitest" in scripts["test"]


def test_frontend_vitest_config_includes_critical_path() -> None:
    config = (ROOT / "frontend" / "vitest.config.ts").read_text()
    # The five critical-path files the plan committed to.
    for path in (
        "lib/auth.tsx",
        "lib/api.ts",
        "lib/ws.ts",
        "components/EmergencyStop.tsx",
        "components/AuthGate.tsx",
    ):
        assert path in config


# ── Chaos workflow ───────────────────────────────────────────────────────────


def test_chaos_workflow_exists() -> None:
    path = ROOT / ".github" / "workflows" / "chaos-test.yml"
    assert path.is_file()
    text = path.read_text()
    # Monthly cron, off-window from load-test + image-scan.
    assert re.search(r'cron:\s*"23 6 1 \* \*"', text)
    assert "workflow_dispatch" in text
    # Both drills wired.
    assert "scripts/chaos/backend_kill.sh" in text
    assert "scripts/chaos/redis_pause.sh" in text


# ── ZAP baseline workflow ────────────────────────────────────────────────────


def test_zap_workflow_exists() -> None:
    path = ROOT / ".github" / "workflows" / "zap-baseline.yml"
    assert path.is_file()
    text = path.read_text()
    # Image digest-pinned (any sha256 reference under the zaproxy repo).
    assert re.search(r"ghcr\.io/zaproxy/zaproxy@sha256:[0-9a-f]{64}", text)
    # Post-step gate.
    assert "scripts/ci/zap_fail_on_high.py" in text
    # Triggers — PR + push + manual, no schedule (per the plan).
    assert "pull_request" in text
    assert "workflow_dispatch" in text
    assert "schedule:" not in text


def test_zap_fail_on_high_script_present_and_executable() -> None:
    path = ROOT / "scripts" / "ci" / "zap_fail_on_high.py"
    assert path.is_file()
    # Stdlib-only — no project deps in the post-step.
    text = path.read_text()
    for needle in ("import argparse", "import json", "import sys"):
        assert needle in text
    assert "third_party" not in text  # cheap canary


# ── Pen-test scope + operator acceptance ────────────────────────────────────


def test_pentest_scope_doc_exists_and_voice_clean() -> None:
    path = ROOT / "docs" / "security" / "pentest-scope.md"
    assert path.is_file()
    text = path.read_text()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"forbidden word {word!r} in {path}"
    # Anchors the plan called out so a rename triggers the test.
    for anchor in (
        "In scope",
        "Out of scope",
        "Credentials policy",
        "CVSS v3.1",
        "Remediation SLA",
        "Retest cycle",
    ):
        assert anchor in text


def test_operator_acceptance_doc_exists_and_voice_clean() -> None:
    path = ROOT / "docs" / "operator" / "acceptance.md"
    assert path.is_file()
    text = path.read_text()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"forbidden word {word!r} in {path}"
    # The 10-scenario rubric the plan promised.
    for scenario in ("Scenario A", "Scenario F", "Scenario G", "Scenario J"):
        assert scenario in text
    assert "Sign-off" in text


# ── Drone-day §2.J ───────────────────────────────────────────────────────────


def test_drone_day_lists_phase6j_items() -> None:
    path = ROOT / "docs" / "ops" / "drone-day-checklist.md"
    text = path.read_text()
    assert "### 2.J" in text
    # The four deferred field items the plan committed to.
    for needle in (
        "External pen-test executed",
        "Live operator acceptance",
        "ZAP prod scan",
        "Chaos prod drill",
    ):
        assert needle in text


# ── README docs map ──────────────────────────────────────────────────────────


def test_readme_links_new_docs() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "docs/operator/acceptance.md" in readme
    assert "docs/security/pentest-scope.md" in readme
