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
| 5 | Real Adapter (MAVLink/PX4) | **CI-ready; SITL attempted/not validated; hardware pending** |
| 6 | Production OS (policy, geofence, auth, SBOM, ops) | **done** — 6.A→6.J all complete |
| 7 | Patrol Cell sim demo (3 scenarios + autonomy baseline + CV + anomaly evidence) | **done** — code-complete; live 3-scenario demo run 2026-06-15 (artifacts in `docs/bench/artifacts/`, `by_rule.R2==1`) |
| 8 | Patrol Cell wedge + customer validation | **next** (market) |
| 9 | Flight-path + PX4/SITL + hardware bench de-risk | **next** |
| 10 | Summer evidence pack + BIEF/YC future-batch decision | **planned** |

(Phases 8/9/10 above use the evidence-to-scale numbering.)

## Current focus

Phase 7 technical work is complete and the live demo gate was exercised on
2026-06-15 (the 3-scenario metrics artifacts exist; still untracked in git).

The founder's **summer code window (pre-BIEF)** is a code-only program
tracked in [`three-month-code-plan.md`](plan/three-month-code-plan.md). It
uses the **`swarmos-roadmap.md` sub-phase numbering** (Phase 8 = autonomy
engine, Phase 9 = federation, Phase 10 = ML) — *not* the evidence-to-scale
Phase 8. Order: Console redesign close → 8.A-8.D autonomy → live CV →
10.C classifier → Phase 9 federation → 10.E RL. Market validation
(evidence-to-scale Phase 8) and PX4/SITL are deferred by founder decision
for this window.

Window progress: **M0** (Console redesign close) merged (`#103`); **8.B**
(autonomy engine — full `VERIFY|DISMISS|ESCALATE|WAIT` decision set +
per-scenario YAML thresholds) merged (`#104`); **8.A** (Console default
inversion → observatory) **done** on `feature/phase8a-console-observatory`.
Next milestone: **8.B-bis** (mandatory shadow mode + divergence report).

## Pending / not yet tracked

- Refreshed YC screenshots + the demo `.mov` (`docs/yc/videos/` empty)
  remain manual founder-machine steps — they need the full sim+backend
  WebGL capture harness driven through the scripted scenario states, not a
  backend-less render.

## Last verified gates

`make lint` + `make test` + `make audit` on 2026-06-16 (Python 3.13):
ruff + mypy (186 files) + tsc clean; **800 passed / 23 skipped / 3
deselected** (backend) + **141 passed / 1 todo** (frontend); audit exit 0
(pip-audit + pnpm audit + bandit 0 high/med + integrity checks — no known
vulnerabilities).

## Most recent changes

See [`STATUS-archive.md`](STATUS-archive.md) for the full dated changelog.
Latest entries:

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
