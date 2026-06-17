# `/sim-feed/` — synthetic SIM-labelled viewport clips

These clips are the CV-live **video sub-step**: a synthetic drone-POV feed served
same-origin to the Console viewport and stamped **`SIMULATED FEED`** (PDF §5.2 —
never a stock clip; this is our own labelled synthetic asset, not a real camera).
They are advertised to the Console by the sim runner as a `simulated`
`StreamDescriptor` (`SWARM_SIM_FEED_PATH`, see `sim/swarm_sim/runner.py`).

## Setting

Rendered to match where the demo is set — a **Langhe vineyard near Alba**
(Piedmont, Italy), the same place the three scenarios model
(`sim/swarm_sim/world.py` `DEFAULT_DOCK` = 44.70 N, 8.03 E). The subject walks an
alley between the vine rows in **back view / distance** (no recognisable face),
consistent with the privacy posture in `sim/swarm_sim/cv/fixtures/LICENSES.md`.

## How it was made

Blender 5.1 (EEVEE), reproducible via
[`scripts/render_sim_feed.py`](../../../scripts/render_sim_feed.py)
(`blender --background --python …`) → PNG sequence → ffmpeg h264. Blender is an
opt-in art tool, not a repo/CI dependency (like the `[cv]` extra). The vine rows,
the figure and the camera path are SwarmOS-authored geometry, dedicated to the
public domain (CC0-1.0).

## Assets (all CC0-1.0)

| Asset | Type | Source (CC0-1.0) |
|-------|------|------------------|
| `alps_field` | HDRI (daylight) | https://polyhaven.com/a/alps_field · Poly Haven |
| `aerial_grass_rock` | Texture (terrain) | https://polyhaven.com/a/aerial_grass_rock · Poly Haven |

Poly Haven publishes all assets under CC0-1.0 (no attribution required; recorded
here for auditability).

## Files

| File | Codec | Geometry | sha256 prefix |
|------|-------|----------|---------------|
| `drone-pov.mp4` | h264 / yuv420p, 24 fps, 2.5 s | 640×480 (4:3) | `e23482d11a8524fc…` |
