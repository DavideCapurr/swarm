#!/usr/bin/env python3
"""Phase 7.D — synthetic CC0 fixture generator.

The committed fixtures under `fire/` and `person_aerial/` are SwarmOS-
authored 32x32 PNGs released to the public domain (CC0). They are NOT
representative imagery — they exist so the seam tests
(`test_detector.py`, `test_perception_seam.py`, `test_wildfire_e2e_cv.py`)
can run end-to-end without redistributing FLAME / D-Fire / VisDrone
content (research-only licenses; see `manifest.json` and `LICENSES.md`).

Drone-day flow (documented in `docs/cv/phase-7d.md`):

1. Download a real CC0 frame from Pexels / Unsplash (URL + license in
   `LICENSES.md`).
2. Drop it into `fire/` or `person_aerial/`.
3. `make audit-cv-integrity` re-verifies the entire set offline.

Re-generation:

    python -m sim.swarm_sim.cv.fixtures._generate

The script only writes files that do NOT already exist — it never
overwrites a real frame an operator may have added.

PNG was chosen over JPEG so the generator can run on the default
`make setup` env (stdlib `zlib` only, no Pillow / numpy required).
The pixel payload is solid-colour zero; per-file variance lives in a
PNG `tEXt` chunk so each file has a unique sha256 without changing
the visible image.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_WIDTH = 32
_HEIGHT = 32
# Bit depth 8, colour type 2 (RGB), default compression / filter / interlace.
_IHDR_BODY = struct.pack(">IIBBBBB", _WIDTH, _HEIGHT, 8, 2, 0, 0, 0)


def _chunk(tag: bytes, payload: bytes) -> bytes:
    if len(tag) != 4:
        raise ValueError(f"chunk tag must be 4 bytes: {tag!r}")
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def _idat_payload() -> bytes:
    # Each row: 1 filter byte (0 = None) + 3 zero bytes per pixel.
    row = b"\x00" + b"\x00" * (_WIDTH * 3)
    raw = row * _HEIGHT
    return zlib.compress(raw, 9)


def _text_chunk(keyword: str, text: str) -> bytes:
    if not keyword or len(keyword) > 79:
        raise ValueError("tEXt keyword must be 1..79 chars")
    body = keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")
    return _chunk(b"tEXt", body)


def _build_png(tag: str) -> bytes:
    ihdr = _chunk(b"IHDR", _IHDR_BODY)
    text = _text_chunk("Comment", tag)
    idat = _chunk(b"IDAT", _idat_payload())
    iend = _chunk(b"IEND", b"")
    return _PNG_SIGNATURE + ihdr + text + idat + iend


_FIRE_TAGS = (
    "swarm-cv-phase-7d-fire-001",
    "swarm-cv-phase-7d-fire-002",
    "swarm-cv-phase-7d-fire-003",
    "swarm-cv-phase-7d-fire-004",
    "swarm-cv-phase-7d-fire-005",
    "swarm-cv-phase-7d-fire-006",
)
_PERSON_TAGS = (
    "swarm-cv-phase-7d-person-001",
    "swarm-cv-phase-7d-person-002",
    "swarm-cv-phase-7d-person-003",
    "swarm-cv-phase-7d-person-004",
    "swarm-cv-phase-7d-person-005",
    "swarm-cv-phase-7d-person-006",
)


def _write_kind(folder: Path, tags: tuple[str, ...]) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    written = 0
    for idx, tag in enumerate(tags, start=1):
        target = folder / f"fixture_{idx:03d}.png"
        if target.exists():
            continue
        target.write_bytes(_build_png(tag))
        written += 1
    return written


def main() -> int:
    fire = _write_kind(FIXTURES_DIR / "fire", _FIRE_TAGS)
    person = _write_kind(FIXTURES_DIR / "person_aerial", _PERSON_TAGS)
    print(f"phase-7d fixtures: fire={fire} person_aerial={person}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
