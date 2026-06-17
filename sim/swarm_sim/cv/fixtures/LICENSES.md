# CV fixture provenance — Phase 7.D

Every binary file under `fire/` and `person_aerial/` MUST have a row in
the matching table below: source URL + license + sha256. CI's
`make audit-cv-integrity` re-verifies the sha256s offline. The audit
fails closed if a file appears in the directory but is missing from
this manifest.

License policy:

- Only **CC0 / public-domain** or **explicit BSD/CC-BY (with attribution
  preserved here)** content may be committed.
- **No FLAME, D-Fire, VisDrone, COCO, or ImageNet redistribution.** Those
  datasets are research-only; samples are fetched on demand into the
  gitignored `.cache/cv/samples/` (see `manifest.json`).
- **`person_aerial/` real frames (CV live decision):** CC0-1.0 frames of a
  real person are allowed **only when the subject is non-identifiable** —
  back-view, distance, or silhouette, no recognisable face. CC0 waives the
  photographer's copyright; the back-view/distance rule covers the depicted
  person's likeness so we never commit a recognisable face. Aerial
  silhouettes / mannequins / synthetic placeholders remain acceptable too.
  Every row records the source landing page + creator so the CC0 grant is
  auditable. (Pre-CV-live the bucket carried synthetic zero-pixel
  placeholders, which scored 0.0 — the reason CV live replaced them.)

## fire/

| File              | Source URL           | License           | sha256 prefix       |
|-------------------|----------------------|-------------------|---------------------|
| fixture_001.png   | SwarmOS synthetic    | CC0-1.0 (SwarmOS) | `9da3afa2977b3c9f…` |
| fixture_002.png   | SwarmOS synthetic    | CC0-1.0 (SwarmOS) | `6079d1e39471f946…` |
| fixture_003.png   | SwarmOS synthetic    | CC0-1.0 (SwarmOS) | `0e8607c4b2a9ae48…` |
| fixture_004.png   | SwarmOS synthetic    | CC0-1.0 (SwarmOS) | `e1ec7d4bc6931dc7…` |
| fixture_005.png   | SwarmOS synthetic    | CC0-1.0 (SwarmOS) | `a3d305382f51741a…` |
| fixture_006.png   | SwarmOS synthetic    | CC0-1.0 (SwarmOS) | `0c58d4c4968bd263…` |

## person_aerial/

Real CC0-1.0 frames, non-identifiable subjects (back-view / distance). Each
is a person in an outdoor setting — the patrol surface for the intrusion +
search scenarios. The `top_person_conf` column is the real COCO yolov8n
score (conf-floor 0.05, `torch.manual_seed(0)`) captured by
`make cv-live` — the value that replaces the old scripted confidence on the
`Anomaly`. Downscaled to ≤ 512 px / JPEG q55.

| File            | Source (CC0 landing page · creator)                                            | License   | sha256 prefix       | top_person_conf |
|-----------------|--------------------------------------------------------------------------------|-----------|---------------------|-----------------|
| fixture_001.jpg | flickr.com/photos/132795455@N08/17984010995 · Image Catalog                    | CC0-1.0   | `8a3c97702e78095d…` | 0.860           |
| fixture_002.jpg | flickr.com/photos/132795455@N08/22649071756 · Image Catalog                    | CC0-1.0   | `7009af1d8847deb3…` | 0.946           |
| fixture_003.jpg | wordpress.org/photos/photo/82865232e6/ · annezazu (WP Photo Directory)         | CC0-1.0   | `52c1684b98d0f887…` | 0.901           |
| fixture_004.jpg | stocksnap.io/photo/man-hiking-EZZSLOHXVG · Matt Bango (StockSnap)              | CC0-1.0   | `87a5c95834069b26…` | 0.801           |

## sim_drone_pov/

Synthetic SIM-labelled drone-POV frames — a **Langhe vineyard** (the demo
setting; `sim/swarm_sim/world.py` `DEFAULT_DOCK` 44.70 N / 8.03 E), subject
walking an alley in **back view / distance** (non-identifiable, same privacy
rule as `person_aerial/`). These are SwarmOS-authored Blender renders dedicated
to the public domain (CC0-1.0), the same source as the Console viewport clip
`frontend/public/sim-feed/drone-pov.mp4` (provenance + reproduction:
`scripts/render_sim_feed.py`; CC0 Poly Haven `alps_field` HDRI +
`aerial_grass_rock` texture). They join the CV fixture **pool** so the detector
can run on them, but they do **not** drive any anomaly confidence — the live
`person` scores keep coming from the real CC0 frames in `person_aerial/` (the
honest-sim line: a synthetic figure is not passed off as a real detection).
Downscaled to 512×384 / JPEG.

| File            | Source (CC0-1.0)                                  | License | sha256 prefix       |
|-----------------|---------------------------------------------------|---------|---------------------|
| fixture_001.jpg | SwarmOS synthetic (Blender; Poly Haven CC0 assets) | CC0-1.0 | `748534974ef1d181…` |
| fixture_002.jpg | SwarmOS synthetic (Blender; Poly Haven CC0 assets) | CC0-1.0 | `2e88d67c2b6c4214…` |
| fixture_003.jpg | SwarmOS synthetic (Blender; Poly Haven CC0 assets) | CC0-1.0 | `f8fc93aacad7fb7a…` |
| fixture_004.jpg | SwarmOS synthetic (Blender; Poly Haven CC0 assets) | CC0-1.0 | `144cdb640461c559…` |

## fire/ — "SwarmOS synthetic" (still placeholder, on purpose)

The `fire/` set is a 32x32 zero-pixel PNG with a `tEXt` comment chunk that
makes each file's sha256 distinct. They are generated by `./_generate.py`
(stdlib `zlib` only — no Pillow / numpy required) and SwarmOS dedicates them
to the public domain (CC0-1.0).

These stay synthetic **deliberately**: wildfire CV is deferred to drone-day.
The COCO yolov8n baseline carries no fire/smoke class and the fine-tuned
`yolov8n-fire.pt` is still a `drone_day` placeholder in `manifest.json`, so a
real smoke frame would only ever score ~0 — a fake value this repo refuses.
The `fire/` fixtures therefore exist solely to keep the detector smoke test
wired (`test_detector.py`, which tolerates conf 0.0). They get replaced with
real CC0 smoke frames the day the fine-tuned weight is pinned.

## Replacing or adding a fixture

`person_aerial/` is now **real CC0 imagery** (the CV live milestone). To add
or replace one:

1. Pull a genuinely CC0 frame (Openverse `license=cc0`, WP Photo Directory,
   StockSnap, Pexels, Unsplash). For `person_aerial/` the subject must be
   **non-identifiable** (back-view / distance / silhouette).
2. Downscale to ≤ 512 px, JPEG q55 (`sips -Z 512 -s format jpeg`), ≤ ~50 KB.
3. Drop it in as `fixture_NNN.jpg` and append/replace the matching row above
   with the CC0 landing page + creator + license + new sha256 prefix (and,
   for `person_aerial/`, the `make cv-live` person score).
4. `make audit-cv-integrity` to confirm the offline sha256 chain.

If you add a brand-new file (not a replacement), append the row here BEFORE
committing the binary — the audit fails closed on any un-rowed fixture.
