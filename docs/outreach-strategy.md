# SWARM outreach strategy

> Status: **current outreach / go-to-market strategy. Evidence-seeking.**
> Updated: 2026-08-29.
>
> Subordinate to [`../swarm-thesis.md`](../swarm-thesis.md) and [`../NORTH_STAR.md`](../NORTH_STAR.md).
> Operational discovery mechanics and the running send log live in
> [`customer-discovery.md`](customer-discovery.md); the full interview kit lives in
> [`yc/customer-discovery-kit.md`](yc/customer-discovery-kit.md); the current product
> hypotheses live in [`product/gtm-campaign-composable-capacity.md`](product/gtm-campaign-composable-capacity.md).
> If this file conflicts with the thesis, the thesis wins.

## The stance

**Discovery before pitch. Decision support before autonomy.**

The first commercial wedge is still an open customer-discovery question (see the thesis).
The purpose of outreach is not to sell SWARM. It is to find, from repeated operator
evidence, one frequent and costly physical-verification workflow with a clear budget
owner where coordinating several units beats one manually operated unit, and to open
the shortest credible path from that evidence to a supervised pilot on real hardware.

Two proofs matter more than anything else right now, and the whole strategy is bent
toward them:

1. **one physical-hardware proof** — the same SwarmOS control path that drives PX4 SITL
   drives at least one real aircraft under supervised conditions (closes the gap that
   damages credibility most: SITL is not field);
2. **one supervised pilot** — a real operator, real assets, a measurable success metric,
   and at least one *named* decision the mission/risk owner lets SwarmOS make inside
   constraints (launch composition, failed-executor replacement, or reinforcement).

The second proof, delegation of a real decision inside real constraints, is the actual
differentiator versus every drone-in-a-box vendor. It is the seed of the "system of
decision" the north star describes. Outreach exists to reach it.

## The funnel

```text
real workflow  ->  friction  ->  authority  ->  delegable decision  ->  pilot
```

A first-touch email only tries to open the first step: get the operator to describe a
real workflow in their own words. Authority, delegable decisions, and pilot conditions
are follow-up conversations after a genuine reply. They are never asks in a cold email.

## Three tracks (different goals — do not mix them)

The single biggest past mistake was treating one undifferentiated list as a pipeline.
Split outreach into three tracks with different objectives, cadences, and success
definitions.

### Track 1 — pilot pipeline (priority)

**Goal:** reach an operator who can give a supervised pilot on real hardware within
months, not years.

**Who:**

- **Drone-service operators who already fly missions manually.** This is the single best
  first call. One of them as a design partner closes three gaps at once: they own
  hardware (the route to physical proof), they have customers and budgets (market
  evidence), and they already feel the "which asset for which job" pain firsthand (the
  exact SWARM problem). Treat them as peers and potential partners, not prospects.
- **Industrial and energy site operators** with bounded geography and one budget owner:
  mines and quarries, solar and wind O&M, ports and terminals, large logistics yards,
  utility and infrastructure inspection contractors, large private or semi-private
  compounds.

**Why these convert:** bounded environments, concentrated operational authority,
existing spend on inspection or verification, a credible path to supervised early
operations, and a real reason coordination of several mobile units beats one operated
unit.

### Track 2 — learning / falsification

**Goal:** find where the thesis breaks before spending a year building for a problem
operators do not actually feel.

**Who:** domain experts and practitioners — robotics integrators, PX4/ArduPilot
practitioners, aviation and airspace experts, CRASAR-style researchers, ONR-style
research contacts, insurance and risk professionals.

**How:** do not pitch. Ask directly where the "missing coordination layer" thesis is
wrong or already solved. This is the highest value per contact for reducing thesis risk.
Raise the priority of these contacts rather than holding them for a later wave.

### Track 3 — credibility / long game

**Goal:** confirm the pattern across large operators, and build future reference logos.
Not a near-term pipeline.

**Who:** government agencies and public-safety / emergency operators (the type of contact
in the 2026-08-26 batch: land, wildland-fire, ocean, disaster-response, and state public
safety), plus very large industrial operators with slow procurement.

**Why demoted:** highest mission value, lowest pilot feasibility for a solo founder now.
Long procurement, security and authorization requirements, and no budget authority at the
level that answers a cold email. Keep them, expect slow or no replies, log non-response as
`unknown` (channel), and never treat silence here as evidence that the segment does not
care. Low cadence.

## Geography: where to run the experiments

Physical experimentation is the current bottleneck. Choose the regions where a solo
founder can most cheaply and quickly put the control path in front of a real aircraft
under a permissive or fast experimental regime. Regulatory speed is a real competitive
edge for closing the two priority proofs above.

### Priority regions

- **Middle East.** Reported to combine fast experimental and BVLOS pathways with heavy
  industrial and energy demand: Gulf oil and gas, ports, solar, and large planned
  developments. Candidate anchors to evaluate: UAE (Dubai and Abu Dhabi test and BVLOS
  frameworks, ports, giga-projects), Saudi Arabia (giga-project sites, mining under the
  current diversification programs), Qatar.
- **Africa.** Several markets are cited as drone-permissive or as running established
  experimental corridors, alongside very large mining and energy demand: Rwanda
  (established drone corridors), Kenya, Ghana, South Africa (large mining sector and
  BVLOS trials), Morocco (industrial and solar), Nigeria (energy). Mining and energy O&M
  are the strongest demand overlap.
- **Europe / Italy (proximity base).** Where the founder physically is, and where the
  warmest first calls live: Italian and European drone-service operators and mid-size
  industrial and energy sites. Slower on airspace than the Gulf, but the shortest path to
  a first face-to-face design-partner conversation.

### Rationale

For repeated real-hardware trials, a jurisdiction with faster or lighter experimental
drone rules lowers the time and cost to physical proof and to a first supervised pilot.
Africa and the Middle East are therefore treated as first-class experimentation and
early-pilot regions, not as an afterthought behind Europe and the US.

### What to verify before committing to any market

Do not treat "regulations are lighter" as a finished fact. For each candidate market,
confirm before investing outreach or travel:

- the actual current airspace / experimental / BVLOS rules **and** how they are enforced
  in practice (permissive enforcement is not the same as permissive rules);
- import and customs handling for the hardware you need on site;
- who must authorize a flight and how long that takes;
- data, IP, and counterparty and payment risk with the specific customer;
- dual-use and export-control sensitivity — SWARM is coordination software with
  defense-adjacent optics, so be deliberate about which customers and which framing, and
  keep to the thesis boundary (no autonomous-weapons use).

Regulatory friendliness is a reason to prioritize a market, not a reason to skip
diligence on it.

## The email

The form is already right and stays: short, human, one question, easy to answer
asynchronously, no pitch, no demo ask, no architecture explanation. What changes is the
**question**.

Stop asking the operator to describe SWARM's problem ("who reallocates assets when
priorities change"). Ask them to describe **their** problem. The strongest opening,
already in the thesis, is more concrete, harder to answer with a reflexive yes, and
surfaces frequency and pain:

> What situations on your site currently require a person to physically go and check what
> is happening?

Authority and delegable decisions come only after a reply, exactly as in the funnel.

For **drone-service operators**, the question is different and more peer-to-peer:

> When you are running several jobs or several aircraft in a day, what is the annoying
> part of deciding which aircraft does which mission?

### Two operational details that move reply rate

- **Language.** Write in the recipient's language. Italian to Italian contacts, clear
  English to Middle East and Africa contacts.
- **Sender.** Send from a SWARM domain address, not a personal mailbox. A real domain
  raises perceived seriousness at near-zero cost and improves deliverability.

### Templates

Industrial / energy operator (IT):

```text
Oggetto: come verificate i controlli sul sito

Buongiorno [Nome],
sto studiando come i grandi siti gestiscono i controlli fisici quando succede
qualcosa e qualcuno deve andare sul posto. Non le sto vendendo niente.
Una domanda sola: quali sono le situazioni in cui oggi qualcuno deve fisicamente
andare a controllare cosa sta succedendo?
Grazie,
Davide
```

Industrial / energy operator (EN, for Middle East and Africa):

```text
Subject: how you handle physical checks on site

Hi [Name],
I am studying how large sites handle physical checks when something happens and
someone has to go and look. I am not selling anything.
One question: what situations on your site currently require a person to
physically go and check what is happening?
Thanks,
Davide
```

Drone-service operator (EN):

```text
Subject: how you assign aircraft across jobs

Hi [Name],
Quick question from someone building coordination software, not selling hardware.
When you are running several jobs or several aircraft in a day, what is the
annoying part of deciding which aircraft does which mission?
Thanks,
Davide
```

### Follow-up rule

One follow-up after **7 working days**, no new pitch, no added pressure. If there is
still no reply, log the contact as `unknown` (channel) and stop. Silence, especially from
a large operator or an agency, is noise, not a "no".

## After a reply

Only when a reply shows genuine engagement, move through the funnel in follow-up
conversations, watching for three escalating signals before asking for the next one:

1. the coordination / allocation problem is real today and still manual or ad hoc, not
   already solved by an existing tool;
2. openness to delegating one specific decision to software, even partially;
3. willingness to test against their own assets, simulators, or data.

Do not ask for signal 2 or 3 in a first-touch email. Add one gentle question about the
**cost of the current process** (how often, how long, what it costs, what gets worse when
verification is late), because outreach can otherwise confirm that a workflow exists
without ever learning whether it hurts enough to buy software.

## Evidence discipline

Classify every meaningful reply, preserving the operator's exact words:

- **supports** — consistent with an existing hypothesis;
- **contradicts** — against an existing hypothesis;
- **new lead** — a workflow or vertical worth investigating;
- **unknown** — something the reply did not establish (including channel non-response).

One reply can change outreach wording immediately. Product or architecture changes
require repeated evidence or a direct contradiction of a core assumption. Do not convert
one operator opinion into a validated wedge, and do not treat a batch of 25 cold emails as
verification of a segment; it generates hypotheses, it does not validate them.

## What outreach must never claim

Preserve the thesis truth rules in every message and every external note:

- simulated is not SITL-validated;
- SITL-validated is not bench- or field-proven;
- a customer interview is not a pilot commitment;
- pilot interest is not revenue;
- a possible vertical is not a validated wedge.

Never describe SWARM with inflated language ("AI-powered", "next-generation",
"revolutionize", "swarms of drones", "replacing helicopters"). Lead with the operator's
workflow, not SWARM's architecture.
