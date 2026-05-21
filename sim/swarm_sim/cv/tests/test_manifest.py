"""Manifest + fixture provenance tests — Phase 7.D.

These tests do NOT require the `[cv]` extra. They run on every push so
a bad manifest entry (non-HTTPS url, missing sha256, orphan fixture) is
caught even when `make test-cv` isn't part of the workflow.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from sim.swarm_sim.cv.weights import (
    AssetPlaceholder,
    AssetUnavailable,
    CVAssetError,
    cv_offline,
    ensure_asset,
    iter_specs,
    list_fixtures,
    load_manifest,
    verify_all,
)

REPO = Path(__file__).resolve().parents[4]
MANIFEST = REPO / "sim" / "swarm_sim" / "cv" / "manifest.json"
LICENSES = REPO / "sim" / "swarm_sim" / "cv" / "fixtures" / "LICENSES.md"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def test_manifest_loads() -> None:
    data = load_manifest()
    assert data["version"] == 1
    assert "weights" in data and "samples" in data


def test_every_url_is_https() -> None:
    for bucket, spec in iter_specs():
        assert spec.url.startswith("https://"), f"{bucket}/{spec.name} not https"


def test_every_sha256_well_formed() -> None:
    for _bucket, spec in iter_specs():
        assert SHA256_RE.match(spec.sha256), f"{spec.name} sha256 malformed"


def test_every_entry_has_license() -> None:
    for _bucket, spec in iter_specs():
        assert spec.license.strip(), f"{spec.name} missing license"


def test_baseline_yolov8n_not_a_placeholder() -> None:
    """The COCO baseline weight is the documented fallback for the
    drone_day fire/person-aerial weights; if its sha256 is a zero-pad
    placeholder then nothing works."""
    data = load_manifest()
    spec = data["weights"]["yolov8n.pt"]
    assert spec["sha256"] != "0" * 64
    assert spec["size_bytes"] > 0


def test_fixtures_only_documented_files(tmp_path: Path) -> None:
    """Every committed fixture must appear in fixtures/LICENSES.md."""
    text = LICENSES.read_text(encoding="utf-8")
    fire_files = list_fixtures("fire")
    person_files = list_fixtures("person_aerial")
    assert fire_files, "fire fixtures missing — run `make cv-generate-fixtures`"
    assert person_files, "person_aerial fixtures missing — run `make cv-generate-fixtures`"
    for path in [*fire_files, *person_files]:
        assert path.name in text, f"fixture {path.name} not in LICENSES.md"


def test_ensure_asset_refuses_placeholder() -> None:
    """drone_day weights still carry zero-pad sha256 → ensure_asset must fail loud."""
    with pytest.raises(AssetPlaceholder):
        ensure_asset("yolov8n-fire.pt")


def test_ensure_asset_refuses_unknown_name() -> None:
    with pytest.raises(CVAssetError):
        ensure_asset("not-in-manifest.pt")


def test_ensure_asset_respects_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """SWARM_CV_OFFLINE=1 + uncached → AssetUnavailable, no network call."""
    monkeypatch.setenv("SWARM_CV_OFFLINE", "1")
    monkeypatch.setenv("SWARM_CV_WEIGHTS_DIR", str(tmp_path / "weights"))
    monkeypatch.setenv("SWARM_CV_SAMPLES_DIR", str(tmp_path / "samples"))
    assert cv_offline() is True
    with pytest.raises(AssetUnavailable):
        ensure_asset("yolov8n.pt")


def test_verify_all_offline_passes_on_fresh_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SWARM_CV_WEIGHTS_DIR", str(tmp_path / "w"))
    monkeypatch.setenv("SWARM_CV_SAMPLES_DIR", str(tmp_path / "s"))
    summary = verify_all()
    assert summary.network_used is False
    assert summary.files_checked == 0
    # 2 fire weights + 2 dataset samples are still drone_day placeholders.
    assert summary.placeholders >= 2


def test_manifest_schema_rejects_http(tmp_path: Path) -> None:
    bad = tmp_path / "manifest.json"
    bad.write_text(
        json.dumps(
            {
                "version": 1,
                "weights": {
                    "x.pt": {
                        "url": "http://example.org/x.pt",
                        "sha256": "a" * 64,
                        "size_bytes": 1,
                        "license": "CC0",
                    }
                },
                "samples": {},
            }
        )
    )
    with pytest.raises(CVAssetError):
        load_manifest(bad)


def test_manifest_schema_rejects_bad_sha256(tmp_path: Path) -> None:
    bad = tmp_path / "manifest.json"
    bad.write_text(
        json.dumps(
            {
                "version": 1,
                "weights": {
                    "x.pt": {
                        "url": "https://example.org/x.pt",
                        "sha256": "not-hex",
                        "size_bytes": 1,
                        "license": "CC0",
                    }
                },
                "samples": {},
            }
        )
    )
    with pytest.raises(CVAssetError):
        load_manifest(bad)


def test_list_fixtures_rejects_traversal() -> None:
    with pytest.raises(CVAssetError):
        list_fixtures("../etc")


def test_list_fixtures_unknown_kind_returns_empty() -> None:
    assert list_fixtures("nonexistent") == []
