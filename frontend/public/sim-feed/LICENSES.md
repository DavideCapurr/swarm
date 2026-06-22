# `/sim-feed/` — synthetic SIM-labelled viewport clips

These clips are the CV-live **video sub-step**: a synthetic drone-POV feed served
same-origin to the Console viewport and stamped **`SIMULATED FEED`** (PDF §5.2 —
never a stock clip; this is our own labelled synthetic asset, not a real camera).
They are advertised to the Console by the sim runner as a `simulated`
`StreamDescriptor` (`SWARM_SIM_FEED_PATH`, see `sim/swarm_sim/runner.py`).

## Setting

Rendered to match where the demo is set — a **Langhe vineyard near Alba**
(Piedmont, Italy), the same place the three scenarios model
(`sim/swarm_sim/world.py` `DEFAULT_DOCK` = 44.70 N, 8.03 E). A drone holds
station over the rows, looking down the vineyard to the horizon, with a treeline
and soft rolling green hills behind under a warm golden-hour sky. **No figure
appears** — a calm vineyard patrol that fits every phase of the wildfire demo,
with nothing identifiable to raise a privacy concern.

## How it was made

Blender 5.x, **path-traced in Cycles** (Metal GPU, 96 samples + OpenImageDenoise,
AgX view transform). It is photorealistic because every element is a **real CC0
photoscanned asset**, not hand-faked geometry:

- **The vines are a real plant model.** Each vine row is thousands of *instances*
  of a real CC0 Poly Haven shrub model (`shrub_01`) — actual leaf geometry with
  alpha cutouts — stacked five-high into tall leafy walls. Instancing shares one
  mesh, so the whole field renders cheaply; each instance is tinted slightly
  differently (Object-Info colour) so the rows are not a flat repeat. This is
  what reads as foliage rather than a textured box.
- **A Langhe landscape**, not just rows: a treeline of real CC0 tree instances
  (`island_tree_01`) and soft rolling green hills sit on the horizon behind.
- **Golden-hour light**: a **real CC0 sky HDRI**, warm-tinted for the camera
  (golden clouds) but dimmed for lighting via a Light-Path mix so the warm low
  sun still rakes the rows, over real CC0 ground texture, gently rolling terrain
  and a depth-of-field drone camera.

Reproducible via [`scripts/render_sim_feed.py`](../../../scripts/render_sim_feed.py)
(`blender --background --python …`) → PNG sequence → ffmpeg h264 (a subtle
vignette + light sensor grain are added at the ffmpeg stage). Blender is an
opt-in art tool, not a repo/CI dependency (like the `[cv]` extra). The terrain,
the row layout, the posts and the camera path are SwarmOS-authored, dedicated to
the public domain (CC0-1.0). The hills are SwarmOS-authored too.

## Assets

| Asset | Type | Source (license) |
|-------|------|------------------|
| `kloofendal_48d_partly_cloudy_puresky` | Sky HDRI (lighting + clouds) | https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky · Poly Haven · CC0-1.0 |
| `aerial_grass_rock` | Texture (terrain) | https://polyhaven.com/a/aerial_grass_rock · Poly Haven · CC0-1.0 |
| `shrub_01` | 3D model (vine plant, instanced) | https://polyhaven.com/a/shrub_01 · Poly Haven · CC0-1.0 |
| `island_tree_01` | 3D model (treeline, instanced) | https://polyhaven.com/a/island_tree_01 · Poly Haven · CC0-1.0 |

Poly Haven publishes all assets under CC0-1.0 (no attribution required; recorded
here for auditability). Assets are fetched from the public Poly Haven API at
render time, so nothing is committed to the repo.

## Files

| File | Codec | Geometry | sha256 prefix |
|------|-------|----------|---------------|
| `drone-pov.mp4` | h264 / yuv420p, 24 fps, 2.5 s | 1280×960 (4:3) | `bdebe97d4bc0f07a…` |
