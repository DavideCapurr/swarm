# M1 A11y Sweep Report

Manual keyboard accessibility sweep run as part of M1 (Phase 7 closure
gate). Methodology + findings are recorded below for future reference;
deeper a11y work (focus management refactor, full ARIA tree) is deferred
to M2 (Phase 8 Console inversion).

## Methodology

- Surface: Console at `http://localhost:3000` driven by Playwright
  headless Chromium (1440×900) and Claude Code's Claude_Preview MCP
  (DOM inspection + key dispatch).
- Auth: signed in as `op-operator01` (operator role; `op-commander01`
  TOTP cycle was not exercised here — EmergencyStop modal verified
  via source-code read instead).
- Coverage: 3 targeted sweeps below.
- Data point: 14 focusable elements on the main route after Console
  hydration (`button, a, input, select, textarea, [tabindex]≥0`).

## Sweeps

### 1. Tab traversal — QuietPanel unit rows

Each unit row is rendered as `<button type="button">` with
`onClick={() => onSelect(u.agent_id)}` ([QuietPanel.tsx:227-244](frontend/components/QuietPanel.tsx:227)).
HTML default `tabIndex=0`; none disabled; reachable in keyboard order.

Visible focus style: `focus:outline-none focus-visible:bg-graphite/40`
([QuietPanel.tsx:231](frontend/components/QuietPanel.tsx:231)). Outline
is suppressed by design (DS Spread 24 — no system focus ring); the
keyboard-only `:focus-visible` background tint is the indicator.

### 2. Enter activation — QuietPanel unit row

Focused `unit-row-sim-2`, dispatched `keydown{Enter}`. The button's
`click` listener fired (`clickFired === true`) — HTML buttons translate
Enter → click natively, no custom `onKeyDown` needed. Selection
propagates through `onSelectAgent` to `TerritoryControl`.

### 3. Escape — EmergencyStop modal

Verified via source read at [EmergencyStop.tsx:43-54](frontend/components/EmergencyStop.tsx:43):
the modal mounts a `window.addEventListener("keydown", onKey)` that
resets phase to `idle` on `Escape`. The listener attaches only while
`phase === "confirm"` and is cleaned up via the effect return — so it
neither leaks nor swallows Escape outside the modal.

End-to-end interactive trigger was skipped this pass — opening the
modal needs `op-commander01` with a valid TOTP code, and the dev
bootstrap script's TOTP secret is not exposed to the sweep harness
without operator action. Recommend re-running this leg in M2 once
the commander TOTP rotation flow is wired.

## Findings

### PASS

- Unit row buttons reachable by Tab; Enter triggers selection
  (verified live via dispatched `keydown` + click listener).
- `:focus-visible` background tint renders on keyboard nav (the
  `focus-visible:bg-graphite/40` class is present on every unit row).
- AUTO eyebrow chip surfaces on the live state: `recent-auto-chip`
  testid present in QuietPanel · Recent action, content
  `"auto · r1 · "` confirmed during the wildfire demo run.
- EmergencyStop button correctly disabled for non-commander roles
  (title `"commander role required"` shown to operator session).
- EmergencyStop Escape handler implementation matches the spec
  (source-level verification; see Sweep 3).

### FIX in M1 (trivial inline fixes)

_None._ The sweep surfaced no defect requiring a code change inside
the M1 scope. Every assertion the M1 plan called out passes on `main`
HEAD as of the screenshot run (commit will be on `phase-7g-m1-gate`).

### MAJOR — deferred to M2 (Console inversion phase)

- **EmergencyStop interactive test not exercised**: live Escape
  verification needs commander+MFA login; dev bootstrap does not
  expose the rotating TOTP secret to a headless sweep. Either expose
  a sweep-only TOTP fixture, or rely on the Vitest component test
  (`frontend/components/__tests__/EmergencyStop.test.tsx`) as the
  contract gate. The Vitest spec already covers the Escape path.
- **AUTO chip surfacing on mobile detail view**: `mobile-02-detail.png`
  shows STATE/SECTOR/VERIFIER but does not surface the AUTO chip even
  though the linked anomaly was autonomy-verified. Confirm whether
  the chip is intentionally desktop-only (recent action is a
  desktop-only KPI row), or whether the mobile detail screen should
  carry an `auto · r1` ribbon next to STATE.
- **Focus visibility under DS Spread 24**: outline is suppressed and
  the visual cue is a 4-opacity background tint on `:focus-visible`.
  This may be too subtle in bright-environment use; consider adding a
  1px Orbital Blue inset stroke to the active focus state when
  inverting the Console default (Phase 8.A).
- **Tab order audit beyond QuietPanel**: this pass exercised the right
  rail only. The map layer (`Map.tsx`) anomaly callouts, the
  CommandTimeline (`/verify`), and the system route were not walked.
  Add to the M2 checklist when Console-default-mode flips.

## Notes

- The interactive sweep itself, the autonomy live run, and the AUTO
  chip rendering are all observable in
  `docs/yc/screenshots/wildfire-{01..05}.png` and
  `docs/yc/screenshots/mobile-{01,02}.png`.
- Resolved (Phase 7.B confirm-by-observation): the wildfire anomaly now
  transitions `verifying → verified` when the dispatched drone dwells
  on-station over the hotspot, so autonomy R2 auto-ESCALATEs the 0.88
  FIRE live in the demo — `wildfire-05` shows the R2 AUTO chip, not R1.
  The confirmed confidence stays the sim's own perception score (no
  kernel-side fabrication), keeping the "SwarmOS decides, never invents"
  rule intact.
