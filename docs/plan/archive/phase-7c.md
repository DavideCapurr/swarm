# Phase 7.C — Console "AUTO" eyebrow + observatory surface

> **ARCHIVED 2026-06-26.** Completed implementation spec for a shipped phase
> (Phase 7 is `done`). Kept for history. Current status: [`../../STATUS.md`](../../STATUS.md).
> Internal links below are relative to the original `docs/plan/` location.

> Branch: `claude/plan-phase-7c-EDLfj`. Predecessor sub-phases done:
> 7.A (3 owner-land scenarios + loader), 7.B (autonomy baseline kernel
> R1/R2/R3 + `OperatorCommand.source` + scenario opt-in via
> `autonomy_baseline: true`). 7.C pre-flight already merged via PR #57
> (`claude/phase-7c-unblock-live-frames`): autonomy commands now
> broadcast live WS frames from `_refresh_async` and persist from
> `bus_consumer` — i.e. the data the Console needs is already on the
> wire and in the DB. 7.C is the **rendering** half.

## Codebase readiness for 7.C

| Check | Evidence |
|-------|----------|
| Branch state | `claude/plan-phase-7c-EDLfj`, working tree clean (`git status`). |
| Phase 7.B suite | STATUS.md updated 2026-05-20: **684 passed / 16 skipped / 3 deselected**. |
| Module spot-check this session | `pytest swarm_os/tests -x -q` → **122 passed in 1.17 s**. |
| Lint spot-check this session | `ruff check swarm_os/autonomy.py command_bus.py coordinator.py` → all checks passed. |
| 7.B contract surfaces | `OperatorCommand.source` exists at `core/swarm_core/messages.py:485`; `AUTONOMY_OPERATOR_ID = "swarmos-autonomy"` at `swarm_os/command_bus.py:52`; `SwarmState.autonomy_enabled` at `swarm_os/state.py:78`. |
| Frontend type plumbing | `OperatorCommand.source` already on `frontend/lib/api.ts:248` (added in 7.B). |

Caveat: full readiness (`rm -rf .venv && make setup && make lint && make
test && make audit`) was not re-run end-to-end in this planning session
— STATUS.md (1 day old) is the authoritative full-suite gate. The
above is a targeted spot-check. The end-of-7.C gate below re-runs the
full cycle.

## Context

7.B landed the autonomy baseline kernel: three deterministic rules
(R1 auto-VERIFY, R2 auto-ESCALATE, R3 auto-DISMISS) dispatch through the
existing operator command bus, every decision lands in
`state.commands` with `source="autonomy"` + the
`AUTONOMY_OPERATOR_ID` sentinel, audited and WS-broadcast. The audit log
already distinguishes operator vs autonomy rows.

7.C is the **Console surface** for that distinction. Per the roadmap
(`docs/plan/swarmos-roadmap.md:871-872`):

> **7.C** Console esistente come "osservatorio" con eyebrow `AUTO` per
> ogni decisione autonoma.

Translation: existing Console as "observatory" with an `AUTO` eyebrow
on every autonomous decision. The operator must be able to tell at a
glance — never by hovering, never by drilling down — which lifecycle
transitions on the spread were issued by SwarmOS rather than by them.

What 7.C does **not** do (anti-overreach, CLAUDE.md §10):

- Does **not** invert the Console default into observatory mode —
  that's Phase 8.A.
- Does **not** add per-scenario thresholds, WAIT decisions, shadow mode,
  soft override, kill switch — Phase 8.B / 8.C.
- Does **not** change the rules (R1/R2/R3 thresholds stay literal in
  `swarm_os/autonomy.py`).
- Does **not** wire CV inference — Phase 7.D.
- Does **not** add `make demo-*` one-liners — Phase 7.E.

## Decisions (recommended)

1. **`AUTO` eyebrow chip in Orbital Blue**, eyebrow tier (Space
   Grotesk uppercase 0.18 em tracking, per PDF §5.2 spread 13).
   Never amber, never red, never accent green — Orbital Blue is the
   "system focus" colour and is the right read for "SwarmOS issued this
   decision, not the operator". No new design tokens, no new SVG; the
   chip is plain text inside the existing `Eyebrow` component or a
   `StatusPill state="connected"` reuse where the chip needs a halo.

2. **Persist `Event.source` on disk** via a 0004 additive Alembic
   migration. Rationale: the EventFeed survives backend restarts via
   the 200-row backfill in `backend/app/main.py` (Phase 4) — if
   `source` only lives on the WS frame, every restart loses the AUTO
   distinction for the timeline tail. The migration is additive,
   default `"operator"`, portable to both Timescale (in-place column
   add on the hypertable) and SQLite. Backfill is the default value;
   no row-by-row rewrite needed.

3. **Surface `Session.autonomy_enabled`** so the HeadBar can render a
   single global `AUTONOMY BASELINE` chip when the kernel is operating
   autonomously. Reads from `state.autonomy_enabled` (already wired in
   7.B); emitted in the same Session frame the Console already
   subscribes to.

4. **Four placement points** for the `AUTO` chip on the Console:
   1. `HeadBar` — global `AUTONOMY BASELINE` chip when
      `session.autonomy_enabled` is true.
   2. `CommandTimeline` — `AUTO` chip in the leading slot (currently
      shows the action name) for any row with `source === "autonomy"`.
   3. `EventFeed` — `AUTO` chip in the kind column for `OPERATOR`-kind
      events with `source === "autonomy"`.
   4. `AnomalySummary` (+ mirrored on `/verify/[id]`) — `AUTO · {action}`
      chip next to the band pill when the most recent non-terminal
      command on this anomaly has `source === "autonomy"`.

5. **No `rule` (R1/R2/R3) in the Console.** The audit body already
   names the rule (e.g. "autonomy verify dispatched · R1") for forensic
   inspection. Hoisting the rule into the UI as a separate field would
   front-run Phase 8.B's per-scenario threshold surface. Keep 7.C tight.

6. **No new external dependencies.** Vitest + Testing Library + Pydantic
   + Alembic + SQLAlchemy are already in.

## Files to create / modify

### Backend — schema + projection

- **`core/swarm_core/messages.py:325-333`** — add
  `autonomy_enabled: bool = False` to `Session`.
- **`core/swarm_core/messages.py:450-465`** — add
  `source: Literal["operator", "autonomy"] = "operator"` to `Event`.
- **`swarm_os/state.py:83`, `swarm_os/state.py:113-118`** — `from_site_config`
  and `vineyard()` populate `session.autonomy_enabled` from
  `state.autonomy_enabled` (7.B already reads the env / YAML flag here).
- **`swarm_os/event_detector.py:264-291`** — `_command_event` reads
  `command.source` and switches the body copy:
  - operator: unchanged ("operator intent submitted · verify", …).
  - autonomy: "autonomy verify dispatched · R{n}" / "autonomy escalate
    dispatched · R{n}" / "autonomy dismiss dispatched · R{n}". Rule
    label optional and only present when the coordinator stamped it
    on the command (see open question 1 below). Returned `Event`
    carries `source=command.source`. Voice-clean (no `Manual`,
    `Intruder`, `red`, `alarm`).
- **`swarm_os/coordinator.py`** (the `_refresh` / autonomy-dispatch
  path) — when minting the autonomy `OperatorCommand`, optionally
  stamp the rule label as a structured field (see open question 1).
- **`backend/app/db/models.py`** — add `source: str` column to
  `EventRow` (default `"operator"`).
- **`backend/app/db/migrations/versions/20260520_0004_phase7c_event_source.py`** —
  additive migration: add `source` to `events` (`server_default='operator'`,
  non-null). Portable to both Postgres/Timescale and SQLite. Includes
  `downgrade()` for the Alembic round-trip test.
- **`backend/app/db/repository.py`** — `write_events` upserts `source`;
  `list_events` returns it.
- **`backend/app/bus_consumer.py`** — when persisting events, propagate
  `source` from the in-memory `Event` (no other change).

### Frontend — types, state, rendering

- **`frontend/lib/api.ts`** — `Session` adds `autonomy_enabled: boolean`;
  `TimelineEvent` adds `source: "operator" | "autonomy"`. The
  `OperatorCommand.source` field is already there from 7.B.
- **`frontend/lib/state.tsx`** — expose `autonomyEnabled: boolean` on
  `SwarmContext`, derived from `session?.autonomy_enabled ?? false`.
- **`frontend/components/HeadBar.tsx`** — when `autonomyEnabled`, render
  a `StatusPill state="connected"` with copy `autonomy baseline` in the
  right-side group, between the mode pill and the fleet pill. Compact;
  one row; no banner. (My recommended placement; see open question 2.)
- **`frontend/components/CommandTimeline.tsx`** — for autonomy rows,
  render an `AUTO` eyebrow chip in Orbital Blue in the leading slot
  before the action label.
- **`frontend/components/EventFeed.tsx`** — for `OPERATOR`-kind events
  with `source === "autonomy"`, replace the kind label "operator" with
  "auto" (Orbital Blue, eyebrow tier). Body copy from the backend
  already reads "autonomy verify dispatched" so the row is honest
  end-to-end.
- **`frontend/components/AnomalySummary.tsx`** — when the most recent
  non-terminal command on `anomaly.id` has `source === "autonomy"`,
  show a small `AUTO · {action}` chip in Orbital Blue next to the
  band pill. Derive the command client-side via
  `useSwarm().commands` (no new selector required).
- **`frontend/app/(console)/verify/[id]/page.tsx`** — same AUTO chip
  semantics as AnomalySummary, placed in the verification panel
  header.
- **`frontend/components/MobileAnomalyScreen.tsx`** — mirror the AUTO
  chip on the mobile alert surface (one line, eyebrow tier).

### Tests

**Backend Python (~12 new):**

- `swarm_os/tests/test_phase7c_session_autonomy.py` (3) —
  `Session.autonomy_enabled` flips with `SWARM_AUTONOMY_BASELINE=1`,
  flips when a scenario YAML sets `autonomy_baseline: true`, defaults
  to `False`.
- `swarm_os/tests/test_phase7c_event_source.py` (4) — autonomy command
  emits an `Event` with `source="autonomy"` and the
  "autonomy verify dispatched" body; operator command emits
  `source="operator"` with the legacy body; voice grep on the new copy
  returns zero hits for `FORBIDDEN_WORDS`; an `EmergencyStop`
  command issued by a commander stays `source="operator"` (not
  autonomy).
- `backend/tests/test_phase7c_event_source_persistence.py` (3) —
  `events.source` round-trips through `write_events` / `list_events`;
  upsert by composite PK preserves `source`; backfill of legacy rows
  reads as `"operator"`.
- `backend/tests/test_phase7c_alembic.py` (1) — Alembic
  `upgrade head → downgrade -1 → upgrade head` clean on aiosqlite.
- `backend/tests/test_phase7c_session_payload.py` (1) — `/session`
  endpoint returns `autonomy_enabled` in the JSON payload.

**Frontend Vitest (~8 new):**

- `frontend/components/__tests__/CommandTimeline.test.tsx` (2) —
  AUTO chip renders for `source="autonomy"` (one operator row, one
  autonomy row → only the autonomy row gets the chip).
- `frontend/components/__tests__/EventFeed.test.tsx` (2) —
  `OPERATOR`-kind event with `source="autonomy"` renders "auto" kind
  label; operator-source row renders "operator".
- `frontend/components/__tests__/HeadBar.test.tsx` (2) —
  `autonomy baseline` chip renders when `session.autonomy_enabled` is
  true; absent when false.
- `frontend/components/__tests__/AnomalySummary.test.tsx` (2) —
  AUTO chip renders when the latest in-flight command on the focus
  anomaly is autonomy; absent otherwise.

**Cross-cutting (~2 new):**

- `tests/test_phase7c_voice.py` (1) — voice grep over
  `frontend/components/*.tsx` + the new Event body strings returns
  zero hits.
- `tests/test_phase7c_brand.py` (1) — brand grep over the same files
  finds no red-state markers; the AUTO chip uses Orbital Blue / eyebrow
  tier only (`text-orbital-blue`, `eyebrow-mono`, `StatusPill
  state="connected"`).

Expected full suite after 7.C: ~706 passed / 16 skipped / 3 deselected
(vs 684 baseline, +22 net new). Backend coverage gate (80%) and
frontend Vitest gate (70%) both retained.

## Acceptance gates (end-of-7.C)

Per CLAUDE.md "readiness check" rules, re-run from a clean state:

1. `rm -rf .venv && make setup` — fresh install; `uv.lock` clean.
2. `make lint` — ruff + mypy + tsc green; mypy file count up by 1
   (`autonomy.py` already counted; new test files only).
3. `make test` — ~706 passed; backend coverage ≥ 80%; vitest ≥ 70%.
4. `make audit` — pip-audit clean, pnpm audit at the existing gate,
   Bandit 0 medium/high, pymavlink integrity PASS.
5. `alembic upgrade head` on the pinned Timescale image (CI gate; same
   caveat as Phase 4 — local Docker pull may be rate-limited).
6. **Manual smoke**: with `SWARM_AUTONOMY_BASELINE=1 make demo`, boot
   the wildfire scenario in a browser and confirm:
   - HeadBar shows `autonomy baseline` chip.
   - When the 0.62 SMOKE detection fires, the corresponding row in
     CommandTimeline carries the AUTO chip.
   - When the 0.88 FIRE follow-up fires, the EventFeed shows an
     `auto` kind row with body "autonomy escalate dispatched · R2".
   - AnomalySummary's focus anomaly shows `AUTO · verify` while R1's
     auto-VERIFY is in flight.
7. Voice + brand audit greps return zero hits on every new file.

## Anti-overreach checklist

- [ ] No new external dependency added to `pyproject.toml` or `package.json`.
- [ ] No change to `AUTO_VERIFY_FLOOR` / `AUTO_ESCALATE_FLOOR` /
      `AUTO_DISMISS_CEIL` or the rule predicates in `autonomy.py`.
- [ ] No new `swarm_os/intelligence/` or per-scenario threshold YAMLs.
- [ ] No CV runtime, no model weight downloads, no inference path.
- [ ] No `make demo-wildfire-sim` / `demo-intrusion-sim` /
      `demo-search-sim` targets (Phase 7.E).
- [ ] No inversion of the Console default — `ActionRail` still works
      identically, the `verify / hold-patrol / dismiss / return`
      buttons remain primary (Phase 8.A inverts).
- [ ] No `red` accent introduced anywhere; the `AUTO` chip stays
      Orbital Blue.
- [ ] No "Manual override" / "Intruder" / "Pilot" wording on the new
      copy paths.

## Open questions for the user

**Q1 — Persist the rule label (R1/R2/R3) on the audit row?**

The `AutonomyDecision` dataclass in `swarm_os/autonomy.py:67-79` carries
the rule label, but `OperatorCommand` does not yet. Three options:

- (a) **Stuff the rule into the Event body only** (current plan). Body
  reads "autonomy verify dispatched · R1". No new column. Forensic
  inspection via the EventFeed. **Recommended** — smallest scope, matches
  the "no per-rule UI in 7.C" decision.
- (b) Add `OperatorCommand.rule: str | None = None`. Touches the audit
  row, the persistence migration, and the WS payload. Slightly more
  expensive but the forensic data lives where you'd expect it.
- (c) Defer the rule label to Phase 8.B entirely (so the body just says
  "autonomy verify dispatched"). Cleanest now; but a future Phase 8 doc
  reader can't trace which 7.C rule fired without checking the kernel
  state at that timestamp.

If you don't pick, I'll go with **(a)**.

**Q2 — `AUTONOMY BASELINE` chip placement in HeadBar?**

- (a) Inline alongside the mode pill in the right-side group
  (compact; one row; my recommended placement).
- (b) As a second row above the existing 44 px HeadBar (more prominent
  but adds height to a deliberately tight chrome).

If you don't pick, I'll go with **(a)**.

## Out of scope (catalogued, not done in 7.C)

- Phase 7.D — CV baseline (FLAME + D-Fire + VisDrone pretrained).
- Phase 7.E — `make demo-{wildfire,intrusion,search}-sim` one-liners.
- Phase 8.A — Console default-inversion to observatory mode.
- Phase 8.B — per-scenario thresholds, WAIT decision, full
  VERIFY/DISMISS/ESCALATE/WAIT matrix.
- Phase 8.B-bis — shadow-mode comparison vs human baseline.
- Phase 8.C — override soft, policy nudge, kill switch.
- Phase 8.D — `OVERRIDE` eyebrow in Console.
- Runtime admin toggle for `state.autonomy_enabled` (no admin endpoint
  in 7.C; the flag still lives on the env / scenario YAML as 7.B
  defined it).
