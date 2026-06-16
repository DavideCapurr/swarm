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

- Live 3-scenario demo artifacts (2026-06-15) and the in-flight Console
  redesign (`TacticalBasemap`) are **uncommitted** on `main`'s working
  tree — to be committed on a feature branch when the redesign milestone
  (M0) starts.
- Demo `.mov` screen recording (`docs/yc/videos/` empty) and refreshed YC
  screenshots remain manual founder-machine steps.

## Last verified gates

`make test` on 2026-06-16 (Python 3.13): **776 passed / 23 skipped**
(backend) + **105 passed / 1 todo** (frontend), exit 0.

## Most recent changes

See [`STATUS-archive.md`](STATUS-archive.md) for the full dated changelog.
Latest entries:

- 2026-06-14 — Phase 7 anomaly evidence layer (provenance + triggering
  signal per anomaly, honest sim, additive persistence, Console callouts);
  merged to `main`.
- 2026-05-31 — Phase 7 WS2: honest in-Console autonomy metrics +
  3-scenario capture tool.
- 2026-05-29 — Phase 7 WS1: live verify-loop fix (VERIFYING→VERIFIED
  promotion) + AUTO attribution persistence.
