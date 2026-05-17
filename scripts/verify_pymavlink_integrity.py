#!/usr/bin/env python3
"""Offline pymavlink package-integrity gate.

This intentionally does not call PyPI or Sigstore services. It verifies the
local supply-chain controls that can run reliably in CI/local audit:

1. `uv.lock` pins pymavlink to a PyPI registry artifact with sha256 hashes for
   the sdist and every wheel.
2. `pyproject.toml` keeps pymavlink in the explicit MAVLink optional extra.
3. The installed pymavlink distribution matches the locked version, and every
   sha256 entry in its wheel RECORD still matches the file on disk.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.metadata
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PYPI_REGISTRY = "https://pypi.org/simple"
PYTHONHOSTED_PREFIX = "https://files.pythonhosted.org/packages/"


class IntegrityError(RuntimeError):
    """Raised when the integrity gate finds a hard failure."""


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _assert_hash(value: str, *, label: str) -> None:
    if not HASH_RE.match(value):
        raise IntegrityError(f"{label} is missing a sha256 lock hash")


def _assert_pythonhosted(url: str, *, label: str) -> None:
    if not url.startswith(PYTHONHOSTED_PREFIX):
        raise IntegrityError(f"{label} is not a PyPI-hosted artifact: {url}")


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = version.split(".")
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise IntegrityError(f"unexpected pymavlink version: {version}") from exc


def verify_lock(root: Path) -> dict[str, Any]:
    lock = _load_toml(root / "uv.lock")
    packages = [pkg for pkg in lock.get("package", []) if pkg.get("name") == "pymavlink"]
    if len(packages) != 1:
        raise IntegrityError(f"expected exactly one pymavlink package in uv.lock, got {len(packages)}")
    package = packages[0]
    version = str(package.get("version", ""))
    if not (_version_tuple("2.4.40") <= _version_tuple(version) < _version_tuple("3")):
        raise IntegrityError(f"locked pymavlink version is outside policy range: {version}")

    source = package.get("source")
    if not isinstance(source, dict) or source.get("registry") != PYPI_REGISTRY:
        raise IntegrityError("pymavlink must resolve from the public PyPI registry")

    sdist = package.get("sdist")
    if not isinstance(sdist, dict):
        raise IntegrityError("pymavlink sdist entry missing from uv.lock")
    _assert_pythonhosted(str(sdist.get("url", "")), label="pymavlink sdist")
    _assert_hash(str(sdist.get("hash", "")), label="pymavlink sdist")

    wheels = package.get("wheels")
    if not isinstance(wheels, list) or not wheels:
        raise IntegrityError("pymavlink wheel entries missing from uv.lock")
    for idx, wheel in enumerate(wheels):
        if not isinstance(wheel, dict):
            raise IntegrityError(f"pymavlink wheel entry {idx} is malformed")
        _assert_pythonhosted(str(wheel.get("url", "")), label=f"pymavlink wheel {idx}")
        _assert_hash(str(wheel.get("hash", "")), label=f"pymavlink wheel {idx}")

    return {
        "version": version,
        "sdist_hash": sdist["hash"],
        "wheel_count": len(wheels),
    }


def verify_pyproject(root: Path) -> None:
    pyproject = _load_toml(root / "pyproject.toml")
    extras = pyproject.get("project", {}).get("optional-dependencies", {})
    mavlink = extras.get("mavlink", [])
    normalized = {str(item).replace(" ", "") for item in mavlink}
    if "pymavlink>=2.4.40,<3" not in normalized:
        raise IntegrityError("pyproject.toml mavlink extra must pin pymavlink>=2.4.40,<3")


def verify_installed_distribution(expected_version: str) -> dict[str, int | str]:
    try:
        dist = importlib.metadata.distribution("pymavlink")
    except importlib.metadata.PackageNotFoundError as exc:
        raise IntegrityError("pymavlink is not installed in this Python environment") from exc
    if dist.version != expected_version:
        raise IntegrityError(
            f"installed pymavlink version {dist.version} does not match uv.lock {expected_version}"
        )
    files = list(dist.files or [])
    record = next((path for path in files if str(path).endswith(".dist-info/RECORD")), None)
    if record is None:
        raise IntegrityError("installed pymavlink RECORD file is missing")

    checked = 0
    unhashed = 0
    with dist.locate_file(record).open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) < 3:
                raise IntegrityError(f"malformed RECORD row: {row!r}")
            rel_path, hash_spec, _size = row
            if not hash_spec:
                unhashed += 1
                continue
            algo, sep, encoded = hash_spec.partition("=")
            if sep != "=":
                raise IntegrityError(f"malformed RECORD hash for {rel_path}")
            if algo != "sha256":
                raise IntegrityError(f"unexpected RECORD hash algorithm {algo!r} for {rel_path}")
            file_path = dist.locate_file(rel_path)
            if not file_path.is_file():
                raise IntegrityError(f"installed file listed in RECORD is missing: {rel_path}")
            digest = base64.urlsafe_b64encode(hashlib.sha256(file_path.read_bytes()).digest())
            actual = digest.decode("ascii").rstrip("=")
            if actual != encoded:
                raise IntegrityError(f"RECORD sha256 mismatch for {rel_path}")
            checked += 1
    if checked == 0:
        raise IntegrityError("pymavlink RECORD did not contain any sha256-protected files")
    return {"installed_version": dist.version, "record_hashes_checked": checked, "unhashed": unhashed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock-only",
        action="store_true",
        help="validate uv.lock/pyproject only; skip installed RECORD verification",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable summary")
    args = parser.parse_args()

    try:
        lock_summary = verify_lock(ROOT)
        verify_pyproject(ROOT)
        installed_summary: dict[str, int | str] = {}
        if not args.lock_only:
            installed_summary = verify_installed_distribution(str(lock_summary["version"]))
    except IntegrityError as exc:
        print(f"pymavlink integrity: FAIL: {exc}", file=sys.stderr)
        return 1

    summary: dict[str, Any] = {
        "status": "pass",
        "package": "pymavlink",
        "lock": lock_summary,
        "installed": installed_summary or "skipped",
        "network": "not used",
        "outside_scope": "publisher identity / Sigstore signing certificate",
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "pymavlink integrity: PASS "
            f"version={lock_summary['version']} "
            f"wheels={lock_summary['wheel_count']} "
            f"record_hashes={installed_summary.get('record_hashes_checked', 'skipped')} "
            "network=not-used"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
