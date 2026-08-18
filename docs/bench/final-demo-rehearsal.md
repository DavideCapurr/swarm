# Final demo rehearsal

Status: **READY TO RECORD**

Recorded takes: 2026-08-15, on `2685736` — the merge of PR #132, which is the first commit on `main` that carries the probe this runbook tells you to run. The earlier `024fabda` this file used to name predates the probe, so it never reproduced these instructions.  
Re-verified: 2026-08-18, on `b586663` plus the two fixes shipped with this update.  
Authoritative evidence: `docs/bench/artifacts/final-demo-rehearsal-2026-08-15.json`

This is the recording runbook for `/demo/intrusion`. It exercises the real Redis bus, backend/orchestrator, authenticated Console, and two PX4 SITL instances. It does not change or use the legacy `/` dashboard.

## What changed since the takes were recorded

The three takes below were recorded before the operational-console redesign
(`8292420` and the UI commits after it). That redesign did not touch the side of
the system the takes proved:

```bash
git diff --name-only 2685736..HEAD -- core swarm_os orchestrator adapters sim backend tests infra pyproject.toml uv.lock
# empty
```

Allocator, bus, mission runtime, PX4 path, payload policy and RTL semantics are
byte-identical to the run that produced the artifact, so the recorded truth
evidence still stands. What changed is the surface that renders it. That was
re-verified separately on 2026-08-18:

- `scripts/console_render_audit.py` at 2560 × 1440 over the four sampled frames:
  0 glyph collisions, 0 truncated readouts, decision-rail steps 01–06 in frame,
  on both the replay harness and the recorded-surface widths;
- a live authenticated boot of `/demo/intrusion` against a real backend and
  Redis: login → `CONNECTED`, no page scroll at 2560 × 1440, and an honest empty
  state (`No allocator frame yet`, `WAITING FOR FLEET STATE`) before any event;
- the on-screen checklist in [What `/demo/intrusion` must show](#what-demointrusion-must-show)
  below, rewritten against the current surface. It previously named labels
  (`INTRUSION DETECTED`, `Fleet auction`, `WINNER`) that the redesign replaced —
  following the old list would have read as a failed take.

Not re-run on 2026-08-18: the two-PX4 SITL sequence itself, which needs Docker
and a host the verification environment did not have. The take evidence for it
is the 2026-08-15 artifact, against unchanged code.

## Verified recording flow

The required sequence passed three consecutive clean takes:

1. clean startup: `mav-001` and `mav-002` are `DOCKED`, 100% battery, no current mission;
2. event 1 (`INTRUSION`) is published only after the authenticated Console reports `CONNECTED`;
3. SwarmOS publishes the authoritative auction with both units eligible, server-side score breakdowns, winner, mission id, and then the award;
4. winner `mav-002` dispatches and reaches `EN_ROUTE`;
5. `ON_STATION` is accepted only with `mavlink_mission_item_reached`;
6. presence payload starts: light `ON` is `mavlink_output_confirmed`; speaker `PLAY` remains explicitly `simulated`;
7. event 2 (`HEAT_SPOT`) is published while mission 1 is still active and before payload cleanup;
8. the event-2 auction excludes `mav-002` as `BUSY` with mission 1's exact `active_mission_id`, then selects different owner `mav-001`;
9. both missions are simultaneously active and visible in `/demo/intrusion` while mission 1 payload is still active;
10. mission 1 payload cleans up: speaker `STOP` is `simulated`, light `OFF` is `mavlink_output_confirmed`;
11. mission 1 closes only after `mavlink_rtl_command_acknowledged`;
12. mission 2 reaches `mavlink_mission_item_reached` and closes with `mavlink_rtl_command_acknowledged`.

The rehearsal probe validates the backend/bus truth directly. The browser check independently verifies that the authenticated Console renders that truth.

## Three consecutive clean takes

| Take | Result | Duration | Mission 1 owner | Mission 2 owner | Browser | Auth |
| --- | --- | ---: | --- | --- | --- | --- |
| 1 | PASS | 62.749 s | `mav-002` | `mav-001` | PASS | PASS |
| 2 | PASS | 62.128 s | `mav-002` | `mav-001` | PASS | PASS |
| 3 | PASS | 62.685 s | `mav-002` | `mav-001` | PASS | PASS |

The final successful GitHub Actions rehearsal was run `31901533790`, job `95052955813`. Its uploaded evidence artifact was `final-demo-live-rehearsal`, artifact id `9251283081`, SHA-256 `e55d6c9e6bc51e19a8a25472bbca1bd23254a1d8364b29dd1382e91e0a383aa3`.

## Exact startup

The validated host is Ubuntu 24.04 with Docker host networking. Keep `localhost` for the browser/API/WS origins; do not substitute `127.0.0.1:3000` for the Console origin.

Two host prerequisites, both silent when missing:

- **Node 24.** `frontend/.nvmrc` and `frontend/package.json` pin `>=24 <25`. An
  older Node still installs and still runs `pnpm dev` — it only prints an
  `Unsupported engine` warning — so a take can be recorded on the wrong runtime
  without anything on screen saying so. Run `node --version` before step 5.
- **A route to `a.basemaps.cartocdn.com`.** The map draws CARTO tiles under the
  local site frame as visual context. Tile failure never removes operational
  state — the site frame, agents, objectives and tracks are local — but the
  bottom attribution strip switches to `BASEMAP UNAVAILABLE · SITE FRAME ONLY ·
  NO EXTERNAL CONTEXT`, and that is what the recording will show. Check the host
  can reach the tile CDN, or record knowing the map band has no aerial context.

### 1. Prepare repo, dependencies, infrastructure, and real dev auth

From repo root:

```bash
git switch main
git pull --ff-only
make setup
make infra
make bootstrap-auth-dev
set -a
source .env
set +a

export SWARM_ENV=dev
export SWARM_ALLOWED_ORIGINS=http://localhost:3000
export SWARM_VENDORS=mavlink
export MAVLINK_FLEET='mav-001=udpin:0.0.0.0:14541,mav-002=udpin:0.0.0.0:14542'
export MAVLINK_MODEL=px4-iris-sitl
export SWARM_PRESENCE_RESPONSE=1
export SWARM_PRESENCE_MIN_CONFIDENCE=0.85
export SWARM_PRESENCE_HOLD_S=20
export MAVLINK_LIGHT_ACTUATOR_NUMBER=1
export MAVLINK_LIGHT_OUTPUT_CHANNEL=5
export SWARM_PRESENCE_SIMULATE_SPEAKER=1
export SWARM_COOPERATIVE_VERIFY=0
export NEXT_PUBLIC_API_URL=http://localhost:8765
export NEXT_PUBLIC_WS_URL=ws://localhost:8765/ws/telemetry
```

`make infra` populates the local Redis URL in `.env`; `make bootstrap-auth-dev` provisions the local auth store and JWT secret. The recording login is the dev viewer account created by that script.

### 2. Start two clean PX4 SITL instances

```bash
docker rm -f px4-final-demo >/dev/null 2>&1 || true

docker run -d --name px4-final-demo --network host \
  --entrypoint /bin/bash -e DISPLAY=:99 \
  jonasvautherin/px4-gazebo-headless@sha256:77f11913cbb2c4e9147a0ec0fdc4318e9575515e20e88d1f3cd9a21470ddcd21 \
  -lc 'rm -f /tmp/.X99-lock; Xvfb :99 -screen 0 1600x1200x24+32 & cd /root/Firmware && Tools/simulation/gazebo-classic/sitl_multiple_run.sh -m iris -n 2 -w empty'

sleep 8

docker inspect -f '{{.State.Running}}' px4-final-demo
```

The last command must print `true`.

### 3. Configure and verify the PX4 payload output

```bash
uv run python scripts/configure_px4_payload_output.py \
  --connections udpin:0.0.0.0:14541,udpin:0.0.0.0:14542 \
  --output-channel 5
```

Both PX4 systems must report a verified `PWM_MAIN_FUNC5 -> 301` mapping. The helper refuses to overwrite an unrelated active output function.

### 4. Start backend

In a dedicated terminal with the environment above exported:

```bash
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8765
```

Confirm:

```bash
curl -fsS http://localhost:8765/health
```

### 5. Start the Console

In another terminal, from `frontend/`, with the same `NEXT_PUBLIC_*` values:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8765 \
NEXT_PUBLIC_WS_URL=ws://localhost:8765/ws/telemetry \
pnpm dev --hostname localhost
```

Open:

```text
http://localhost:3000/login?next=/demo/intrusion
```

**Record at 2560 × 1440, browser zoom 100%, device pixel ratio 1**, as
[`docs/design/operational-console-ia.md`](../design/operational-console-ia.md) §3
specifies. That document is the authority on the size; this is a pointer to it,
not a second place to change.

It matters more than it looks. The Console's layout budgets are horizontal and
vertical at once, and the spec notes that smaller viewports *degrade rather than
break* — at 1920 × 1080 the control-loop strip starts truncating its live values
from T+44s and the decision rail drops step 04 below the fold, silently, with
nothing on screen to say so. Both are fine at the specified size. A take
recorded smaller has not been measured.

Verify the viewport before the first take rather than after:

```bash
# in the page console
innerWidth + '×' + innerHeight + ' @' + devicePixelRatio
```

Log in with the dev viewer created by `make bootstrap-auth-dev`, then wait until `/demo/intrusion` visibly says exactly `CONNECTED`.

**Do not trigger event 1 before `CONNECTED`.** The final deterministic rehearsal waited for that signal and then allowed a 1-second settle before publishing event 1.

### 6. Run the authoritative recording sequence

Only after the Console is `CONNECTED`:

```bash
sleep 1
uv run python scripts/final_demo_rehearsal_probe.py \
  --redis-url "$REDIS_URL" \
  --expected-agents mav-001,mav-002 \
  --timeout-s 220 \
  --json-out artifacts/final-demo-take.json
```

The probe emits the two events at the verified points in the mission lifecycle and fails non-zero if any required truth gate is missing or inconsistent.

### For a YC recording, use the recording scenario instead

`scripts/final_demo_rehearsal_probe.py` is the authoritative rehearsal: it is
what the artifact and the three takes were produced with, and it is what proves
the gates. It is not the best thing to point a camera at. Its event 2 sits about
2.1 m from `mav-001`'s SITL home, so the second aircraft's flight is essentially
invisible on screen.

`scripts/yc_demo_recording_probe.py` reuses `final_demo_rehearsal_probe.run`
unchanged — same gates, same failure behaviour — and moves event 2 only: 15 m
west and 20 m south of the recorded `mav-001` home, 25 m of displacement on a
different axis from event 1, so the second dispatch reads on camera.

```bash
sleep 1
uv run python scripts/yc_demo_recording_probe.py \
  --redis-url "$REDIS_URL" \
  --expected-agents mav-001,mav-002 \
  --timeout-s 220 \
  --json-out artifacts/yc-demo-take.json
```

Use the rehearsal probe to prove readiness, the recording probe to record. Do
not edit either one's geometry during a session; `/dev/replay` and the
2026-08-15 artifact are the fixed reference for the original recorded geometry.

## Trigger order

The trigger order is fixed and must not be improvised:

1. PX4 fleet is clean and backend fleet truth shows both agents `DOCKED` with no mission.
2. Authenticated Console is on `/demo/intrusion` and says `CONNECTED`.
3. Wait 1 second.
4. Probe publishes event 1: `INTRUSION`, confidence `0.95`, at `47.3980, 8.5460`.
5. Probe waits for allocation, award, `EN_ROUTE`, and verified `ON_STATION` with `mavlink_mission_item_reached`.
6. Probe waits for both payload start events: confirmed light `ON` and simulated speaker `PLAY`.
7. While mission 1 is still non-terminal and payload cleanup has not occurred, probe publishes event 2: `HEAT_SPOT`, confidence `0.99`, at `47.39775, 8.54559`.
8. Probe requires event 2 to exclude mission-1 owner as `BUSY` with the exact active mission id and to award a different owner.
9. Probe requires mission 2 `EN_ROUTE` while mission 1 remains active.
10. Probe then observes mission-1 payload cleanup, mission-1 accepted RTL acknowledgement, mission-2 `MISSION_ITEM_REACHED`, and mission-2 accepted RTL acknowledgement.

## What `/demo/intrusion` must show

Every string below was read off the rendered surface on 2026-08-18 at
2560 × 1440. The console was redesigned after the takes were recorded, so this
list is written against the surface as it is now, not as it was.

### Before event 1

- command bar reads `LINK CONNECTED`;
- `FLEET 002 AGENTS · 00 OWNING`, with `mav-001` and `mav-002` both `DOCKED`,
  100%, `no mission · available`;
- `OBJECTIVES 00 OPEN` and the decision rail says `No allocator frame yet` — no
  stale story from a previous take.

### Event 1 allocation

- objective queue grows `OBJ 01 · VERIFY INTRUSION`, `confidence 95%`,
  `owner mav-002`;
- decision rail step `01 OBJECTIVE` shows `INTRUSION`, `CONFIDENCE 95%`, the
  event id and the position;
- step `02 FLEET EVALUATED BY SWARMOS` shows `MODE · AUCTION` and `SERVER
  REASONS`;
- the winner row reads `mav-002 · SELECTED`, the other `mav-001 · ELIGIBLE` —
  the redesign marks the winner `SELECTED` rather than `WINNER`, and only the
  losing candidate carries `ELIGIBLE`;
- each row shows the score and its breakdown (`dist … · batt … · priority …`);
- step `03 SELECTED BY SWARMOS` shows `mav-002` with `WINNER SCORE 2.258` and
  the sentence `mav-002 selected · highest score of 2 eligible agents`;
- step `04 MISSION OWNERSHIP` shows `mission 4c97f2f2 owned by mav-002`.

### Dispatch and arrival

- step `05 PHYSICAL EXECUTION` ticks `ALLOCATED` → `DISPATCHED` → `EN ROUTE`,
  with `SERVER PHASE EN ROUTE`;
- step `06 EVIDENCE` holds at `NO EXECUTION EVIDENCE PUBLISHED` until arrival,
  then shows `ON STATION` with `MISSION_ITEM_REACHED · PX4 SITL`.

### Payload active

Under `BOUNDED PHYSICAL RESPONSE · FLEET`, headed `VERIFIED VS SIMULATED`:

- `LIGHT` — `mav-002`, `LIGHT ON`, `PX4 OUTPUT CONFIRMED`;
- `SPEAKER` — `mav-002`, `SPEAKER ACTIVE`, `SIMULATED`.

The two channels are fleet-wide, not focus-scoped: they stay on screen while the
rail follows objective 2.

### Event 2 while mission 1 is still active

- the rail follows the new objective by itself — `FOCUS OBJ 02`, `HEAT_SPOT`,
  `CONFIDENCE 99%`;
- step 02 shows `mav-002 · EXCLUDED · BUSY` with
  `ON_STATION · batt 97% · holds active mission 4c97f2f2`;
- `mav-001 · SELECTED` with its own score and breakdown;
- step 03 restates it in words: `mav-002 excluded · BUSY · already owns mission
  4c97f2f2` / `mav-001 selected · highest score of 1 eligible agent`;
- the mission timeline reads `CONCURRENT MISSION OWNERSHIP · 2 EXECUTING` with
  two swimlanes, one owned by `mav-002` and one by `mav-001` — this is where
  concurrency is proved, not in a card ledger;
- at this point the light channel still reads `LIGHT ON`.

### Cleanup and RTL

- `SPEAKER STOPPED`, still `SIMULATED`;
- `LIGHT OFF`, still `PX4 OUTPUT CONFIRMED`;
- mission 1's lane ticks `RTL` then `DONE`, and its evidence shows
  `RTL COMMAND ACKNOWLEDGED · PX4 SITL`;
- mission 2 shows `ON STATION` with `MISSION_ITEM_REACHED · PX4 SITL`, then
  `RTL COMMAND ACKNOWLEDGED · PX4 SITL`.

### Labels that must never disappear

- `RUNTIME TRUTH · PX4 SITL TELEMETRY · IMAGERY SIMULATED` in the command bar;
- `SIMULATED IMAGERY · NOT EVIDENCE` and `NOT A LIVE FEED` on the CCTV thumbnail;
- `SIMULATED` beside the speaker channel, in its own lane, never in the verified
  lane;
- `PROJECTED FROM PX4 SITL TELEMETRY` on the site frame, and the same source in
  the command bar's `RUNTIME TRUTH` and beside the focused executor's telemetry.
  These read `PX4 SITL TELEMETRY` because the units report `vendor: mavlink` and
  a model containing `sitl` — the label is derived, not asserted. If a take shows
  anything else there, the fleet is not the bench you think it is.

If any of these is missing from a take, the take is not usable — they are the
claim boundary, not decoration.

## Reset between takes

Keep the frontend dev server running if desired, but reset mission state, PX4, backend, and the browser session. The validated rehearsal used a new authenticated browser context every take.

Stop the backend, then:

```bash
docker rm -f px4-final-demo >/dev/null 2>&1 || true

uv run python - <<'PY'
import os
import redis

client = redis.Redis.from_url(os.environ["REDIS_URL"])
client.flushall()
client.close()
PY
```

Then repeat:

1. start a fresh two-instance PX4 container;
2. wait for it to be running;
3. run `scripts/configure_px4_payload_output.py` and require both verified mappings;
4. start a fresh backend process;
5. open a fresh browser/login session on `/demo/intrusion`;
6. wait for exact `CONNECTED`;
7. wait 1 second;
8. start `scripts/final_demo_rehearsal_probe.py` — or, for a take you intend to
   keep, `scripts/yc_demo_recording_probe.py`.

Do not reuse a previous take's backend process, Redis state, PX4 container, or already-open story state when validating a fresh take.

## Pre-session gate

Run this once before the first take of a session, not after. It is the cheap
half of the readiness question and it catches the failures that are invisible
in the viewfinder:

```bash
make lint
make test
make audit
cd frontend && pnpm dev            # leave running
uv run python scripts/console_render_audit.py
```

The render audit must report 0 glyph collisions, 0 truncated readouts, and
decision-rail steps 01–06 in frame at 2560 × 1440.

Its Playwright dependency is pinned in the `dev` extra, so `make setup` — which
the `make lint` / `make test` lines above already require — installs it. The
wheel carries no browser, so on a machine that has never run the audit, download
Chromium once:

```bash
uv run python -m playwright install chromium
```

That is a one-time per-machine step, not a per-session one; skip it if
`SWARM_CHROMIUM_PATH` or `PLAYWRIGHT_BROWSERS_PATH` already points at a build.
Nothing outside dev/bench inherits the dependency — extras are opt-in and
`backend/Dockerfile` syncs `--extra mavlink` only — so the deployed image is
unchanged. It was previously pulled per-invocation with
`uv run --with playwright`, which left it unpinned and absent from `uv.lock`;
on a clean checkout the plain command in this gate then failed with
`ModuleNotFoundError`.

## Known limitations

- The final rehearsal topology is two PX4 SITL vehicles. The separate four-PX4 cooperative proof and failover proof are prior validated benches, not re-run as part of this final recording rehearsal.
- `PX4 OUTPUT CONFIRMED` is real PX4 SITL command/output confirmation; there is no physical lamp in this bench.
- Speaker behavior remains intentionally and visibly `SIMULATED`.
- The Console's visual scene/map/video material remains simulated. Allocation, mission ownership, runtime evidence, payload events, exclusions, and acknowledgements come from backend/bus truth.
- Event 2 is deliberately `HEAT_SPOT`: it proves concurrent reallocation and `BUSY` exclusion while mission 1's intrusion payload remains active, without starting a second presence-response payload.
- The validated environment is Ubuntu 24.04 with Docker host networking. Docker Desktop/macOS networking should be revalidated before using the exact same container command on a Mac.
- Use `http://localhost:3000` for the Console in this dev-auth setup. The default backend origin allowlist is not the same as `http://127.0.0.1:3000`.

## Remaining blockers

None in the validated environment.

Open items that are not blockers, stated so a take is not recorded in ignorance
of them:

- the two-PX4 SITL sequence has not been re-run since 2026-08-15. The code it
  exercises is unchanged (see [What changed since the takes were recorded](#what-changed-since-the-takes-were-recorded)),
  but a session on a new host should treat its first take as a rehearsal;
- the basemap under the site frame comes from a public tile CDN. On a host that
  cannot reach it the map band carries the local site frame alone and says so;
- `/dev/replay` replays the original recorded geometry, not the YC recording
  scenario's event 2. Do not use it to preview where the second aircraft will
  fly.
