# `/sim-feed/` — demo viewport clips

These are the clips the Console verification viewport (`LiveFeedFrame`) plays.
The Console draws the **`SIMULATED FEED`** stamp *over* the video (a component
overlay, not burned into the file), so the footage is always presented honestly
as a simulated viewport — never as a real live camera. The sim runner advertises
the per-unit `simulated` `StreamDescriptor` (`SWARM_SIM_FEED_PATH`); `dev_up.sh`
selects the per-scenario clip from the booted `SIM_SCENARIO`.

## What these clips are (demo build)

For the demos the founder asked for footage that simply **looks real**, at zero
cost. So the committed clips are **real, free-licensed stock drone footage of
vineyards** (Mixkit), conformed to the viewport shape. One clip per scenario so
the viewport fits what the operator is verifying:

| Clip | Scenario | Source (Mixkit, free license) |
|------|----------|-------------------------------|
| `drone-pov.mp4` | standby / default | "Sunset over vineyards" — [mixkit/8204](https://mixkit.co/free-stock-video/sunset-over-vineyards-8204/) |
| `search-pov.mp4` | search | "Drone flying across a Vineyard" — [mixkit/8292](https://mixkit.co/free-stock-video/drone-flying-across-a-vineyard-8292/) |
| `intrusion-pov.mp4` | intrusion | "Couple walking through a vineyard field" — [mixkit/29301](https://mixkit.co/free-stock-video/couple-walking-through-a-vineyard-field-29301/) |
| `wildfire-pov.mp4` | wildfire | **composite:** "Vineyards of Chianti in the afternoon" [mixkit/8296](https://mixkit.co/free-stock-video/vineyards-of-chianti-in-the-afternoon-8296/) + grey-smoke plate [mixkit/45298](https://mixkit.co/free-stock-video/grey-smoke-on-a-black-background-45298/), screen-blended with ffmpeg |

## License

All source footage is **Mixkit License** (free for commercial and personal use,
**no attribution required**): <https://mixkit.co/license/>. The clips are used as
in-app demo footage (a permitted use); the IDs above are recorded for
auditability. The wildfire clip is our own ffmpeg composite of two Mixkit clips.

## Honesty + design-rule note (read this)

- **Always stamped `SIMULATED FEED`** and shown as a *simulated* viewport — never
  passed off as the unit's real live camera. The platform logic is real; the
  camera feed is illustrative.
- **People**: real people appear only in `intrusion-pov.mp4`, and only as **small,
  distant, non-identifiable** figures in the rows (no recognisable faces); they
  are model-released stock, not the CV `person` score (which stays on the
  committed CC0 `person_aerial/` fixtures). The synthetic figure never feeds CV.
- **No red**: the wildfire clip shows **grey smoke only**, never a red/orange fire
  glow (PDF §5.2).
- **Design-rule tension, on purpose**: CLAUDE.md §Design system says
  `LiveFeedFrame` must "Never [show] a stock clip." Using stock footage here
  **deliberately relaxes that rule for demo realism** (founder decision), made
  safe by the always-on `SIMULATED FEED` label + recorded provenance. The strict
  alternative still lives in the repo — a CC0, fully-synthetic, reproducible
  Blender pipeline (next section). Swap back to it for any build that must comply
  strictly.

## Reproduce / swap a clip

- **Drop-in any clip**: `scripts/normalize_sim_feed.sh <input> <scenario> [start_s] [duration_s]`
  conforms any source video to the committed shape (1280×960 4:3, h264/yuv420p,
  faststart, no audio) and writes `frontend/public/sim-feed/<scenario>-pov.mp4`.
  The `<video loop>` element loops it, so a few seconds is enough.
- **Wildfire composite** (real vineyard + real smoke, no fire glow):

  ```
  ffmpeg -y -i chianti.mp4 -ss 2 -i grey_smoke.mp4 -filter_complex "
    [0:v]scale=1280:960:force_original_aspect_ratio=increase,crop=1280:960,setsar=1[bg];
    [1:v]scale=1500:1125,crop=1280:960:110:80,setsar=1,colorchannelmixer=rr=0.9:gg=0.9:bb=0.93[sm];
    [bg][sm]blend=all_mode=screen:all_opacity=0.82,format=yuv420p[out]" \
    -map "[out]" -t 6 -an -c:v libx264 -preset slow -crf 22 -movflags +faststart wildfire-pov.mp4
  ```
- **Strict CC0 synthetic alternative** (no stock): `scripts/render_sim_feed.py`
  renders the same four scenarios from CC0 Poly Haven assets in Blender
  (`SWARM_SIM_FEED_SCENARIO=<scenario> blender --background --python …`). Blender
  is an opt-in art tool, not a repo/CI dependency. See
  [`docs/cv/cv-live.md`](../../../docs/cv/cv-live.md).

## Files

All clips: h264 / yuv420p, 1280×960 (4:3), ~6 s, looped by the viewport.

| File | Scenario | sha256 prefix |
|------|----------|---------------|
| `drone-pov.mp4` | standby / default | `ec62bfde5aa503cf…` |
| `search-pov.mp4` | search | `4e3b77230d8fa8ba…` |
| `intrusion-pov.mp4` | intrusion | `2b2e2187f19c6cb6…` |
| `wildfire-pov.mp4` | wildfire | `463cae4cd90ed9a0…` |
