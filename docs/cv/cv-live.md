# CV live (three-month plan, Track B)

Status: **done** for the two `person`-class scenarios (intrusion + search);
the synthetic SIM-labeled drone-POV **video clip** sub-step is now **done** too
(see [Synthetic SIM viewport feed](#synthetic-sim-viewport-feed-video-sub-step)
below). Builds on [Phase 7.D](phase-7d.md).

## What CV live does

7.D wired the seam but ran it on 32×32 zero-pixel placeholder fixtures, so
every "real" score was 0.0 — wired, not live. CV live makes the score
**real and meaningful**:

| Scenario | `cv_enabled` | Anomaly confidence | Source |
|----------|--------------|--------------------|--------|
| `intrusion_owner_land` | true  | **real** YOLOv8 `person` score | committed CC0 fixture |
| `search_owner_land`    | true  | **real** YOLOv8 `person` score | committed CC0 fixture |
| `wildfire_owner_land`  | false | scripted (0.62 / 0.88) | fire/smoke-CV deferred to drone-day |

Last `make cv-live` evidence (real COCO yolov8n, conf-floor 0.05,
`torch.manual_seed(0)`):

```
intrusion_owner_land   INTRUSION  cv label='person'  score=0.946  (was scripted 0.71)
search_owner_land      HEAT_SPOT  cv label='person'  score=0.860  (was scripted 0.55)
wildfire_owner_land    SMOKE/FIRE scripted 0.62/0.88 (cv deferred)
```

The geo + kind still come from the scenario YAML (the sim has no
geo-localized frames); only `confidence` is the model output, exactly the
7.D contract — now on representative imagery.

## Why wildfire stays scripted (fire-CV deferred)

Honest-sim discipline: the COCO yolov8n baseline carries **no fire/smoke
class**, and the fine-tuned `yolov8n-fire.pt` is still a `drone_day`
placeholder (zero-pad sha) in [`manifest.json`](../../sim/swarm_sim/cv/manifest.json).
Running COCO on a smoke frame would emit a meaningless ~0 score — a fake
value this repo refuses. So wildfire's SMOKE keeps its scripted 0.62 and the
FIRE follow-up stays `thermal_sat` (a satellite thermal signal, never an
RGB/CV detection). Those scripted numbers also drive the deterministic
R1→R2 path and the 0% shadow-divergence gate. Fire-CV lands the day the
fine-tuned weight is pinned (drone-day).

## Real CC0 fixtures (privacy posture)

`sim/swarm_sim/cv/fixtures/person_aerial/` now holds **real CC0-1.0** frames
instead of zero-pixel placeholders. Policy (see
[`fixtures/LICENSES.md`](../../sim/swarm_sim/cv/fixtures/LICENSES.md)): the
subject must be **non-identifiable** — back-view / distance / silhouette.
CC0 waives the photographer's copyright; the back-view rule covers the
depicted person's likeness, so no recognisable face is ever committed. Each
row records the CC0 landing page + creator + sha + the real person score.

| File | Subject | `person` conf | Source |
|------|---------|---------------|--------|
| fixture_001.jpg | man in field, back-view | 0.860 | Image Catalog (Flickr, CC0) |
| fixture_002.jpg | person in field, back-view | 0.946 | Image Catalog (Flickr, CC0) |
| fixture_003.jpg | person walking away, beach | 0.901 | annezazu (WP Photo Directory, CC0) |
| fixture_004.jpg | hiker on trail, back-view | 0.801 | Matt Bango (StockSnap, CC0) |

The `fire/` bucket stays synthetic zero-pixel on purpose (wildfire CV
deferred; the fixtures only keep `test_detector.py` wired).

## Manifest re-pin (supply-chain fix)

CV live caught a real integrity drift: the pinned `yolov8n.pt` sha
(`31e20dde…`, 6534387 B) no longer matched the bytes GitHub serves —
Ultralytics re-published the release asset. Re-verified that the v8.3.0 and
v8.4.0 URLs serve **byte-identical** files (`f59b3d83…`, 6549796 B) and that
the model loads + detects `person`; pinned the current verified sha. The
offline integrity gate (`make audit-cv-integrity`) confirms the chain.

## Running it

```
make setup-cv     # opt-in [cv] extra (~2 GB wheels, AGPL — never in prod)
make test-cv      # cv_baseline suite incl. the CV-live e2e contract
make cv-live      # real-score bench → docs/bench/artifacts/cv-live-*.json
```

`make cv-live` exits non-zero if any `cv_enabled` anomaly score falls below
the regression floor (default 0.25) — a real gate that would catch a fixture
silently degrading back to a 0.0 placeholder. The default `make test`,
`make lint`, `make audit` all stay green **without** the `[cv]` extra.

Reproducibly verified in an **ephemeral** CV env (`uv run --with`, no
`.venv`/lockfile mutation — the 2 GB AGPL surface never enters the working
env), matching the opt-in production posture: CV is a sim/dev module,
installed only where it's licensed, never in the backend image.

## Synthetic SIM viewport feed (video sub-step)

The sim has no real camera, so the verification viewport showed only the honest
`VIEWPORT PENDING` placard. The video sub-step adds a synthetic SIM-labeled
drone-POV clip — **never a stock clip** (PDF §5.2): it is our own Blender render,
stamped `SIMULATED FEED` in the Console, and explicitly not passed off as a real
camera.

- **Setting matches the demo.** Rendered as a **Langhe vineyard near Alba** —
  the same place the three scenarios model (`world.py` `DEFAULT_DOCK`
  44.70 N / 8.03 E). Parallel vine rows, subject walking an alley in
  **back view / distance** (the same non-identifiable privacy rule as the real
  `person_aerial/` fixtures).
- **Assets are CC0-1.0** (Poly Haven `alps_field` HDRI + `aerial_grass_rock`
  texture); the vine rows / figure / camera path are SwarmOS-authored (CC0-1.0).
  Reproducible via [`scripts/render_sim_feed.py`](../../scripts/render_sim_feed.py)
  (`blender --background`); Blender is an opt-in art tool, not a repo/CI dep.
- **Served via `StreamDescriptor`.** The model gained a third honest state —
  `simulated=True`, carrying a **same-origin** `/sim-feed/…` path (not an
  external URL, so zero SSRF surface). The sim runner advertises it per unit
  when `SWARM_SIM_FEED_PATH` is set; `dev_up.sh` turns it on for the demo when
  the clip is present. Clip + provenance:
  [`frontend/public/sim-feed/`](../../frontend/public/sim-feed/LICENSES.md).
- **Feeds the CV fixture pool.** A few frames live in
  `sim/swarm_sim/cv/fixtures/sim_drone_pov/` (the detector can run on them), but
  they **do not** drive anomaly confidence — the live `person` scores stay on
  the real CC0 `person_aerial/` frames. A synthetic figure is never passed off
  as a real detection (the same honest-sim line as deferred fire-CV).

## Not in CV live (next / deferred)

- **bbox overlay** in the Console — the next Track B milestone.
- Fire/smoke-CV — drone-day (fine-tuned weight pin).
- 10.C classifier replacing the thresholds — later in the plan.
