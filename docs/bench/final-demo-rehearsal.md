# Final demo rehearsal

Status: **READY TO RECORD**

Date: 2026-08-15  
Baseline: `main` at `024fabda6d687599bf9455d133883c5f3fa31b81`  
Authoritative evidence: `docs/bench/artifacts/final-demo-rehearsal-2026-08-15.json`

This is the recording runbook for `/demo/intrusion`. It exercises the real Redis bus, backend/orchestrator, authenticated Console, and two PX4 SITL instances. It does not change or use the legacy `/` dashboard.

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

### Before event 1

- top connection status: `CONNECTED`;
- fleet includes `mav-001` and `mav-002` clean/available;
- no stale mission story from a previous take.

### Event 1 allocation

- `INTRUSION DETECTED`;
- `Fleet auction`;
- `SERVER REASONS`;
- both `mav-001` and `mav-002` marked `ELIGIBLE`;
- server score and score-breakdown values;
- `mav-002` marked `WINNER`;
- mission ledger owner is `mav-002`.

### Dispatch and arrival

- mission 1 reaches `EN_ROUTE`;
- then mission 1 shows `MISSION_ITEM_REACHED` as the evidence behind `ON_STATION`.

### Payload active

- `LIGHT ON`;
- `PX4 OUTPUT CONFIRMED`;
- `SPEAKER ACTIVE`;
- `SIMULATED` beside the speaker behavior.

### Event 2 while mission 1 is still active

- a second auction/story is present;
- `mav-002` is visibly `EXCLUDED · BUSY`;
- the exclusion includes mission 1's active mission id;
- `mav-001` is eligible and becomes the different winner;
- mission ledger contains exactly two simultaneous mission cards, one owned by `mav-002` and one by `mav-001`;
- at this concurrency point, mission 1 payload is still active and `LIGHT OFF` has not occurred yet.

### Cleanup and RTL

- `SPEAKER STOPPED` and still explicitly `SIMULATED`;
- `LIGHT OFF` with `PX4 OUTPUT CONFIRMED`;
- mission 1 shows `RTL COMMAND ACKNOWLEDGED`;
- mission 2 also shows `MISSION_ITEM_REACHED` and later `RTL COMMAND ACKNOWLEDGED`.

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
8. start `scripts/final_demo_rehearsal_probe.py`.

Do not reuse a previous take's backend process, Redis state, PX4 container, or already-open story state when validating a fresh take.

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
