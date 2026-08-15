# SWARM — competitive landscape & market research

> **Status: research archive / non-canonical, updated 2026-08-15.**
>
> The original version of this file was researched around a wildfire/private-land wedge. That wedge is no longer canonical.
>
> Keep the historical competitor notes as useful context, but do **not** use this file as the current market thesis or copy old market numbers into an application without re-verifying them.
>
> Current strategy: [`../../swarm-thesis.md`](../../swarm-thesis.md)  
> Current YC draft: [`application-draft.md`](application-draft.md)  
> Current discovery plan: [`customer-discovery-kit.md`](customer-discovery-kit.md)

## What changed

The previous thesis was:

> private high-value land → wildfire-risk patrol → mobile/no-fixed-infrastructure wedge.

That was too specific relative to the amount of buyer evidence available.

The current company thesis is:

> SWARM is the coordination layer for autonomous drone fleets / autonomous physical response. The first commercial workflow must be discovered from repeated customer evidence.

Therefore the competitive set should now be researched **after** a recurring workflow starts to emerge.

---

## Platform-level competitor categories to keep watching

These categories matter regardless of the first wedge.

### 1. Drone-in-a-box / autonomous inspection platforms

Examples historically researched include Percepto and Skydio.

Relevant questions:

- do they coordinate multiple vehicles or mostly operate one dock/aircraft at a time?;
- are they tied to proprietary hardware?;
- how do they schedule tasks across sites?;
- how do they handle asset availability, battery and mission conflicts?;
- how much of the operator workflow do they own?;
- what APIs exist for external task generation?;
- what parts of the coordination problem are already solved well enough that SWARM should not rebuild them?

### 2. Autopilot / ground-control ecosystems

Examples: PX4/ArduPilot ecosystems and vendor ground-control software.

Relevant question:

> Where does single-aircraft mission execution end and fleet-level autonomous allocation begin?

SWARM must be clearly valuable above the autopilot rather than duplicating it.

### 3. Fleet-management / robotics orchestration software

Research products that schedule, monitor or coordinate heterogeneous robots/drones.

The important comparison is not UI style. It is:

- task allocation;
- multi-agent behavior;
- cross-vendor support;
- dynamic re-tasking;
- failure handling;
- evidence/audit;
- operational integrations;
- deployment maturity.

### 4. Manual drone-service operators

In many real workflows, the competitor may not be software at all.

It may be:

- a person driving to the site;
- an employee piloting one drone;
- an external inspection contractor;
- a security/maintenance round;
- a fixed camera plus a human callout.

For a first wedge, these current workflows may matter more than a venture-backed “competitor.”

### 5. Fixed sensor/camera systems

In some workflows the alternative will be fixed sensing rather than mobile robots.

The relevant question is not “fixed bad, mobile good.” It is:

> In which workflows does a mobile autonomous viewpoint create enough incremental value to justify the complexity of aircraft operations?

That must be demonstrated market by market.

---

## Historical wildfire research

The earlier file researched companies such as:

- Pano AI;
- Dryad Networks;
- Percepto;
- Skydio;
- manual drone operations / guard patrols.

It also collected wildfire and vineyard market statistics for Mediterranean Europe and Piedmont.

Those notes may still be useful if wildfire re-emerges from customer discovery, but they are **not** current proof that wildfire should be the first wedge.

Re-research all company status, funding, pricing and market statistics before using them externally. The original research date was 2026-06-23 and many of those facts are time-sensitive.

---

## New competitive-research process

Once customer discovery produces a repeated workflow, create a wedge-specific competitive memo using this order:

### A. Define the job

Example format:

> “When [event] happens at [site type], [role] must verify [thing] within [time], and currently does it by [workflow].”

### B. Identify the real alternatives

Include:

- no action / delay;
- person physically checking;
- fixed camera/sensor;
- manually operated drone;
- drone contractor;
- autonomous drone system;
- incumbent robotics software;
- internal custom workflow.

### C. Compare on buyer metrics

- response time;
- labor;
- coverage;
- reliability;
- deployment cost;
- regulatory burden;
- integration effort;
- evidence quality;
- ability to handle simultaneous tasks;
- total annual cost.

### D. Test whether multi-agent coordination matters

The wedge is weaker for SWARM if one manually operated drone already solves the job cheaply and reliably.

The wedge is stronger if the buyer experiences:

- multiple simultaneous tasks;
- large-area coverage;
- battery rotation;
- different payload requirements;
- multiple launch locations;
- asset availability conflicts;
- need for rapid autonomous dispatch;
- increasing fleet size that exceeds human attention.

### E. Quantify switching and moat potential

Ask what could become defensible through deployment:

- operational data;
- integrations;
- adapter maturity;
- reliability history;
- workflow-specific automation;
- audit/safety tooling;
- customer process dependence;
- coordination performance at scale.

---

## Market-sizing process

Do not start from a broad global-drone TAM.

Once a wedge is selected:

1. Count realistic target sites / buyers.
2. Estimate annual contract value from the existing workflow/budget.
3. Calculate an initial serviceable market.
4. Estimate realistic first-region penetration.
5. Identify adjacent workflows on the same customer base.
6. Identify adjacent verticals using the same coordination primitive.

Formula:

`target sites × annual contract value × realistic penetration`

Then explain the expansion ladder separately.

---

## Long-term competitive thesis

The long-term bet remains:

> autonomous hardware becomes increasingly capable and replaceable; the coordination layer that allocates tasks across distributed physical agents can become strategically valuable.

But that thesis is not enough by itself.

SWARM must prove that customers have coordination problems worth paying for, and that incumbents/autopilots do not already solve those problems adequately.

---

## Research hygiene

Before any YC/investor/customer-facing use:

- verify every company is still active;
- verify current product capabilities;
- verify pricing from a credible source or mark it unknown;
- verify funding/status if quoted;
- prefer primary sources;
- distinguish marketing claims from demonstrated capability;
- never use the old wildfire statistics merely because they are already in the repo.

The correct competitive memo is the one built around the workflow customers repeatedly tell us matters.
