# SwarmOS — execution status

Live, slim status. Read this first to see the current phase and what's
pending. **Full history** (per-phase completed checklists, resolved open
decisions, dated changelog) is in [`STATUS-archive.md`](STATUS-archive.md).
Append detailed phase write-ups to the archive; keep this file short.

Phase 0-6 technical plan: [`swarmos-roadmap.md`](plan/swarmos-roadmap.md).
Current Phase 7+ execution order:
[`swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md).

Product shape (2026-06-16): **SWARM Patrol Cell** — mobile patrol,
verification, evidence and escalation for private territories without
SWARM-owned fixed cameras/towers/ground sensors in the MVP. Wildfire-risk
patrol is the first beachhead, not the boundary.
See [`docs/product/patrol-cell.md`](product/patrol-cell.md).

## Current state

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Repo discipline + security baseline + shared types | **done** |
| 1 | SwarmOS Sim Kernel + endpoints + actions | **done** |
| 2 | Console Operating Shell + routing + components | **done** |
| 3 | Truth Layer (no DERIVED) | **done** |
| 4 | Persistence (Timescale + Alembic + audit) | **done** |
| 5 | Real Adapter (MAVLink/PX4) | **CI-ready; PX4 SITL-validated 2026-06-24 (`docs/bench/artifacts/phase9-sitl-probe.json` → `status:"pass"`); hardware pending** |
| 6 | Production OS (policy, geofence, auth, SBOM, ops) | **done** — 6.A→6.J all complete |
| 7 | Patrol Cell sim demo (3 scenarios + autonomy baseline + CV + anomaly evidence) | **done** — code-complete; live 3-scenario demo run 2026-06-15 (artifacts in `docs/bench/artifacts/`, `by_rule.R2==1`) |
| 8 | Patrol Cell wedge + customer validation | **next** (market) |
| 9 | Flight-path + PX4/SITL + hardware bench de-risk | **in_progress** — PX4 SITL adapter evidence captured 2026-06-24 (`docs/bench/phase9-sitl-validation.md`); flight-path planner + hardware bench still pending |
| 10 | Summer evidence pack + BIEF/YC future-batch decision | **planned** |

(All phase numbers use the **evidence-to-scale** roadmap — the single
canonical source. The old `swarmos-roadmap.md` Phase 7+ numbering, and the
summer code-window's Phase 8/9/10 = autonomy/federation/ML, are retired to
[`plan/archive/`](plan/archive/).)

## Current focus

Phase 7 technical work is complete and the live demo gate was exercised on
2026-06-15 (the 3-scenario metrics artifacts exist; still untracked in git).

**Strategy decision — 2026-06-26: evidence-first for YC (Early Decision).**
The binding constraints on a YC outcome are non-code, so the canonical plan
is the evidence-first order in
[`swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md)
(Phase 8 market validation → Phase 9 flight/SITL → Phase 10 evidence pack +
founder decision gate), executed against
[`yc/readiness-and-gaps.md`](yc/readiness-and-gaps.md).

Why (data review of YC admissions, 2026-06-26): acceptance ~0.6-1%; solo
founders are ~10% of batches at ~5× worse odds and must offset the handicap
with traction *or* elite technical depth; ~40% of funded companies are
pre-revenue, so the bar is *slope of progress* + *evidence people want it*
(deep customer interviews count as traction); the drones/defense vertical is
now actively funded but its bar includes real-world evidence (e.g. Theseus
shipped to US SOF). SWARM already clears the technical-depth axis; it scores
~zero on user evidence, demo video/live link, founder-commitment framing and
flight proof — exactly the axes YC rejects on. More autonomy/federation/ML
depth moves none of them. Early Decision fits the BIEF calendar (funded
immediately, place held until after graduation; deadline 2026-07-27).

**Immediate queue** (readiness-and-gaps order):
1. Gap #2 — record the <2-min demo video + deploy the live one-pager
   (`frontend/public/landing/`, set the contact email).
2. Gap #1 — 8-15 buyer/expert conversations in the Langhe
   ([`yc/customer-discovery-kit.md`](yc/customer-discovery-kit.md)); log real quotes.
3. Gap #5 — extend the PX4/SITL evidence started 2026-06-24
   ([`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md)) toward the bench plan.
4. By mid-July — decide Early-Decision vs Winter-2027 from real signal.

**On hold (not abandoned):** the summer code-only window (autonomy engine /
federation / ML), formerly `three-month-code-plan.md` → now
[`plan/archive/`](plan/archive/). It deepened the one axis already above the YC
bar; paused in favour of the evidence work above; revive on a concrete
acceleration trigger (CLAUDE.md). **Already shipped under that window and
staying merged:** **M0** Console redesign close (`#103`); **8.B** autonomy
engine — full `VERIFY|DISMISS|ESCALATE|WAIT` + per-scenario YAML thresholds
(`#104`); **8.A** Console default inversion → observatory (`#105`); **8.B-bis**
mandatory shadow mode + divergence report (`#106`); **CV live** real YOLO
`person` scores feeding intrusion+search anomalies (`#107`); **CV-live video
sub-step** per-scenario SIM-labeled drone-POV clips stamped `SIMULATED FEED`
(on `feature/cv-live-sim-feed`). Remaining federation/ML is deferred to its
evidence-earned position (evidence-to-scale Phase 17 intelligence / Phase 19
multi-cell).

Baseline-oracle decision (8.B-bis, the plan's "first design decision of
Track A"): the human-baseline oracle decides on the **same observable
signal** the engine sees (no ground-truth peeking, so it transfers to a
real deployment), but reasons in the PDF voice confidence **bands** with
documented per-scenario operator intent. Divergence = how often the tuned
float thresholds depart from band-level human judgment. See
`swarm_os/shadow_oracle.py` + `infra/config/autonomy_baseline.yaml`.

## Pending / not yet tracked

- **YC application pack drafted 2026-06-23** (`docs/yc/`): `application-draft.md`
  (fill-in-ready answers + founder/demo video scripts + typed-claim truth table),
  `readiness-and-gaps.md` (ranked gap analysis + dated plan; Early-Decision
  deadline 2026-07-27 vs Winter-2027 ~Nov), `customer-discovery-kit.md` (Langhe
  buyer interview script + outreach + one-pager), `supporting-answers.md`
  (flight/regulatory/TAM) + `competitive-and-market.md` (researched, cited).
  Founder decision A-vs-B deferred. Context: [[yc-winter-push]] memory.
- **YC live one-pager built 2026-06-23**: `frontend/public/landing/index.html` —
  self-contained static landing page, design-system compliant (no-red verified via
  preview eval, `SIMULATED FEED` honesty placard, typed-claim truth table). Hostable
  on any static host; deploy + set contact email to close YC gap #2's "live link"
  half. Preview locally via the `landing-static` launch config (port 4173, `/landing/`).
- Refreshed YC screenshots + the demo `.mov` (`docs/yc/videos/` empty)
  remain manual founder-machine steps — they need the full sim+backend
  WebGL capture harness driven through the scripted scenario states, not a
  backend-less render. **This is now gap #2 (critical) in the YC plan.**

## Last verified gates

`make lint` + `make test` re-run **2026-06-23** (Python 3.13) after the
per-scenario sim-feed clips: ruff + mypy (190 files) + tsc clean; **847 passed /
23 skipped** (backend) + **151 passed / 1 todo** (frontend);
`cv assets integrity: PASS fixtures=14` (the new viewport clips are correctly
*not* in the CV fixture pool). `make audit` now flags **one pre-existing
transitive CVE** — `msgpack 1.1.2` (GHSA-6v7p-g79w-8964, via `cachecontrol`, fix
1.2.1), a newly-published advisory unrelated to the video work, tracked as a
separate dependency bump (do not allowlist; root-cause via `uv lock`). The full
2026-06-17 gate (audit exit 0 incl. pnpm audit + bandit 0 high/med) otherwise
stands. Shadow gate: `make shadow-divergence` → **0%** divergence
over 100 runs of the 3 scenarios (deterministic), within the < 5% Phase 8
gate (`docs/bench/artifacts/phase-8bbis-shadow-*.json`). CV-live gate:
`make cv-live` (opt-in `[cv]`, verified in an ephemeral `uv run --with` env
so the 2 GB AGPL surface never enters `.venv`) → real `person` scores
**0.946** (intrusion) / **0.860** (search), ≥ 0.25 floor
(`docs/bench/artifacts/cv-live-*.json`); `make test-cv` → **10 passed**.

## Most recent changes

See [`STATUS-archive.md`](STATUS-archive.md) for the full dated changelog.
Latest entries:

- 2026-06-23 — demo viewport clips → **real "looks-real" footage** (founder ask):
  the committed `frontend/public/sim-feed/*.mp4` are now **real, free-licensed
  (Mixkit) stock drone-vineyard clips** instead of the Blender renders —
  standby = sunset-over-vineyards, search = drone-over-rows, intrusion = a couple
  (small, distant, non-identifiable) in the rows, wildfire = a Chianti aerial
  ffmpeg-composited with a grey-smoke plate (grey only, no fire glow). Still
  stamped `SIMULATED FEED` by the Console (overlay, not burned in) — never a live
  camera. New `scripts/normalize_sim_feed.sh` conforms any clip to the viewport
  shape (1280×960, h264). This **deliberately relaxes the "never a stock clip"
  design rule for demo realism** (recorded + justified in
  `frontend/public/sim-feed/LICENSES.md`); the CC0 Blender pipeline below stays as
  the strict-compliance alternative. `dev_up.sh` selection + `StreamDescriptor`
  contract unchanged.
- 2026-06-23 — CV-live video sub-step **per-scenario clips**: the single generic
  patrol clip became **one photoreal drone-POV clip per demo scenario** so a demo
  viewer sees a viewport that fits what the operator is verifying —
  `wildfire-pov.mp4` (a grey smoke plume rising from the rows), `intrusion-pov.mp4`
  (one figure on the vineyard access lane, back-view), `search-pov.mp4` (the same
  figure, small + distant, over a wider sweep), plus the unchanged `drone-pov.mp4`
  standby/default. All four are the **same** photoreal Langhe vineyard (real CC0
  Poly Haven instances) from [`scripts/render_sim_feed.py`](cv/cv-live.md), now
  parametrized by `SWARM_SIM_FEED_SCENARIO`; the smoke (a noise-driven Cycles
  volume, no bake) and the figure (a low-poly SwarmOS-authored proxy) are both
  **honest sim ambiance** — the figure is non-identifiable (back-view, not a real
  likeness), never enters the CV fixture pool and never feeds the `person` score;
  the smoke is grey-only (no red/orange fire glow, PDF §5.2) and wildfire CV stays
  deferred. `dev_up.sh` selects the clip from the booted `SIM_SCENARIO` (backend
  re-validates against the `/sim-feed/` prefix allowlist, so the new names need no
  security change). Provenance: `frontend/public/sim-feed/LICENSES.md`,
  [`docs/cv/cv-live.md`](cv/cv-live.md). Sim wiring + `StreamDescriptor` contract
  unchanged.
- 2026-06-21 — CV-live video sub-step **photorealism pass**: re-rendered the
  Langhe-vineyard drone-POV clip (`frontend/public/sim-feed/drone-pov.mp4`) to a
  genuinely photorealistic, demo-neutral shot. The key change: the vines are now
  **thousands of instances of a real CC0 Poly Haven plant model** (`shrub_01`,
  actual leaf geometry with alpha) stacked into rows — real foliage, not faked
  texture on a box (instancing shares one mesh, so the field stays cheap). A
  drone holds station over the rows looking down the vineyard, **no figure** (a
  calm patrol that fits every wildfire-demo phase, nothing identifiable). Full
  Langhe landscape: tall five-high vine walls with per-plant tint variation, a
  real CC0 `island_tree_01` treeline + rolling green hills on the horizon, under
  golden-hour light. Cycles (Metal GPU, 96 spp + OIDN, AgX), lit by a real CC0
  sky HDRI (`kloofendal_48d_partly_cloudy_puresky` — warm-tinted, image-based
  light + clouds via a Light-Path mix so the warm low sun still rakes the rows)
  over a CC0 `aerial_grass_rock` ground. Provenance/reproduction rewritten in
  `scripts/render_sim_feed.py`; `frontend/public/sim-feed/LICENSES.md`,
  `sim/swarm_sim/cv/fixtures/LICENSES.md` (sim_drone_pov re-shas) and
  `docs/cv/cv-live.md` updated. Sim wiring + `StreamDescriptor` contract
  unchanged.
- 2026-06-17 — CV-live **video sub-step** (three-month plan, Track B): the
  verification viewport now shows a synthetic SIM-labeled drone-POV clip instead
  of only the `VIEWPORT PENDING` placard. **Setting matches the demo** — a
  **Langhe vineyard near Alba** (the place `world.py` models), parallel vine
  rows, subject walking an alley in **back view** (the same non-identifiable
  privacy rule as the real `person_aerial/` fixtures). Rendered in Blender from
  **CC0-1.0** Poly Haven assets (`alps_field` HDRI + `aerial_grass_rock`),
  reproducible via `scripts/render_sim_feed.py` (Blender is an opt-in art tool,
  not a repo/CI dep — like `[cv]`). New: `StreamDescriptor` gained a third honest
  state — `simulated=True` carrying a **same-origin** `/sim-feed/…` path (zero
  SSRF surface; a forged external/`..` url is rejected by the backend
  re-validation), Console `LiveFeedFrame` renders it stamped **`SIMULATED FEED`**
  (monochrome, never amber — it's an honesty label, not a state), the sim runner
  advertises it per unit on `SWARM_SIM_FEED_PATH` (`dev_up.sh` turns it on for
  the demo when the clip is present), and a `media-src 'self'` CSP pin. Clip +
  provenance: `frontend/public/sim-feed/`. The clip also **feeds the CV fixture
  pool** (`sim/swarm_sim/cv/fixtures/sim_drone_pov/`, integrity-gated) but does
  **not** drive anomaly confidence — the live `person` scores stay on the real
  CC0 frames (honest-sim: a synthetic figure is never a real detection). +25
  tests (core/streams, frontend LiveFeedFrame + sim-feed allowlist, sim runner
  publisher, backend re-broadcast + forged-url drop, fixture-pool). See
  [`docs/cv/cv-live.md`](cv/cv-live.md).
- 2026-06-17 — CV live (three-month plan, Track B) real perception: the
  `person`-class scenarios now feed **real YOLOv8 scores** to the bus
  instead of scripted YAML values. Replaced the zero-pixel `person_aerial/`
  placeholder fixtures (which scored 0.0) with 4 **real CC0-1.0** frames of
  non-identifiable people (back-view / distance; CC0 covers the
  photographer's copyright, the back-view rule the subject's likeness) —
  provenance + real scores recorded in `fixtures/LICENSES.md`. intrusion →
  `person` **0.946**, search → **0.860** (were scripted 0.71 / 0.55).
  Wildfire stays `cv_enabled:false` **on purpose** (fire/smoke-CV deferred to
  drone-day — COCO has no fire class; its scripted 0.62/0.88 keep driving the
  R1→R2 path + the 0% shadow gate). Caught + fixed a real supply-chain drift:
  the pinned `yolov8n.pt` sha no longer matched the bytes GitHub serves
  (Ultralytics re-published the asset) → re-verified + re-pinned
  (`f59b3d83…`). New `scripts/cv_live_report.py` + `make cv-live` (real-score
  evidence bench, regression floor gate) and `test_cv_live_e2e.py` (replaces
  the now-obsolete wildfire e2e cv test). Verified end-to-end on the real
  repo path in an **ephemeral** CV env (`uv run --with`, no `.venv`/lockfile
  mutation — matches the opt-in/out-of-prod AGPL posture). Default
  `make {lint,test,audit}` stay green without the `[cv]` extra. The CV-live
  **video sub-step** (Blender SIM-feed) is the next, separate step. See
  [`docs/cv/cv-live.md`](cv/cv-live.md).
- 2026-06-16 — 8.B-bis (three-month plan) mandatory shadow mode +
  divergence report: the prerequisite the plan calls out for 10.C/10.E —
  every new decider must `decide + log + compare to a human baseline`
  before it is trusted. New `swarm_os/shadow.py` (a pluggable `Decider` =
  `(state, now) → dispositions`; `ShadowDecisionLog` + `DivergenceReport`
  with the `< 5%` `GATE_DIVERGENCE`) and `swarm_os/shadow_oracle.py`
  (`BaselineOracle` — the human-baseline reference, committed in
  `infra/config/autonomy_baseline.yaml`). **Design decision** (the plan's
  open item): the oracle decides on the *observable* signal only — kind,
  confidence, lifecycle state, hold_patrol — in PDF voice **bands**, with
  per-scenario intent (wildfire escalates a verified hotspot; intrusion/
  search reserve escalation for the operator; search verifies even faint
  heat-spots). No ground-truth peeking, so the same policy transfers to a
  real deployment. New `scripts/shadow_divergence.py` (+ `make
  shadow-divergence`) runs the real engine in shadow over the 3 scenarios:
  **0%** divergence deterministic (engine matches the baseline on every
  canonical decision point); at σ=0.05 CV jitter ≈0.7% overall, and the
  per-scenario gate correctly *fails* (>5%) under large jitter — the gate
  has teeth. +26 backend tests (→ 829). Console + live backend path
  untouched (the harness only observes deciders).
- 2026-06-16 — 8.A (three-month plan) Console default inversion →
  observatory: the viewport rail now leads with *what SwarmOS decided*.
  New `autonomyStance()` selector (`frontend/lib/autonomy.ts`) collapses
  the focus anomaly + autonomy commands into `decided | holding | clear |
  manual`; new `AutonomyDecision` component renders the verdict (verb +
  `AUTO · R*` Orbital-Blue chip + status sub-line) and demotes the four
  operator intents to ghost override buttons under an `— override`
  eyebrow. `QuietPanel` leads with the decision block when
  `autonomy_enabled`; the legacy operator-led `InlineActions` only renders
  on the autonomy-off path (zero regression for non-autonomy sites).
  `ActionRail` (verify route) gains the same `— override` framing. Voice-
  clean copy in `lib/copy.ts`; no red (decision accent is Orbital Blue).
  +12 frontend tests (→ 141). Console-only; no backend change.
- 2026-06-16 — 8.B (three-month plan) autonomy engine complete: the
  deterministic engine now returns an explicit `VERIFY|DISMISS|ESCALATE|
  WAIT` verdict on **every** anomaly (`autonomy.decide_all`) and the four
  thresholds moved from module constants to per-scenario profiles loaded
  from `infra/config/autonomy.yaml` (`swarm_os/autonomy_config.py`, routed
  by `AnomalyKind` — wildfire/intrusion/search + a `default` fallback).
  `tick()` is now the actionable adapter (gates `autonomy_enabled`, drops
  WAIT) so the coordinator + Phase 7.B command path are unchanged; the
  Phase 7.B constants now derive from the `default` profile (single source
  of truth). +24 backend tests (→ 803). No Console change (that's 8.A).
- 2026-06-16 — M0 (three-month plan) Console redesign close: added the
  missing test coverage for the shipped `TacticalBasemap` redesign —
  procedural geometry, tactical↔satellite basemap toggle + localStorage
  persistence, per-state marker colours (no-red guard), and a CSP↔basemap
  tile-host invariant (+24 frontend tests → 129). Exported the basemap
  helpers from `Map.tsx` for testability (no behaviour change) and
  live-verified the basemap + CSP in the preview server (CARTO tiles 200,
  toggle works, no console/CSP errors).
- 2026-06-14 — Phase 7 anomaly evidence layer (provenance + triggering
  signal per anomaly, honest sim, additive persistence, Console callouts);
  merged to `main`.
- 2026-05-31 — Phase 7 WS2: honest in-Console autonomy metrics +
  3-scenario capture tool.
- 2026-05-29 — Phase 7 WS1: live verify-loop fix (VERIFYING→VERIFIED
  promotion) + AUTO attribution persistence.
