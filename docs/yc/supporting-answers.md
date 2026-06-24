# SWARM — YC supporting answers (gaps #5 / #6 / #7)

> Drafts for the three application answers reviewers always probe on a
> hard-tech robotics company: *will it actually fly, is it legal, how big.*
> Grounded in the real repo (adapter layer, threat model). Companion to
> [`application-draft.md`](application-draft.md) and
> [`readiness-and-gaps.md`](readiness-and-gaps.md).
>
> **All market numbers below are illustrative placeholders** marked
> `[RESEARCH]` — replace with a figure you can defend. Do not submit invented
> statistics; an investor will check, and a wrong number costs more than an
> honest "we're sizing this."

## Gap #5 — "Why should we believe this ever flies?" (flight-path credibility)

> The hard part of SWARM is **coordination and autonomy you can trust**, which
> is software — and that's done end-to-end in simulation. The flight layer is
> deliberately the *least* novel part: SWARM talks to drones through a
> vendor-agnostic adapter interface (`adapters/base.py`), with a **MAVLink/PX4
> adapter already implemented and CI-ready** and conformance-tested stubs for
> DJI, Skydio, Autel and Parrot paths. SWARM does not build airframes — it
> coordinates commodity ones.
>
> The path from sim to real flight is short and standard: the same adapter
> interface drives (1) **PX4/SITL** software-in-the-loop — a logged,
> reproducible run is the immediate next milestone, (2) a **supervised bench**
> test against a real flight controller, then (3) a supervised field flight
> with an explicit safety/regulatory checklist. We move the claim ladder only
> as far as the evidence moves: nothing is described as field-proven until it
> is. The autonomy is also gated by a mandatory shadow-mode that checks every
> decision against a human baseline (currently 0% divergence in sim), so the
> decision logic that reaches a real aircraft is the same one that's already
> been validated.

## Gap #6 — "Can you even legally fly this?" (regulatory + privacy)

> **Operations.** The MVP is a **human-supervised** service, not an
> unattended BVLOS autonomous fleet — that keeps the first deployments inside
> the EASA **Open / Specific** category with a licensed operator in the loop,
> in Italy under ENAC. We don't claim a regulatory unlock we haven't earned;
> the operator supervises every mission through the Console and SwarmOS only
> proposes verify/escalate decisions. The harder BVLOS/autonomy envelope is a
> *later* phase tied to evidence and a written operating path for the specific
> geography — not assumed.
>
> **Privacy / GDPR.** Camera data is treated as PII from day one (it's in our
> committed threat model). Concrete posture already in the product: the CV
> pipeline operates on **non-identifiable** imagery (back-view / distance, no
> recognizable faces committed or stored), every operator decision is
> audit-logged, the system is built to minimize unnecessary surveillance, and
> data handling/retention is an explicit MVP concern, not an afterthought. We
> patrol *private* land for *its owner* — the consent and data-controller
> story is clean, unlike public-space surveillance.

## Gap #7 — "How much could you make?" (bottoms-up market)

> **Wedge first, then expansion.** Size the wedge buyer honestly before
> claiming a platform TAM.
>
> **Bottoms-up (illustrative — replace each `[RESEARCH]`):**
> - Serviceable wedge buyers near the first geography: `[RESEARCH]` number of
>   mid-large private estates / vineyards / forestry holdings with woodland
>   wildfire exposure in Piedmont (then NW Italy, then wildfire-exposed
>   Mediterranean EU).
> - Seasonal patrol price per territory: `[RESEARCH]` €/season, anchored to
>   what one wasted callout + one late-response event costs them (get this
>   number from the discovery interviews — question 3 & 4 in the kit).
> - Wedge ARR per buyer ≈ price × seasons; first-region SAM ≈ buyers × ARR.
>
> **Expansion levers** (don't claim these as today's market, name them as the
> ladder): additional event classes on the *same* patrol loop (perimeter
> intrusion, search, post-storm damage, infrastructure check) → adjacent
> high-value-territory verticals (utilities corridors, logistics yards, large
> rural sites) → SwarmOS **coordination-OS licensing** to operators running
> their own fleets. The destination is autonomous coordination infrastructure
> for time-critical territorial events; the wildfire patrol wedge is the
> capex-free front door.
>
> **Framing line for the app:** "We can defend a real bottoms-up wedge number
> from buyer conversations; the platform TAM (territorial security + wildfire
> resilience + infrastructure monitoring) is large but we're not pricing the
> company on it yet."

## Note

These three answers are strongest *after* the discovery interviews: #6 gains
a real operator's reg view, #7 gains a real price anchor, #5 gains a logged
SITL run. They're written now so the application is complete on day one and
only needs real numbers dropped in.
