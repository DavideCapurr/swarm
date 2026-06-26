# Pre-YC build plan — fix the demo climax, then sequence the 3-month surface

> **ARCHIVED 2026-06-26.** Mostly executed: WS1-WS3 shipped (PRs #103-#107),
> WS5 PX4/SITL evidence captured 2026-06-24. The only unbuilt item — WS4 citizen
> SOS — is deliberately deferred (it lives as conditional Phase 20 in the
> canonical roadmap). Kept for history. Current status: [`../../STATUS.md`](../../STATUS.md).
> Internal links below are relative to the original `docs/plan/` location.

> Status: **approved, pending execution** (to be executed in a later session).
> Branch for the immediate work (Workstream 1): `claude/dazzling-shannon-CDca7`.
> Commit convention: `phase-N: <subject>` (CLAUDE.md). Run
> `make lint && make test && make audit` + forbidden-word grep at the end of
> each shippable unit and update [`docs/STATUS.md`](../STATUS.md).

## Context

The question was which functionalities to pursue before YC and the roadmap
("M") phases. Chosen scope: **"3 months, everything we can"** at YC stage
**"Exploring"** (optimize for the strongest product story, no hard deadline).

Research surfaced a load-bearing defect: **the YC wildfire demo's climax does
not happen on a live run.** The VO script
([`docs/yc/m1-vo-script.md`](../yc/m1-vo-script.md)) builds to *"confidence
climbs to 88%, R2 auto-escalates"* at t≈35s, but R2 auto-ESCALATE never fires
in `make demo-wildfire-sim`. The repo's own a11y report already flagged this
and punted it to "M2" — but the **M1 YC video depends on it**. The pitch video
deliverable (`docs/yc/videos/demo-01-sim-wildfire.mov`) also does not exist
yet; only screenshots are committed.

This plan does two things: (1) specifies the **immediate, concrete fix** that
makes the demo climax real and closes Phase 7 honestly (Workstream 1), and
(2) lays out the **sequenced 3-month roadmap** (Workstreams 2–5) so we know
what to build, in what order, for maximum YC signal — and what to deliberately
*not* build.

Intended outcome: a bulletproof, reproducible autonomous demo whose every
on-screen number comes from SwarmOS (no fabrication), plus a credible path to
breadth (3 scenarios), autonomy-as-default (Phase 8), and the single
highest-leverage new build for a generalist partner — a one-tap citizen SOS
(Phase 12).

---

## Root cause (verified firsthand in code)

R2 ([`swarm_os/autonomy.py:141-154`](../../swarm_os/autonomy.py)) requires an
anomaly in state `VERIFIED` with `confidence ≥ 0.80`. In the live demo no
anomaly ever reaches `VERIFIED`, for two independent reasons:

1. **Nothing promotes `VERIFYING → VERIFIED` on VERIFY-mission completion.**
   R1 moves the anomaly `PENDING → VERIFYING`
   (`swarm_os/command_bus.py:297-307`) and spawns a *bookkeeping* mission
   `cmd-{command.id}`. That `cmd-` mission is **never executed** — the
   orchestrator independently subscribes to `swarm:anomalies` and opens its
   **own** `VERIFY` mission with a *different random uuid*
   (`orchestrator/swarm_orchestrator/service.py:77-82`), runs it on the
   simulated adapter, and publishes `MissionProgress(... phase="DONE")` under
   that uuid (`adapters/simulated/adapter.py:185`). The only existing
   `VERIFIED` setter (`swarm_os/coordinator.py:141`) just mirrors the raw sim
   `anomaly.verified` flag at creation time. So the executed VERIFY completes,
   but the anomaly stays stuck in `VERIFYING` forever.
2. **The FIRE follow-up is a separate anomaly, not a confidence bump.**
   `emit_anomaly` builds `Anomaly(...)` with no `id=`, minting a fresh uuid per
   scripted ignition (`sim/swarm_sim/perception.py:49-50`). So SMOKE (0.62) and
   FIRE (0.88) are two independent anomalies; there is no merge-by-proximity.

The integration test
`swarm_os/tests/test_phase7b_integration.py:179-188,257-273` **manually
forces** the anomaly to `VERIFIED`, which is why CI is green while the live
demo is broken.

> Correction to the initial instinct: the fix is **not** a one-liner in
> `command_bus.tick()`'s `cmd-` DONE branch — that branch never fires live.
> The promotion must happen where the *executed* mission's DONE arrives:
> `coordinator.apply_mission_progress`.

---

## Workstream 1 — Core demo bulletproofing (DO FIRST; unblocks everything) · effort L

The immediate executable work. Ships Phase 7 truly done and unblocks Phase 8.

### 1a. Promote the anomaly when the executed VERIFY mission completes
**File: `swarm_os/coordinator.py`, `apply_mission_progress` (lines 160-183).**
When an incoming `MissionProgress` has `phase == DONE` for a VERIFY mission,
resolve the target anomaly and promote it `VERIFYING → VERIFIED`:
- Add a helper `_anomaly_for_verify_mission(mission) -> str | None` that finds
  the anomaly currently in `VERIFYING` matching the mission's `sector_id` /
  waypoint geo (the executed mission has no `OperatorCommand` link, so resolve
  by VERIFYING-state + geo/sector, not by mission id).
- **Guards:** promote **only** if the anomaly is currently `VERIFYING`. Never
  clobber `DISMISSED` / `ESCALATED` / `PENDING` (a late completion must not
  resurrect a dismissed anomaly). On a `FAILED` VERIFY mission, leave the
  anomaly in `VERIFYING` (do not force back to `PENDING` — that would loop).
- On promote: `model_copy(update={"state": VERIFIED, "ts": now})`. Stamping
  `ts=now` starts R2's `AUTO_ESCALATE_IDLE_S` (10s) cleanly.
- Note ordering: autonomy tick runs **before** command tick in `_refresh`
  (`coordinator.py:261-262`), so R2 observes the freshly-VERIFIED anomaly on
  the **next** refresh, not same-tick — fine for the demo, but the test must
  encode it (1c).

### 1b. Make the wildfire climax read true (scenario/VO reframe)
With 1a, the FIRE anomaly (0.88) now flows: born PENDING → R1 auto-VERIFY →
executed VERIFY DONE → 1a promotes to VERIFIED → after 10s idle → R2
auto-ESCALATE. That *is* the VO story, but on the second detection, not a
rising single marker.
- **Recommended (Option 2, smaller blast radius, fully honest):** reword the VO
  climax in `docs/yc/m1-vo-script.md` to *"a higher-confidence fire signature
  is detected and auto-verified; the verified hotspot then auto-escalates."* No
  sim code change.
- *Alternative (Option 1):* give both scripted ignitions a shared logical `id`
  so the second updates the first (literal "confidence climbs on one marker").
  Requires an optional `id` on `ScriptedAnomalyCfg` (`sim/swarm_sim/scenario.py`)
  + `emit_anomaly` (`perception.py`). Keep in reserve.

### 1c. De-mask the tests + add the real regression
**File: `swarm_os/tests/test_phase7b_integration.py`.**
- Remove the manual `VERIFIED` forcing in both spots; instead drive a real
  `apply_mission_progress(phase="DONE")` and assert promotion through the
  production path.
- **New** `test_verify_mission_done_promotes_anomaly_then_r2_escalates_end_to_end`:
  full arc PENDING(≥0.80) → R1 VERIFY → executed mission DONE → VERIFIED (fresh
  `ts`) → advance ≥10s → R2 ESCALATE. (This is the test that would have caught
  the live bug; it must drive an extra `_refresh` to honor the tick ordering.)
- **Guards:** `test_failed_verify_mission_leaves_anomaly_verifying`;
  `test_done_verify_mission_does_not_resurrect_dismissed_anomaly`.
- Keep the negative control green: intrusion/search reach VERIFIED via real
  code but R2 does **not** fire (confidence < 0.80).

### 1d. Persist AUTO attribution after the command terminates · effort S
`findActiveAutonomyCommand` filters to non-terminal statuses
(`frontend/lib/autonomy.ts:12-16,29-34`), so the "AUTO · r1" chip vanishes the
moment the VERIFY command COMPLETES — exactly when "SwarmOS decided this"
matters most for the pitch.
- **File: `frontend/lib/autonomy.ts`** — add `findLatestAutonomyCommand(commands,
  anomalyId)` (most-recent autonomy command **regardless of status**; same
  sort, drop the terminal filter). Truthful — it reads a real audit record, not
  DERIVED fabrication. The frontend already retains terminal commands
  (`state.tsx` `upsertById`).
- **Switch these call sites** active→latest: `MobileAnomalyScreen.tsx:25`,
  `AnomalySummary.tsx:24`, `app/(console)/verify/[id]/page.tsx:27`, and
  `Map.tsx:210-212,372-389` (the on-callout chip the VO literally points at — a
  terminal ESCALATED callout reading `auto · r2 · anomaly escalated` is the
  money shot). `QuietPanel.tsx` RecentSection and `CommandTimeline`/`EventFeed`
  already read source/rule per-row — no change.
- Tests: extend `frontend/lib/autonomy.test.ts` + update `AnomalySummary.test.tsx`.

### 1e. Deterministic demo timing · effort S
Do **not** shorten the autonomy floors (`AUTO_VERIFY_DEBOUNCE_S=2.0`,
`AUTO_ESCALATE_IDLE_S=10.0`) for stagecraft — they're product behavior.
Instead tune scenario `after_s` so beats land in the recording window: FIRE at
`after_s:25` → R1 ~t27 → executed VERIFY → VERIFIED → +10s → R2 ~t37-40
(matches the VO t35 beat). Ensure the metrics collector `--duration`
(default 60s) spans R2.

### 1f. Close the Phase 7 hands-on gate + record the missing video · effort M (manual)
- Run `make demo-wildfire-sim` against the local Docker stack; capture per-beat
  screenshots (standby / SMOKE+R1 AUTO / FIRE+R2 AUTO / hold) into
  `docs/yc/screenshots/` using the existing `scripts/m1_capture_screenshots.py`.
- Confirm `docs/bench/artifacts/phase-7e-wildfire_owner_land-*.json` now shows
  `by_rule: {R1: ≥1, R2: 1}` (only truthful **after** 1a — the linchpin between
  "code-complete" and "gate green").
- Record `docs/yc/videos/demo-01-sim-wildfire.mov` (dir missing today; notes in
  `docs/yc/m1-vo-script.md:41-48`), using the reworded climax from 1b.
- Flip Phase 7 to fully `done` in `docs/STATUS.md` with cited command evidence.

**Security/voice/anti-overreach (WS1):** no new endpoints, no new deps. The
only behavior change is making an existing, intended autonomy rule reachable.
Run the forbidden-words grep on the updated VO script. No red. The `.mov` is a
real screen recording (no fake video).

---

## Workstream 2 — Demo breadth (3 legible arcs + honest metrics) · effort M

- **2a. All three scenarios become legible after 1a** (intrusion/search are
  stuck in `VERIFYING` today too). Audit each in-browser: wildfire =
  R1→VERIFIED→R2; intrusion (0.71) & search (0.55) = R1→VERIFIED→**operator
  owns escalation** (a *good* human-on-the-loop story). Capture screenshots for
  all three (`make demo-intrusion-sim` / `demo-search-sim` exist). **Do not**
  add per-scenario thresholds (that's Phase 8.B).
- **2b. Honest in-Console metrics surface.** The collector already computes
  `anomaly→decision` and `decision→dispatch` p50/p95
  (`scripts/scenario_metrics.py`). Build a read-only
  `frontend/components/AutonomyMetrics.tsx` (or extend QuietPanel's
  PerformanceSection) computing the same deltas client-side from the audit
  frames already in `useSwarm()`. **CSS/SVG-only** readouts — no external chart
  lib (CLAUDE.md §5.2). Label everything "(sim)". No new backend endpoint.

---

## Workstream 3 — Phase 8: Console inversion + autonomy production (M2) · effort L

Prerequisite: WS1 merged. Stay strictly inside roadmap §Phase 8 (8.A–8.D):
- **8.A** Console default → observatory; the 4 intents (verify/hold-patrol/
  dismiss/return) become **override** buttons. Frontend IA change
  (`TerritoryControl.tsx`, `ActionRail.tsx`, `QuietPanel.tsx`); backend
  unchanged.
- **8.B** Full `VERIFY|DISMISS|ESCALATE|WAIT` rule set with **per-scenario
  configurable thresholds** (where the thresholds avoided in Phase 7 finally
  belong). **8.B-bis** mandatory shadow mode (decide + log + compare to human
  baseline, no dispatch) — the "no autonomy that isn't verifiable" invariant
  made concrete.
- **8.C** Human-intervention hooks: soft override (reuse the
  operator-preempts-autonomy priority machinery, `command_bus.py:38,51`),
  policy nudge, and the kill switch (the **one** sanctioned "no red" exception —
  model it explicitly; reuse the `EMERGENCY_RTL_ALL` priority-200 precedent).
- **8.D** Rule-level `AUTO`/`OVERRIDE` eyebrows everywhere. **Here** add the
  server stamp `AnomalyView.decided_by`/`rule` (`core/swarm_core/messages.py` +
  `coordinator.py`) so attribution is robust even if a command ages out of the
  client window — making WS1d's client selector belt-and-suspenders, not
  throwaway.

---

## Workstream 4 — Phase 12: Citizen SOS web MVP (highest-leverage NEW build) · effort L

The demo that makes a generalist partner *feel* it: one tap on a phone → a
drone is dispatched, live. MVP slice = **12.B** (one-tap + cancel timer +
anti-misclick).

- **Framing (non-negotiable):** the citizen sends an **intent/event** ("help
  here"); SwarmOS plans the dispatch. The app **never** commands a drone — same
  invariant as the operator Console, extended to a new actor.
- **Surface:** a minimal **web** route group `frontend/app/(sos)/sos/page.tsx`
  (no operator chrome, no operator state), demoable on the founder's phone via
  LAN/tunnel. **Defer the native app (12.A)** and 12.C–H.
- **Contract:** new strict Pydantic `CitizenSosIntent` in
  `core/swarm_core/messages.py` — server-minted `id` (never client-supplied),
  optional `geo` (only with 12.D opt-in; coarse-area fallback otherwise), closed
  `kind` enum (`medical|fire|intrusion|other` — no free text → no PII, no voice
  violations), `created_at`, idempotency nonce. An SOS becomes a high-confidence
  anomaly flowing through the **existing** coordinator → command bus →
  orchestrator dispatch path (elegant: SOS is just another anomaly source).
- **Endpoint (new — justified; no public ingress exists today):**
  `POST /sos` in a new `backend/app/api/sos_routes.py`. **Most
  security-sensitive surface in the plan** — must carry every CLAUDE.md
  invariant: not behind the operator JWT (anonymous + aggressive per-IP/device
  rate limit, reuse `backend/app/security.py`); body-size + timeout limits;
  Pydantic strict; geo bounds-checked to the site geofence; no PII, no stack
  traces; CORS/WS origin allowlist extended explicitly (never `*`). Add
  `coordinator.apply_sos_intent` mirroring `apply_anomaly`.
- **12.B UX:** large SOS button; press-and-hold to arm + a 5s cancel countdown
  before the POST actually fires (satisfies cancel-timer + anti-misclick). The
  SOS button must be **amber/neutral, not red** (CLAUDE.md) — worth flagging
  since it feels counterintuitive.
- **Truthful ETA:** the citizen sees only their own SOS's mission state via a
  scoped, rate-limited `GET /sos/{id}/status` (real `MissionView.eta_s`, no
  fabrication; scoped by `sos_id` for privacy + the "citizen asks, SwarmOS
  decides" boundary).
- **Gate (roadmap):** "SOS → event → drone in < 2s", proven via the existing
  `decision→dispatch` latency metric.

---

## Workstream 5 — Phase 19 hardware bench (SEQUENCING NOTE ONLY)

Not built in the 3-month software window (hardware-dependent). The real
software-readiness gate is the still-unvalidated PX4 SITL path (Phase 5 is
"CI-ready; SITL not validated" per `docs/STATUS.md:16`). If slack remains after
WS1/WS2, the single highest-leverage de-risking task is to **actually validate
PX4 SITL in CI** (flip the Phase 5 caveat) — that's the gating unknown for
"we have flown," which is the eventual real pitch unlock (roadmap Phase 20).

---

## Deprioritize / keep sim-only (do NOT over-invest pre-pitch)

- **Phase 9 federation** — multi-week sim rebuild a generalist won't probe;
  resist pulling it forward during Phase 8 shadow mode.
- **Phase 10 custom ML** — keep the deterministic baseline; a half-trained model
  is a credibility *liability*. CV stays `cv_enabled:false` as it is today.
- **Phase 11 multimodal**, **Phase 13 city-scale dispatch**, **Phase 15
  multi-tenant/billing**, **Phases 16–18** — all defer; near-zero
  Exploring-stage pitch value. (8.B-bis shadow audit already gives a credible
  "every decision is logged + verifiable" story without the full signed log.)

---

## Recommended sequence

1. **WS1 (L)** — verify-loop fix + AUTO persistence + Phase 7 gate + record
   `.mov`. *First; unblocks the demo and Phase 8.*
2. **WS2 (M)** — three-scenario arcs (mostly free after WS1) + honest metrics
   panel.
3. **WS3 (L)** — Phase 8 console inversion + autonomy production + shadow mode.
4. **WS4 (L)** — Phase 12.B citizen SOS web MVP.
5. **WS5** — note only; optionally validate PX4 SITL if slack remains.

Each unit ends with `make lint && make test && make audit` green +
forbidden-word grep clean + `docs/STATUS.md` updated.

---

## Verification (end-to-end, for WS1 — the immediate work)

1. **Unit/integration:** `make test` — the new
   `test_verify_mission_done_promotes_anomaly_then_r2_escalates_end_to_end` and
   the two guard tests pass; de-masked tests pass via the production path; the
   intrusion/search negative control still shows no R2.
2. **Gates:** `make lint` (ruff + mypy + tsc) and `make audit` green;
   forbidden-words grep clean on the updated VO script.
3. **Live demo (the real gate, not the checklist):** `make demo-wildfire-sim`,
   open `http://localhost:3000`, sign in `op-viewer01`/`swarm-dev`. Observe the
   full arc end-to-end: standby → SMOKE 062% (R1 AUTO chip) → FIRE 088% →
   anomaly reaches **verified** → **R2 auto-ESCALATE** with the AUTO chip
   persisting on the escalated callout. Confirm
   `docs/bench/artifacts/phase-7e-wildfire_owner_land-*.json` shows
   `by_rule.R2 == 1`.
4. **Frontend:** `pnpm test` for the autonomy selector + AnomalySummary specs;
   visually confirm the AUTO chip survives terminal state on desktop + mobile.
5. **Deliverable:** `docs/yc/videos/demo-01-sim-wildfire.mov` exists and matches
   the reworded VO climax.
