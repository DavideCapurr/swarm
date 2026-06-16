# Three-month code plan — summer 2026 (pre-BIEF → semester)

Created 2026-06-16. This is the founder's code-only execution plan for the
window before BIEF starts (Italian maturità June 2026, BIEF Bocconi
September 2026). It deliberately excludes market validation, pitch assets
and PX4/SITL/hardware de-risk — those are tracked elsewhere
([`swarm-roadmap-evidence-to-scale.md`](swarm-roadmap-evidence-to-scale.md))
and are the founder's explicit non-goals for this window.

## ⚠️ Roadmap-number disambiguation (read first)

There are two roadmaps with **conflicting Phase numbers**:

- [`swarmos-roadmap.md`](swarmos-roadmap.md) — the technical 0→100M plan.
  Its **Phase 8** = "Autonomy engine production (sim)", **Phase 9** =
  federation, **Phase 10** = ML/AI.
- [`swarm-roadmap-evidence-to-scale.md`](swarm-roadmap-evidence-to-scale.md)
  — the current execution order. Its **Phase 8** = market validation.

**This plan follows the `swarmos-roadmap.md` technical sub-phases.** Every
"8.x / 9.x / 10.x" ID below refers to that document, not to the market
Phase 8.

## Honest framing

The software is already past the YC-application stage on engineering
depth. The two genuine credibility gaps (zero market validation, zero
real-world flight evidence) are **out of scope by founder decision** for
this window. The added scope below (federation + RL) pushes the program
from ~3 months to **~6 months**; that is acceptable because SWARM
continues at semester cadence after BIEF. This plan therefore draws a
**September cut line**: what closes pre-BIEF vs what flows into the
semester.

## Non-negotiable dependency facts (these fix the order)

1. **10.C replaces the 8.B thresholds** — it cannot start before 8.B
   exists, and it needs the **8.B-bis shadow harness** to be validated.
   So 10.C comes after Track A.
2. **Phase 10 gate**: every ML model must pass shadow mode in sim +
   calibration audit + SHAP/attention saved to the decision log. So
   8.B-bis is the prerequisite for both 10.C and 10.E — build it once, in
   Track A.
3. **The deterministic safety shield (Phase 6.A) stays intact under every
   ML model.** Geofence / battery / link / weather are never bypassed.
4. **Phase 9 is a core refactor** (singleton `SwarmCoordinator` → per-cell
   coordinators). Doing it while decision logic is still changing causes
   churn — it comes after single-cell autonomy is frozen.
5. **10.E RL is the longest, riskiest pole.** Its gate is "beat the
   10.C/8.B baseline on a held-out set without weakening safety" — a
   research outcome, not a guaranteed implementation. It goes last so a
   slip drops the lowest expected-value item.

## Track A — Autonomy engine production (swarmos Phase 8)

Roadmap estimate: 3-4 weeks. All in sim.

| ID | Scope | Deliverable | Depends on |
|----|-------|-------------|------------|
| 8.B | `autonomy.py` complete: `VERIFY \| DISMISS \| ESCALATE \| WAIT` on every anomaly; per-scenario deterministic thresholds (config) | Extend the baseline R1/R2/R3 rules to the full set + `WAIT`; move thresholds from constants to per-scenario YAML | — |
| 8.A | Console default inversion → observatory. The 4 intents (`verify / hold-patrol / dismiss / return`) become override buttons, not the primary flow | Console surfaces autonomy decisions first; buttons remain as override | 8.B |
| 8.B-bis | Mandatory shadow mode for every new decider: decide + log + compare to a human baseline | Shadow decision logger + divergence report. **Open design item:** define the "human baseline" oracle per scenario (there is no human in sim) — without it the Phase 8 `<5%` gate is not measurable | 8.B |
| 8.C | Human-intervention hooks: soft override (cancel/modify an in-flight autonomous decision), timed policy nudge (raise/lower thresholds temporarily), kill switch (lands all sim drones — the single exception to the design-system no-red rule) | 3 new intents + UI; the kill switch reuses the existing `EMERGENCY_RTL_ALL` | 8.A, 8.B |
| 8.D | `AUTO` / `OVERRIDE` eyebrow everywhere in Console + timeline | Extend the existing `AUTO · R*` chip to cover override and all surfaces | 8.A, 8.C |

**Gate 8:** 100+ runs of the 3 scenarios with full autonomy, **< 5%**
divergence from the baseline oracle.

## Track B — Console redesign + live CV

| ID | Scope | Deliverable | Note |
|----|-------|-------------|------|
| M0 | Close the **in-flight uncommitted** redesign (TacticalBasemap + tactical↔satellite basemap toggle, per-state markers, `next.config.mjs` CSP for the tile hosts) | Finish, verify live via the preview server, add tests, branch + commit, regenerate the stale YC screenshots | ~80% done; the quick win that cleans the working tree |
| CV live | Take the 7.D baseline (YOLOv8 fire / VisDrone person, today opt-in with fixtures) to **real live perception in the 3 scenarios** | CV produces real scores that feed anomalies, not scripted values | `[cv]` wheels ~2 GB, AGPL — stays opt-in, out of the prod image |
| bbox overlay | Detection bounding-box overlay on the viewport/verify panel (the item STATUS attributes to "8.D / 10") | Real boxes + scores rendered in Console | depends on CV live |

## Added scope — federation + real ML

**Phase 9 — federation ("swarm of swarms")** (roadmap estimate 4-6 weeks)

| ID | Scope |
|----|-------|
| 9.A | `Swarm` entity in `core/swarm_core/messages.py` (id, current goal, assigned drones, area of responsibility, health) |
| 9.B | `SwarmCellCoordinator` per swarm instead of the singleton; lock per `swarm_id` |
| 9.C | Namespaced Redis bus per cell (`swarm:cell:<id>:telemetry`, `…:events`) |
| 9.D | `swarm_os/meta_coordinator.py`: assigns goals (not atomic missions) to cells — load balancing, coverage, reserve |
| 9.E | Inter-swarm mesh protocol (contract-net): `swarm:mesh:offer / request / commit` |
| 9.F | Dynamic swarm fusion/split |
| 9.G | Backpressure: a cell can refuse assignments under emergency |
| 9.H | Simultaneous multi-site in one instance (replaces Phase 6.B one-site-at-a-time) |

**Gate 9:** chaos test (random cell kills) → system converges with no
intervention; inter-cell mesh p95 < 200 ms in sim.

**Real ML — only the two requested (no 10.A/B/D-K)**

| ID | Scope | Depends on |
|----|-------|------------|
| 10.C | Anomaly-disposition classifier (gradient boosting, light, interpretable, **calibrated**) → **replaces the 8.B thresholds** | 8.B + 8.B-bis |
| 10.E | RL patrolling (PPO or contextual bandits) trained in sim | stable sim + patrol surface; convergence risk |

**Gate 10:** every model passes shadow mode in sim + calibration audit +
SHAP/attention saved to the decision log; the deterministic 6.A shield
stays intact underneath.

## Sequence (~6 months, dependency-ordered)

**Pre-BIEF (months 1-3) — the realistic, self-contained block:**
M0 redesign → 8.B → 8.A → 8.B-bis → CV live → 8.C → bbox overlay → 8.D →
gate 100+ runs. Plus a **first cut of 10.C** in shadow (the most tractable
ML; it rides the 8.B-bis harness). This is the block to have ready for the
BIEF decision gate.

**Semester (months 4-6+):** 10.C hardening (pass calibration + SHAP gate)
→ **Phase 9 federation** (the big refactor) → **10.E RL** (last, longest,
outcome not guaranteed).

## Out of scope (stays frozen)

CV custom training (10.A), tracking (10.B), MLOps/feature store (10.D-K),
10.F multi-agent RL, 10.H LLM; PX4/SITL and hardware; any new production
hardening. `make {lint,test,audit}` + voice/brand gates stay green at
every milestone (CLAUDE.md).

## Risk flag

**10.E RL is the only item that may produce nothing useful.** If a
calibrated 10.C already beats the thresholds by the end of the semester,
10.E risks being effort without payoff. It is queued last on purpose.

## Two decisions before any code

1. **Baseline oracle for the 8.B-bis gate.** "< 5% divergence from a human
   decision" in a sim with no human means a labelled reference policy per
   scenario. First design decision of Track A.
2. **Branching.** Work starts on a feature branch off `main`
   (e.g. `feature/phase8-autonomy`, `feature/console-redesign-cv`), never
   on `main`.

## Session boundaries (for execution)

One milestone = one session = one branch. Each session starts by reading
this file + [`STATUS.md`](../STATUS.md), implements one milestone, runs the
gates, updates STATUS, commits. Default start point: **M0** (close the
in-flight redesign).
