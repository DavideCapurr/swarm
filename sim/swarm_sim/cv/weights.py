"""Phase 7.D — CV asset cache + integrity gate.

Reads `manifest.json`, downloads each asset on first use, and verifies
SHA256 before handing the path back. The flow mirrors
`scripts/verify_pymavlink_integrity.py` (offline SHA256 verify) — same
exit-codes, same "no network unless we have to" stance.

Environment variables:
- `SWARM_CV_WEIGHTS_DIR`  — cache dir for model weights. Default
  `<repo>/.cache/cv/weights/`.
- `SWARM_CV_SAMPLES_DIR`  — cache dir for dataset reference samples.
  Default `<repo>/.cache/cv/samples/`.
- `SWARM_CV_OFFLINE`      — when `1` / `true`, refuse to make any HTTPS
  request; raise `AssetUnavailable` if a missing asset is requested. CI
  default is offline-on so that "no extra cached" never silently turns
  into a network call.

Drone-day note: entries with `"drone_day": true` carry a zero-pad
sha256 placeholder until first verified download. `ensure_asset` for
those raises `AssetPlaceholder` to make the gap obvious; the fall-back
to the COCO baseline lives in `detector.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ZERO_SHA256 = "0" * 64
_HTTPS_PREFIX = "https://"
_CHUNK_BYTES = 64 * 1024
_DOWNLOAD_TIMEOUT_S = 60.0


class CVAssetError(RuntimeError):
    """Base error for the CV asset gate."""


class AssetUnavailable(CVAssetError):
    """Asset is missing and the environment is offline (or its url is unreachable)."""


class AssetPlaceholder(CVAssetError):
    """Asset entry still carries a zero-pad sha256 — drone-day pin pending."""


class AssetIntegrityError(CVAssetError):
    """The bytes on disk did not match the manifest sha256."""


@dataclass(frozen=True)
class AssetSpec:
    """One row of the manifest, validated."""

    name: str
    url: str
    sha256: str
    size_bytes: int
    license: str
    description: str
    drone_day: bool


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def cv_offline() -> bool:
    return _truthy(os.getenv("SWARM_CV_OFFLINE"))


def weights_dir() -> Path:
    return Path(os.getenv("SWARM_CV_WEIGHTS_DIR") or (_ROOT / ".cache" / "cv" / "weights"))


def samples_dir() -> Path:
    return Path(os.getenv("SWARM_CV_SAMPLES_DIR") or (_ROOT / ".cache" / "cv" / "samples"))


def fixtures_dir() -> Path:
    return _FIXTURES_DIR


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    """Parse `manifest.json` and validate the shape strictly.

    Raises `CVAssetError` on the first malformed entry — there is no
    silent "best-effort" fallback.
    """

    src = path or _MANIFEST_PATH
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise CVAssetError(f"manifest {src} must be version 1")
    for bucket in ("weights", "samples"):
        if bucket not in data or not isinstance(data[bucket], dict):
            raise CVAssetError(f"manifest {src} missing required bucket {bucket!r}")
        for name, entry in data[bucket].items():
            _validate_entry(bucket, name, entry)
    return data


def _validate_entry(bucket: str, name: str, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise CVAssetError(f"manifest entry {bucket}/{name} must be an object")
    for required in ("url", "sha256", "size_bytes", "license"):
        if required not in entry:
            raise CVAssetError(f"manifest entry {bucket}/{name} missing key {required!r}")
    url = str(entry["url"])
    if not url.startswith(_HTTPS_PREFIX):
        raise CVAssetError(f"manifest entry {bucket}/{name} url must be https://")
    parsed = urlparse(url)
    if not parsed.netloc:
        raise CVAssetError(f"manifest entry {bucket}/{name} url has no host")
    sha = str(entry["sha256"]).lower()
    if not _SHA256_RE.match(sha):
        raise CVAssetError(f"manifest entry {bucket}/{name} sha256 must be 64 hex chars")
    size = entry["size_bytes"]
    if not isinstance(size, int) or size < 0:
        raise CVAssetError(f"manifest entry {bucket}/{name} size_bytes must be >=0 int")
    if not str(entry["license"]).strip():
        raise CVAssetError(f"manifest entry {bucket}/{name} license must be non-empty")


def _spec_from(bucket: str, name: str, entry: dict[str, Any]) -> AssetSpec:
    return AssetSpec(
        name=name,
        url=str(entry["url"]),
        sha256=str(entry["sha256"]).lower(),
        size_bytes=int(entry["size_bytes"]),
        license=str(entry["license"]),
        description=str(entry.get("description", "")),
        drone_day=bool(entry.get("drone_day", False)),
    )


def iter_specs(manifest: dict[str, Any] | None = None) -> Iterator[tuple[str, AssetSpec]]:
    """Yield (bucket, spec) for every manifest entry."""

    data = manifest or load_manifest()
    for bucket in ("weights", "samples"):
        for name, entry in data[bucket].items():
            yield bucket, _spec_from(bucket, name, entry)


def lookup(name: str, *, manifest: dict[str, Any] | None = None) -> tuple[str, AssetSpec]:
    data = manifest or load_manifest()
    for bucket in ("weights", "samples"):
        if name in data[bucket]:
            return bucket, _spec_from(bucket, name, data[bucket][name])
    raise CVAssetError(f"asset {name!r} not in manifest")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


def _target_dir(bucket: str) -> Path:
    if bucket == "weights":
        return weights_dir()
    if bucket == "samples":
        return samples_dir()
    raise CVAssetError(f"unknown bucket {bucket!r}")


class _HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse any redirect to a non-HTTPS URL.

    Defense in depth against a 30x → `http://` downgrade. Even with an
    HTTPS-only manifest, a compromised CDN could send a Location header
    pointing at an unencrypted mirror; we kill the connection before
    the body is read.
    """

    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.startswith(_HTTPS_PREFIX):
            raise CVAssetError(f"refusing redirect to non-https url: {newurl!r}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url: str, target: Path) -> None:
    if not url.startswith(_HTTPS_PREFIX):
        raise CVAssetError(f"refusing to fetch non-https url: {url!r}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic move via tempfile in the same dir, so a partial fetch cannot
    # leave a half-written file masquerading as a verified asset.
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.")
    tmp = Path(tmp_name)
    opener = urllib.request.build_opener(_HTTPSOnlyRedirectHandler())
    try:
        # `opener.open` is restricted to https:// via the redirect handler
        # above + the up-front prefix check; the manifest schema is the
        # third defense-in-depth layer.
        with (
            os.fdopen(fd, "wb") as out,
            opener.open(url, timeout=_DOWNLOAD_TIMEOUT_S) as resp,  # nosec B310
        ):
            while True:
                chunk = resp.read(_CHUNK_BYTES)
                if not chunk:
                    break
                out.write(chunk)
        tmp.replace(target)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def ensure_asset(name: str, *, manifest: dict[str, Any] | None = None) -> Path:
    """Resolve a manifest entry to a verified path on disk.

    1. Refuse `drone_day` placeholders up-front (the sha256 is still zero).
    2. If cached, verify sha256 — surface a mismatch loudly.
    3. If absent and `SWARM_CV_OFFLINE=1`, raise `AssetUnavailable`.
    4. Otherwise download via HTTPS, verify, then atomic-move into cache.
    """

    bucket, spec = lookup(name, manifest=manifest)
    if spec.sha256 == _ZERO_SHA256:
        raise AssetPlaceholder(
            f"asset {name!r} carries a zero-pad sha256 placeholder; "
            "pin the real hash before requesting it"
        )
    target = _target_dir(bucket) / name
    if target.exists():
        actual = _sha256_file(target)
        if actual != spec.sha256:
            raise AssetIntegrityError(
                f"sha256 mismatch for cached {name}: expected {spec.sha256}, got {actual}"
            )
        return target
    if cv_offline():
        raise AssetUnavailable(
            f"asset {name!r} not cached and SWARM_CV_OFFLINE=1 forbids the fetch"
        )
    if not spec.url.startswith(_HTTPS_PREFIX):
        raise CVAssetError(f"refusing to fetch {name!r} from non-https url")
    _download(spec.url, target)
    actual = _sha256_file(target)
    if actual != spec.sha256:
        target.unlink(missing_ok=True)
        raise AssetIntegrityError(
            f"downloaded {name} sha256 {actual} != manifest {spec.sha256}"
        )
    return target


@dataclass(frozen=True)
class IntegritySummary:
    files_checked: int
    weights_present: int
    samples_present: int
    placeholders: int
    network_used: bool

    def as_line(self) -> str:
        return (
            f"cv assets integrity: PASS files={self.files_checked} "
            f"weights_present={self.weights_present} "
            f"samples_present={self.samples_present} "
            f"placeholders={self.placeholders} "
            f"network={'used' if self.network_used else 'not-used'}"
        )


def verify_all(*, manifest: dict[str, Any] | None = None) -> IntegritySummary:
    """Offline integrity audit — never touches the network.

    Validates the manifest structure, then verifies SHA256 of any asset
    that happens to be cached locally. Missing assets are silently fine
    (audit-time `make audit-cv-integrity` runs without forcing a download).
    Zero-pad placeholders are counted but never resolved.
    """

    data = manifest or load_manifest()
    files_checked = 0
    weights_present = 0
    samples_present = 0
    placeholders = 0
    for bucket, spec in iter_specs(data):
        if spec.sha256 == _ZERO_SHA256:
            placeholders += 1
            continue
        target = _target_dir(bucket) / spec.name
        if not target.exists():
            continue
        actual = _sha256_file(target)
        if actual != spec.sha256:
            raise AssetIntegrityError(
                f"sha256 mismatch for cached {bucket}/{spec.name}: "
                f"expected {spec.sha256}, got {actual}"
            )
        files_checked += 1
        if bucket == "weights":
            weights_present += 1
        else:
            samples_present += 1
    return IntegritySummary(
        files_checked=files_checked,
        weights_present=weights_present,
        samples_present=samples_present,
        placeholders=placeholders,
        network_used=False,
    )


def list_fixtures(kind: str) -> list[Path]:
    """Return committed CC0 fixture frames for the given kind.

    `kind` ∈ {"fire", "person_aerial"}. Files are listed lexically so the
    order is deterministic across machines; pick one using a seeded RNG
    (`CVPerception` does so per scenario+after_s).
    """

    safe = re.sub(r"[^a-z_]", "", kind.lower())
    if safe != kind.lower():
        raise CVAssetError(f"invalid fixture kind {kind!r}")
    folder = _FIXTURES_DIR / safe
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"})
