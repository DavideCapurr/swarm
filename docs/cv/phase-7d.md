# Phase 7.D — CV baseline (sim)

Status: code-complete (`sim/swarm_sim/cv/`); fixtures are SwarmOS-authored
synthetic CC0 placeholders. Drone-day items (real CC0 frames, fine-tuned
weight pins, NOTAM/weather sample integration) catalogued in
[`drone-day-checklist.md`](../ops/drone-day-checklist.md) §2.D — they do
not block the 7.E demo.

## What 7.D does

Replaces the mock perception with real YOLOv8 inference inside the sim.
The three committed scenarios (`sim/scenarios/{wildfire,intrusion,
search}_owner_land.yaml`) now opt into the CV baseline with
`perception.cv_enabled: true`. When enabled:

1. `Scenario.build_world()` instantiates `CVPerception` instead of
   `MockPerception` (`sim/swarm_sim/scenario.py`).
2. For every scripted `IgnitionEvent`, `CVPerception` picks a fixture
   frame deterministically (seed from `(scenario_id, kind, after_s)`).
3. `YOLODetector.predict()` runs `ultralytics.YOLO(weight_path).predict()`
   with `torch.manual_seed(0)`.
4. The top-1 detection's confidence becomes the `Anomaly.confidence`
   on the bus. Geo + kind still come from the YAML.

The seam matches `MockPerception` structurally (`run()` + `on_anomaly`
callback), so no other code path in `swarm_os` / `backend` / `Console`
changes.

## Why this layout

- **`sim/swarm_sim/cv/` (not `swarm_os/cv/`, not top-level `ml/`).**
  SwarmOS decides; the sim percepts. Top-level `ml/` would be a
  premature abstraction — the second caller will not land until Phase 19
  (hardware adapter) and we'll re-evaluate the seam then.
- **Opt-in `[cv]` extra (~2 GB wheels).** Default `make setup` skips it;
  prod images (`backend/Dockerfile`, `docker-compose.prod.yml`) skip it.
  AGPL-3.0 license surface is contained to the sim runtime.
- **Asset cache outside the repo.** Weights + dataset samples live in
  `.cache/cv/` (gitignored). The repo carries the manifest, the
  integrity gate, and the synthetic CC0 fixtures only.

## Asset classes

| Class             | Where it lives                          | Policy                                                                |
|-------------------|-----------------------------------------|-----------------------------------------------------------------------|
| Fixtures (smoke)  | `sim/swarm_sim/cv/fixtures/`            | Committed, CC0 only, sha256-tracked in `fixtures/LICENSES.md`.        |
| Weights           | `.cache/cv/weights/` (gitignored)       | Manifest-pinned `https://`+sha256; lazy download on first use.        |
| Samples (datasets)| `.cache/cv/samples/` (gitignored)       | FLAME / D-Fire / VisDrone subsets, research-only, never redistributed.|

### Adding a new fixture

1. Find a CC0 image on Pexels / Unsplash (or author one yourself).
2. Save it as `sim/swarm_sim/cv/fixtures/<kind>/<short-name>.png` (or
   `.jpg`). ≤ 200 KB each.
3. Append a row to `sim/swarm_sim/cv/fixtures/LICENSES.md` with:
   - filename,
   - source URL,
   - explicit license line ("CC0-1.0 (Pexels)" etc.),
   - first 16 hex chars of the file's sha256.
4. `make audit-cv-integrity` validates the chain offline.

### Pinning a new weight or sample

1. Identify the exact GitHub release / HTTPS URL.
2. `curl -sL <url> | sha256sum` → the new sha256.
3. Edit `sim/swarm_sim/cv/manifest.json`:
   - drop the `"drone_day": true` flag,
   - replace the zero-pad sha256,
   - set `size_bytes` to the real byte count,
   - tighten the license text.
4. `python -c "from sim.swarm_sim.cv.weights import ensure_asset;
   ensure_asset('<name>')"` to populate the local cache.
5. `make audit-cv-integrity` to confirm the re-verify.

## Running the suite

```
make setup-cv            # opt-in: installs ultralytics + torch + cv2 + Pillow + numpy
make test-cv             # runs the cv_baseline + cv_baseline_realistic tests
make audit-cv-integrity  # offline manifest + fixture sha256 audit (no network)
```

Default `make test` and `make audit` already exclude the `cv_baseline`
markers, so a contributor without `setup-cv` never sees a spurious
failure.

## Offline mode

`SWARM_CV_OFFLINE=1` refuses any HTTPS download. Cached assets still
verify. Useful for:

- CI runs that should never spend a download budget unexpectedly.
- Air-gapped customer environments where the bundle is pre-staged.
- Demo recordings where a flaky link must not block the script.

## License posture

| Component              | License             | Where it can run                                |
|------------------------|---------------------|-------------------------------------------------|
| Ultralytics YOLOv8     | AGPL-3.0            | Sim runtime (CI/dev). NOT in prod image.        |
| Torch / torchvision    | BSD-3 / BSD-3       | Anywhere.                                       |
| OpenCV-Python-Headless | Apache-2.0          | Anywhere.                                       |
| Pillow                 | HPND (MIT-like)     | Anywhere.                                       |
| NumPy                  | BSD-3               | Anywhere.                                       |
| Committed fixtures     | CC0-1.0 (SwarmOS)   | Anywhere.                                       |
| FLAME / D-Fire / VisDrone samples | Research-only | `.cache/cv/samples/` only — never committed. |

The AGPL surface is the reason the `cv` extra is opt-in and excluded
from the production deploy. Customer-facing CV runtime (Phase 19+) will
require an Ultralytics Enterprise license or a swap to a permissively-
licensed detector — that's a separate legal decision.

## What is NOT in 7.D (anti-overreach)

- No per-scenario thresholds — `cv.fire_conf_floor`, `cv.person_min_box_px`
  etc. land in Phase 8.B.
- No shadow / A-B comparison with MockPerception — Phase 8.B-bis.
- No detection-bbox overlay in the Console — Phase 8.D / 10.
- No `make demo-wildfire-sim` style targets — Phase 7.E.
- No fine-tuning / DataLoader / training loop — Phase 10.A.
- No live RTSP/WebRTC ingestion — Phase 11 / 14.
- No detection history table in Postgres — Phase 16 (signed decision
  log).
- No AGPL deny-list flip in `dependency-review.yml` — Phase 6 scope.

## See also

- [`docs/security/threat-model.md`](../security/threat-model.md) §Supply chain
- [`sim/swarm_sim/cv/manifest.json`](../../sim/swarm_sim/cv/manifest.json)
- [`sim/swarm_sim/cv/fixtures/LICENSES.md`](../../sim/swarm_sim/cv/fixtures/LICENSES.md)
- [`docs/plan/swarmos-roadmap.md`](../plan/swarmos-roadmap.md) §7.D
