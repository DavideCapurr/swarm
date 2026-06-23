# SWARM — YC application draft

> **Status:** working draft, 2026-06-23. Fill-in-ready answers to the real YC
> application questions, grounded in the actual repo state — not aspiration.
> Two live targets are kept open (decision deferred):
>
> - **Early Decision (now):** apply in the currently-open window, **on-time
>   deadline 2026-07-27 20:00 PT**, batch deferred to after the BIEF school
>   year. ([ycombinator.com/early-decision](https://www.ycombinator.com/early-decision))
> - **Winter 2027 batch:** literal Jan–Mar 2027 batch in SF (implies a BIEF
>   leave). Deadline expected ~Nov 2026; confirm on
>   [ycombinator.com/apply](https://www.ycombinator.com/apply).
>
> The application content below is identical for both; only the *batch target*
> line and the *location/leave* answer change. Gap analysis + dated plan:
> [`readiness-and-gaps.md`](readiness-and-gaps.md).

**Honesty rule (carried from the codebase):** every claim here is typed `sim`.
Nothing is SITL-, bench-, or field-validated yet. Do not let any external
material imply otherwise — overclaiming is the fastest YC rejection for a
hard-tech solo founder, and the typed-claim discipline is itself a selling
point.

---

## Company

**Company name:** SWARM

**Describe what your company does in 50 characters or less.**
> `Autonomous drone patrol for high-value land` (43 chars)

Alternatives to A/B:
- `Self-flying patrol that verifies land threats` (46)
- `An operating system for autonomous drone patrols` (48)

**Company URL / product link.**
> Demo + repo. *(Gap: stand up a one-page live link before submitting — see
> gap plan. Today there is no public URL; the demo is local one-command.)*

**Demo video.**
> See the demo shot-list below. A <2-min screen capture of the one-command
> wildfire Patrol Cell run: sector freshness → cue → verification mission →
> evidence packet → verify/escalate decision, narrated in confidence-bound
> voice. (`docs/yc/videos/` is currently empty — this is a required pre-submit
> artifact.)

**What is your company going to make? (long answer)**

> SWARM keeps private high-value land — vineyards, estates, forestry, remote
> industrial sites — recently observed, and turns an uncertain signal into
> verified evidence in minutes, using drones as **mobile** sensors instead of
> a fixed camera/tower/sensor network.
>
> The product is **SwarmOS**: the autonomous operating layer that decides,
> plans and coordinates the fleet. It tracks coverage freshness per sector,
> schedules patrols from risk and staleness (not a static route), turns a cue
> — a patrol observation, a weather/fire-risk feed, a guard call-in, a
> stale-sector rule — into a verification mission, dispatches the best
> available drone, and builds an evidence packet: coordinates, captures,
> source, confidence, timeline, nearby assets, recommended disposition. A
> human operator supervises through the **Console** and escalates, dismisses,
> requests another pass, or returns the unit. **SwarmOS decides; the Console
> only supervises** — and every number on screen comes from SwarmOS or an
> honest simulator, never invented in the UI.
>
> The first wedge is **wildfire-risk patrol** because the problem is urgent,
> seasonal and measurable — but the same loop already runs perimeter
> intrusion and missing-person/search scenarios in the demo. The buyer doesn't
> pay for "a drone that looks at a fire"; they pay for a recent view of the
> land, fast conversion of an uncertain signal into evidence, fewer wasted
> callouts, and an auditable record of patrols and decisions.
>
> The MVP deliberately needs **no SWARM-owned fixed infrastructure**: one
> thermal-capable drone, an operator, the Console, and reports. That removes
> the capex that makes incumbents slow to deploy.

**Where do you live now / where based after YC?**
> Now: Piedmont, Italy (Langhe — wildfire-prone wine country, the exact
> territory the product models). After YC: *(Early-Decision answer)* remain
> in Italy / EU for the BIEF year and join the batch in SF after the school
> year; *(Winter-batch answer)* relocate to SF for the batch. Be explicit and
> honest about the school timeline either way.

---

## Progress

**How far along are you?**
> Code-complete, simulation-validated product. SwarmOS runs end-to-end in an
> honest simulator: the autonomy engine returns an explicit
> `VERIFY | DISMISS | ESCALATE | WAIT` verdict on every anomaly, gated by a
> mandatory **shadow-mode** that compares every decision to a human baseline
> and fails the build above 5% divergence (currently 0% deterministic over the
> 3 scenarios). A one-command demo runs three Patrol Cell scenarios
> (wildfire / intrusion / search) with real event-to-detection and
> detection-to-verification metrics. The verification viewport runs **real**
> YOLOv8 person detection (0.95 / 0.86 confidence) on licensed imagery, kept
> opt-in and out of the production image for licensing hygiene.
>
> Engineering maturity is unusually high for stage: JWT auth with mandatory
> MFA for the commander role, Timescale-backed audit history, SHA-pinned
> dependencies + SBOM, CSP/security headers on every response, a committed
> threat model, and CI gates that fail on overclaiming language. **~850
> backend + ~150 frontend tests pass.** A MAVLink/PX4 adapter path exists and
> is CI-ready.

**How long / how much full-time?**
> *(Fill in honestly.)* Built largely solo over [N months]; full-time during
> the summer code window, around Italian secondary-school finals (maturità,
> June 2026).

**Are people using your product?** No.
**Active users / paying?** None yet. **Revenue?** None yet.
> Honest and intentional: the roadmap deliberately put market and field
> evidence *after* a working, investor-readable demo. The gap plan closes the
> "talked to users" hole before submission.

**Incubators/accelerators?** *(Fill in — likely none. Bocconi B4i / HAX are
> options under evaluation, not commitments.)*

---

## Idea

**Why this idea? Domain expertise? How do you know people need it?**
> I grew up in the Langhe, where dry-season wildfire risk over vineyards and
> woodland is a real, recurring threat, and where high-value private land is
> mostly *unwatched* between rare guard rounds. Fixed camera/tower networks
> (public wildfire camera grids, perimeter CCTV) don't cover private
> mid-size estates — the capex and install don't pencil out. So the land goes
> unobserved until something is already burning or already inside the fence.
>
> I'm a software founder, not a hardware vendor: I built the coordination OS
> first because **autonomy and coordination — not the airframe — is the hard,
> defensible part**. *(Demand evidence: this is the current weakest answer.
> The gap plan adds 10–15 real conversations with estate/vineyard managers,
> land-risk and drone-operator contacts in Piedmont before submission, so this
> answer cites real quotes, not a founder hunch.)*

**Competitors? What do you understand that they don't?**
> Every credible incumbent requires **fixed infrastructure** (researched
> landscape + sources: [`competitive-and-market.md`](competitive-and-market.md)):
> - **Pano AI** — AI cameras on fixed towers (~30M acres; $44M Series B Jun
>   2025). Tower capex only pencils for utilities/public land at landscape
>   scale, not a single private estate; press flags cloud false-positives and
>   heavy human reliance.
> - **Dryad Networks** — fixed solar mesh **gas sensors** on trees; dense
>   per-hectare install, detection only, no verification/response.
> - **Percepto / Skydio** — drone-in-a-box tied to a **fixed dock**, **$40k–
>   $250k+ capex per site**, aimed at heavy industry/defense; they sell the box.
> - **Manual drone ops / guard patrols** — not autonomous, not coordinated, no
>   auditable record, doesn't scale.
>
> What I understand: fixed infrastructure structurally locks all of them out of
> **private mid-size high-value territory**, which is left unserved. The wedge
> is **mobile, no-fixed-infrastructure, capex-free patrol**, and the defensible
> product is the **coordination OS**, not the drone. Start with one drone +
> operator + Console, prove value on freshness + verification + evidence, and
> the same loop generalizes across event classes and, later, to multi-cell
> coordination. They sell fixed hardware; I sell trustworthy decisions.

**How do you make money? How much?**
> Per-territory seasonal patrol subscription (mobile cell), priced against the
> cost of a wasted callout and an unverified threat; later a docked-cell
> premium and SwarmOS coordination-OS licensing. Demand tailwind is real and
> citable: the Mediterranean basin is **86% of total EU burned area**, and
> extreme-fire-weather exposure is projected to rise sharply through 2049 — a
> clean "why now." Beachhead alone (Piedmont ~45,000 ha under vine, thousands
> of mostly small family estates) is sizable before widening to the wildfire-
> exposed Mediterranean EU. Bottoms-up frame + sources:
> [`competitive-and-market.md`](competitive-and-market.md). *(Drop the
> seasonal price anchor from the discovery interviews before submitting.)*

**Category:** Hard tech / robotics / aerospace & defense-adjacent (civil
territorial security).

---

## Founders / team

> Answer chosen: **founder + cofounder in progress.** Frame honestly.
>
> - **[Founder]** — technical founder; designed and built SwarmOS end-to-end
>   (kernel, autonomy engine, sim, security, Console). The story is the
>   strongest single asset: a solo pre-university founder shipped a
>   production-discipline autonomous-coordination system. Lean into it.
> - **[Cofounder / candidate]** — *(fill in real name + complementary
>   strengths: ideally domain/field-ops, hardware/flight, or
>   commercial/buyer-access — the lanes I'm weakest in.)* If still recruiting
>   at submission, say so plainly and describe the exact gap being filled; YC
>   prefers honesty to a fabricated team.

**Founder video script (<1 min, each founder records their own):**
> "I'm [name], from the Langhe in Piedmont — wine country that's also some of
> Italy's most wildfire-exposed private land. Between rare guard rounds, that
> land is unwatched, and fixed camera networks are too expensive to install on
> a private estate. I spent the last [N] months building SwarmOS: the
> autonomous layer that flies a drone to patrol the land, verifies a
> suspicious signal in minutes, and hands a human operator an evidence packet
> and a verify-or-escalate decision — no fixed cameras, no towers. It already
> runs end-to-end in simulation across wildfire, intrusion and search, with
> real computer-vision detection and a safety gate that checks every
> autonomous decision against a human baseline. I'm building this because the
> land I grew up on deserves to be watched, and because the hard part —
> coordinating autonomy you can trust — is software, which is what I'm best
> at. [Cofounder line.] Next we put it in front of buyers and onto real
> hardware."
> *(Record in one take, plain background, look at camera, no slides. Energy +
> clarity beat polish.)*

---

## Curious

**What convinced you to apply to YC?** *(Fill in — genuine, specific, short.)*
**How did you hear about YC?** *(Fill in.)*

---

## Demo video — shot list (target <2 min)

Drive the real one-command demo (`make demo` / wildfire scenario) and screen-
capture the Console. Use the existing stills in
[`docs/yc/screenshots/`](screenshots/) as fallback frames. Narrate in the
PDF §5.2 confidence-bound voice — never the forbidden words.

1. **0:00–0:12 — Hook.** "Private high-value land is unwatched between guard
   rounds. SWARM keeps it observed and verifies threats with autonomous
   drones — no fixed cameras." (`wildfire-01-standby.png`)
2. **0:12–0:30 — Coverage freshness.** Show sectors + last-seen/staleness; a
   priority sector goes stale and triggers a patrol.
3. **0:30–0:50 — Cue → mission.** A wildfire-risk cue appears; SwarmOS turns
   it into a verification mission and dispatches a unit.
   (`wildfire-02-smoke.png`)
4. **0:50–1:15 — Verification + CV.** Viewport (stamped `SIMULATED FEED`);
   SwarmOS reaches R1/VERIFY. (`wildfire-03-r1-verify.png`) Note: CV person-
   detection is real on intrusion/search; wildfire smoke is honestly scripted
   (no fake fire CV).
5. **1:15–1:40 — Evidence + decision.** Evidence packet; SwarmOS escalates a
   verified hotspot; operator supervises. (`wildfire-04-fire.png`,
   `wildfire-05-r2-escalate.png`)
6. **1:40–2:00 — Truth + ask.** One line: "Everything you saw is
   simulation-validated today. Next: buyers and real flight." State the YC
   ask. Show the typed claim table.

**Hard rule:** stamp simulation honestly; never imply field/hardware proof.

---

## Truth table (paste into the application / demo)

| Capability | sim | SITL | bench | field |
|---|:--:|:--:|:--:|:--:|
| Autonomy engine (verify/dismiss/escalate/wait) | ✅ | — | — | — |
| Shadow-mode safety gate (<5% vs human baseline) | ✅ | — | — | — |
| Coverage freshness + patrol scheduling | ✅ | — | — | — |
| CV person detection (real YOLOv8) | ✅ | — | — | — |
| Wildfire smoke/fire CV | scripted | — | — | — |
| MAVLink/PX4 adapter | CI-ready | attempted | — | — |
| Flight / hardware | — | — | — | — |

Nothing ships to an investor as more proven than this table says.
