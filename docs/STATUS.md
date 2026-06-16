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

## Pending / not yet tracked

- M0 (Console redesign close) is on branch
  `feature/m0-console-redesign-close`. The `TacticalBasemap` redesign +
  live 3-scenario demo artifacts already shipped in `0d34891`; this
  milestone adds the missing test coverage (basemap geometry, tactical↔
  satellite toggle + persistence, per-state marker colours, CSP tile-host
  invariant — +24 frontend tests) and a live preview verification (CARTO
  tiles 200, toggle switches, zero CSP violations).
- Refreshed YC screenshots + the demo `.mov` (`docs/yc/videos/` empty)
  remain manual founder-machine steps — they need the full sim+backend
  WebGL capture harness driven through the scripted scenario states, not a
  backend-less render.

## Last verified gates

`make lint` + `make test` on 2026-06-16 (Python 3.13): ruff + mypy (184
files) + tsc clean; **776 passed / 23 skipped** (backend, 88.91% cov) +
**129 passed / 1 todo** (frontend), exit 0.

## Most recent changes

See [`STATUS-archive.md`](STATUS-archive.md) for the full dated changelog.
Latest entries:

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
