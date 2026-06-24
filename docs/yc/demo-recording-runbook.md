# SWARM — YC demo video recording runbook

> Closes gap #2 (critical) in [`readiness-and-gaps.md`](readiness-and-gaps.md):
> the watchable proof. Founder-machine step (needs the full stack + a headed
> browser for real WebGL — same constraint as the screenshot harness).
>
> **Why this supersedes [`m1-vo-script.md`](m1-vo-script.md) for the YC cut.**
> That script is accurate but pitched at an *internal* audience — it says
> "Phase 7 complete," "Console inversion," "Phase 10 ML." A YC reviewer doesn't
> know or care about phase numbers; they need **problem → product → proof** in
> a buyer's language, in under two minutes. Same demo, same verified beat
> timing — different narration. Keep `m1-vo-script.md` as the internal
> reference; record *this* for YC.

## Setup (≈5 min)

1. Boot the stack so the demo is ready (one terminal): `docker compose up -d
   postgres redis` → backend → frontend, or your usual `make demo` path.
2. QuickTime Player → File → New Screen Recording → record the Console window
   (1080p; hide the dock/menubar clutter).
3. Have the narration below on a second screen / phone. Speak it **live** over
   the run, or record voice separately and overlay in the QuickTime trim.
4. **Press record first**, then in a second terminal run the boot command. The
   first ~10s of standby is your intro runway.

Boot command (wildfire arc — the canonical YC cut):
```
make demo-wildfire-sim
```

## Narration — wildfire arc (target 75–90s, buyer voice)

Verified beat timing (from the metrics artifact
`docs/bench/artifacts/phase-7e-wildfire_owner_land-*.json`, `by_rule.R2 == 1`;
re-confirm against your live run before the final cut).

| t (s) | On screen | Say (buyer voice — no phase numbers, no forbidden words) |
|---|---|---|
| 0–10 | Standby: 3 drones idle on owner land, no anomaly | "This is private high-value land — a vineyard estate with woodland that's a fire risk every dry season. Between rare guard rounds, nobody's watching it. SWARM keeps it observed with autonomous drones — and no fixed cameras or towers installed." |
| 10–22 | SMOKE callout amber 62%; AUTO chip `r1 · verifying` (Orbital Blue) | "A fire-risk signal appears at low confidence. No operator has to react — SwarmOS dispatches a drone and verifies it. The AUTO chip means the system decided, not a human." |
| 22–40 | FIRE 88% (a *second*, higher-confidence anomaly); auto-verify then `r2 · escalated` | "A stronger signature follows. SwarmOS verifies it, and once the hotspot holds, escalates it — handing the operator coordinates, captures, a timeline and a recommended action. The operator supervises; the system does the work." |
| 40–60 | Hold on final escalated state / evidence | "From an uncertain signal to verified evidence in under a minute — without a single fixed sensor, and with every decision auditable." |
| 60–75 | Truth table / honest close | "Everything you just saw is validated in simulation today, across wildfire, intrusion and search, with real computer-vision detection. Next: buyers, and real flight. We're honest about exactly what's proven — that table is on screen." |

> **Hard rules while recording:** the viewport must show `SIMULATED FEED`;
> never imply a live camera or field/hardware proof. Voice stays
> confidence-bound (no `intruder`, `manual`, `alarm`, etc. — CI greps these).

## The separate <1-min founder video

YC also wants a short founder video (each founder, one take, look at camera,
no slides). Script is in [`application-draft.md`](application-draft.md) →
"Founder video script." Record it separately from the demo; authenticity beats
production value.

## Output

- Demo: `docs/yc/videos/swarm-demo-wildfire.mov` (H.264, 1080p, ≤2 min).
- Founder video: `docs/yc/videos/founder.mov` (≤60s).
- Minimum 3 takes each; pick the cleanest audio. Trim tight — dead air kills a
  YC video faster than anything.

## Optional intrusion/search cut

If you want a second 30s clip showing the loop generalizes, boot
`make demo-intrusion-sim` (3-beat arc: standby → R1 verify → VERIFIED, where
the operator owns escalation). Use it only if it adds something the wildfire
cut didn't — don't pad.
