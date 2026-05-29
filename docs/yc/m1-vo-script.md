# M1 VO Script — demo-01-sim-wildfire

Voice-over script per il primo video pitch YC. Durata target: 60 s (±5 s).
Tone: confident, founder voice, no jargon. Voce piana, niente forbidden
words (cfr. CLAUDE.md §Voice).

Pair to: `docs/yc/videos/demo-01-sim-wildfire.mov`
Scenario: `sim/scenarios/wildfire_owner_land.yaml`
Boot: `make demo-wildfire-sim`

## Script

**[0–10 s · standby]**

"This is SwarmOS. Three drones on owner land in standby. No operator
input."

**[10–22 s · SMOKE + R1 auto-VERIFY]**

"Smoke detected at 62% confidence. No human reacts — SwarmOS R1 rule
auto-verifies. The AUTO chip on the callout shows the decision is
machine-source, not operator-source."

**[22–40 s · FIRE detected → auto-VERIFY → R2 auto-ESCALATE]**

"About twelve seconds later, a second, higher-confidence fire signature is
detected — a separate anomaly at 88%. SwarmOS auto-verifies it, then
auto-escalates the verified hotspot once it has held. No operator clicked
anything. Console supervises. SwarmOS decides."

**[40–55 s · close]**

"Phase 7 complete. The autonomous loop runs without human input. Next
phase: Console inversion plus Phase 10 ML custom-trained on real fire
imagery."

**[55–60 s · brand]**

"SwarmOS. Drones that decide."

## Recording notes

- QuickTime Player → File → New Screen Recording → Record entire screen
- Run `make demo-wildfire-sim` AFTER pressing record
- Speak VO live OR record VO separately and overlay in QuickTime trim
- Minimum 3 takes; pick the cleanest audio
- Trim to 60 s ±5 s, export H.264 1080p max
- Output path: `docs/yc/videos/demo-01-sim-wildfire.mov`

## Beat timing reference

| t (s)  | What's on screen | VO segment |
|--------|------------------|------------|
| 0      | Standby — 3 IDLE drones, no anomaly | standby |
| 10     | SMOKE callout amber 62% | SMOKE intro |
| 12     | SMOKE AUTO chip `r1 · unit … · verifying` Orbital Blue | R1 line |
| —      | SMOKE reaches `verified` and holds — 62% is below the 0.80 R2 floor, so it never auto-escalates | — |
| 25     | FIRE callout 88% — a *second* anomaly, not a confidence bump on the smoke marker | FIRE intro |
| ~27    | FIRE AUTO chip `r1 · … · verifying` (auto-VERIFY) | FIRE line |
| 37–40  | FIRE reads `verified`, then AUTO chip `r2 · … · escalated` Orbital Blue | R2 line |
| 40-55  | Hold on final state | close |
| 55-60  | Brand sign-off | brand |

> The FIRE verify→escalate gap is the real `AUTO_ESCALATE_IDLE_S` floor (10 s)
> plus the executed VERIFY mission's flight time, so R2 lands at ≈t37–40.
> Confirm the exact beat against the live run + the metrics artifact
> (`docs/bench/artifacts/phase-7e-wildfire_owner_land-*.json`, `by_rule.R2 == 1`)
> before the final cut.
