# `/sim-feed/` — synthetic SIM-labelled viewport clips

These clips are the CV-live **video sub-step**: a synthetic drone-POV feed served
same-origin to the Console viewport and stamped **`SIMULATED FEED`** (PDF §5.2 —
never a stock clip; this is our own labelled synthetic asset, not a real camera).
They are advertised to the Console by the sim runner as a `simulated`
`StreamDescriptor` (`SWARM_SIM_FEED_PATH`, see `sim/swarm_sim/runner.py`).

## Setting

Rendered to match where the demo is set — a **Langhe vineyard near Alba**
(Piedmont, Italy), the same place the three scenarios model
(`sim/swarm_sim/world.py` `DEFAULT_DOCK` = 44.70 N, 8.03 E). A low oblique drone
follows a figure walking an alley between the vine rows in **back view /
distance** (no recognisable face), consistent with the privacy posture in
`sim/swarm_sim/cv/fixtures/LICENSES.md`.

## How it was made

Blender 5.1, **path-traced in Cycles** (Metal GPU, 64 samples + OpenImageDenoise,
AgX view transform) for a photorealistic late-afternoon look — a physically-based
sky + warm sun, gently rolling terrain, trellised vine rows with leaf-level
colour variation, and a depth-of-field drone camera. Reproducible via
[`scripts/render_sim_feed.py`](../../../scripts/render_sim_feed.py)
(`blender --background --python …`) → PNG sequence → ffmpeg h264 (a subtle
vignette + light sensor grain are added at the ffmpeg stage). Blender is an
opt-in art tool, not a repo/CI dependency (like the `[cv]` extra). The terrain,
vine rows, the figure and the camera path are SwarmOS-authored geometry,
dedicated to the public domain (CC0-1.0).

## Assets

| Asset | Type | Source (license) |
|-------|------|------------------|
| Sky | Procedural atmosphere (Blender Sky Texture) | SwarmOS-authored · CC0-1.0 (no download) |
| `aerial_grass_rock` | Texture (terrain) | https://polyhaven.com/a/aerial_grass_rock · Poly Haven · CC0-1.0 |
| `forest_leaves_02` | Texture (vine canopy) | https://polyhaven.com/a/forest_leaves_02 · Poly Haven · CC0-1.0 |

Poly Haven publishes all assets under CC0-1.0 (no attribution required; recorded
here for auditability). The sky is the procedural Blender atmospheric model, so
no external sky/HDRI asset is bundled.

## Files

| File | Codec | Geometry | sha256 prefix |
|------|-------|----------|---------------|
| `drone-pov.mp4` | h264 / yuv420p, 24 fps, 2.5 s | 1280×960 (4:3) | `dec4426b4e644bde…` |
