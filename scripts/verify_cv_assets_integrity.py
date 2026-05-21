#!/usr/bin/env python3
"""Offline CV asset integrity gate — Phase 7.D.

Mirrors `scripts/verify_pymavlink_integrity.py`:

1. Parses `sim/swarm_sim/cv/manifest.json` and validates the schema
   strictly (HTTPS url, sha256 hex64, non-empty license, size_bytes int).
2. Verifies the sha256 of every cached asset under
   `.cache/cv/weights/` and `.cache/cv/samples/` (configurable via
   `SWARM_CV_WEIGHTS_DIR` / `SWARM_CV_SAMPLES_DIR`).
3. Verifies the sha256 of every file under `sim/swarm_sim/cv/fixtures/`
   against the row in `fixtures/LICENSES.md`. A file in the directory
   that has NO row → audit FAIL (drone-day rule from the threat model:
   provenance must precede commit).
4. NEVER makes a network request. Exit code 0 on PASS, 1 on any
   integrity failure. Output line matches the pymavlink gate format so
   `make audit-cv-integrity` plays nicely with grep.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CV_DIR = ROOT / "sim" / "swarm_sim" / "cv"
MANIFEST = CV_DIR / "manifest.json"
LICENSES = CV_DIR / "fixtures" / "LICENSES.md"
FIXTURES_DIR = CV_DIR / "fixtures"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA256_PREFIX_RE = re.compile(r"`([0-9a-f]{16})…`")
HTTPS_PREFIX = "https://"


class IntegrityError(RuntimeError):
    """Raised when the CV integrity gate finds a hard failure."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest_schema(manifest: dict[str, Any]) -> None:
    if manifest.get("version") != 1:
        raise IntegrityError("manifest must be version 1")
    for bucket in ("weights", "samples"):
        if bucket not in manifest or not isinstance(manifest[bucket], dict):
            raise IntegrityError(f"manifest missing required bucket {bucket!r}")
        for name, entry in manifest[bucket].items():
            for key in ("url", "sha256", "size_bytes", "license"):
                if key not in entry:
                    raise IntegrityError(f"manifest entry {bucket}/{name} missing {key!r}")
            url = str(entry["url"])
            if not url.startswith(HTTPS_PREFIX):
                raise IntegrityError(f"manifest entry {bucket}/{name} url must be https://")
            if not SHA256_RE.match(str(entry["sha256"]).lower()):
                raise IntegrityError(f"manifest entry {bucket}/{name} sha256 must be 64 hex chars")
            if not str(entry["license"]).strip():
                raise IntegrityError(f"manifest entry {bucket}/{name} license must be non-empty")


def verify_cached_assets(manifest: dict[str, Any]) -> dict[str, int]:
    import os

    weights_dir = Path(os.getenv("SWARM_CV_WEIGHTS_DIR") or (ROOT / ".cache" / "cv" / "weights"))
    samples_dir = Path(os.getenv("SWARM_CV_SAMPLES_DIR") or (ROOT / ".cache" / "cv" / "samples"))
    cached = {"weights": 0, "samples": 0}
    for bucket, root in (("weights", weights_dir), ("samples", samples_dir)):
        for name, entry in manifest[bucket].items():
            path = root / name
            if not path.is_file():
                continue
            if str(entry["sha256"]) == "0" * 64:
                raise IntegrityError(
                    f"cached {bucket}/{name} exists but manifest still carries a zero-pad sha256"
                )
            actual = _sha256(path)
            if actual != str(entry["sha256"]).lower():
                raise IntegrityError(
                    f"sha256 mismatch for cached {bucket}/{name}: "
                    f"expected {entry['sha256']}, got {actual}"
                )
            cached[bucket] += 1
    return cached


def _parse_license_rows() -> dict[str, dict[str, str]]:
    """Parse the per-fixture rows out of fixtures/LICENSES.md.

    The doc uses a Markdown table per kind. We're strict: every committed
    fixture file must appear in this table.
    """

    text = LICENSES.read_text(encoding="utf-8")
    rows: dict[str, dict[str, str]] = {}
    current_kind: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped.lstrip("# ").strip().rstrip("/").lower()
            current_kind = heading if heading in {"fire", "person_aerial"} else None
            continue
        if current_kind is None or not stripped.startswith("|"):
            continue
        parts = [c.strip() for c in stripped.strip("|").split("|")]
        if len(parts) < 4 or parts[0].lower().startswith(("file", "---")):
            continue
        file_name, source, license_field, sha_prefix_field = parts[:4]
        match = SHA256_PREFIX_RE.search(sha_prefix_field)
        if not match:
            continue
        rows[f"{current_kind}/{file_name}"] = {
            "source": source,
            "license": license_field,
            "sha256_prefix": match.group(1),
        }
    return rows


def verify_fixtures() -> int:
    rows = _parse_license_rows()
    seen_keys: set[str] = set()
    count = 0
    for kind in ("fire", "person_aerial"):
        folder = FIXTURES_DIR / kind
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            key = f"{kind}/{path.name}"
            row = rows.get(key)
            if row is None:
                raise IntegrityError(
                    f"committed fixture {key} has no row in fixtures/LICENSES.md "
                    "(provenance must precede commit)"
                )
            actual = _sha256(path)
            if not actual.startswith(row["sha256_prefix"]):
                raise IntegrityError(
                    f"fixture {key} sha256 prefix {actual[:16]!r} does not match "
                    f"LICENSES.md row {row['sha256_prefix']!r}"
                )
            if not row["license"].strip():
                raise IntegrityError(f"fixture {key} missing license in LICENSES.md")
            seen_keys.add(key)
            count += 1
    stale = sorted(set(rows) - seen_keys)
    if stale:
        raise IntegrityError(
            "LICENSES.md has rows for files that no longer exist on disk: "
            + ", ".join(stale)
        )
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args()

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        verify_manifest_schema(manifest)
        cached = verify_cached_assets(manifest)
        fixtures_count = verify_fixtures()
    except IntegrityError as exc:
        print(f"cv assets integrity: FAIL: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"cv assets integrity: FAIL: {exc}", file=sys.stderr)
        return 1

    summary = {
        "status": "pass",
        "fixtures_committed": fixtures_count,
        "weights_cached": cached["weights"],
        "samples_cached": cached["samples"],
        "network": "not used",
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "cv assets integrity: PASS "
            f"fixtures={fixtures_count} "
            f"weights_cached={cached['weights']} "
            f"samples_cached={cached['samples']} "
            "network=not-used"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
