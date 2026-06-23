#!/usr/bin/env bash
# Normalize any source video into a Console `/sim-feed/` demo clip — no Blender.
#
# The verification viewport (`LiveFeedFrame`) renders whatever clip lives at
# `frontend/public/sim-feed/<scenario>-pov.mp4` full-screen and draws the
# `SIMULATED FEED` stamp *over* it (the stamp is a component overlay, not burned
# into the file), so any realistic clip you drop in shows up honestly labelled.
# `dev_up.sh` already selects the per-scenario file from `SIM_SCENARIO`.
#
# This script just conforms a source clip to the committed shape: 1280x960 (4:3,
# matches the viewport), h264/yuv420p, faststart, trimmed, no audio. The
# `<video loop>` element loops it, so a short clip (a few seconds) is enough.
#
# Usage:
#   scripts/normalize_sim_feed.sh <input> <scenario> [start_seconds] [duration]
#     scenario ∈ standby | wildfire | intrusion | search
#
# Examples:
#   scripts/normalize_sim_feed.sh ~/Downloads/vineyard_aerial.mp4 standby
#   scripts/normalize_sim_feed.sh ~/Downloads/wildfire_smoke.mp4 wildfire 2 6
#
# IMPORTANT (honesty + licensing): only use footage you are licensed to use
# (CC0 / Pexels / Pixabay / Mixkit / your own). Record the source + license in
# frontend/public/sim-feed/LICENSES.md. The clip is shown as a *simulated*
# viewport (stamped), never passed off as a real live camera.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <input> <scenario:standby|wildfire|intrusion|search> [start_s] [duration_s]" >&2
  exit 2
fi

IN="$1"
SCEN="$2"
SS="${3:-0}"
DUR="${4:-6}"

case "$SCEN" in
  standby) OUT="drone-pov.mp4" ;;
  wildfire | intrusion | search) OUT="$SCEN-pov.mp4" ;;
  *) echo "scenario must be standby|wildfire|intrusion|search (got: $SCEN)" >&2; exit 2 ;;
esac

if [ ! -f "$IN" ]; then
  echo "input not found: $IN" >&2
  exit 2
fi

DST="frontend/public/sim-feed/$OUT"
echo "[normalize] $IN  ->  $DST  (ss=$SS dur=$DUR)"
ffmpeg -y -loglevel error -ss "$SS" -i "$IN" -t "$DUR" \
  -vf "scale=1280:960:force_original_aspect_ratio=increase,crop=1280:960,format=yuv420p" \
  -an -c:v libx264 -preset slow -movflags +faststart -crf 22 "$DST"

echo "[normalize] wrote $DST:"
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames \
  -show_entries format=duration -of default=noprint_wrappers=1 "$DST"
echo "[normalize] sha256: $(shasum -a 256 "$DST" | awk '{print $1}')"
echo "[normalize] done — record the source + license in frontend/public/sim-feed/LICENSES.md"
