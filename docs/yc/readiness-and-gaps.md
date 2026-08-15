# SWARM — YC readiness & gap plan

> Updated 2026-08-15. Companion to [`application-draft.md`](application-draft.md).
>
> The canonical company thesis is [`../../swarm-thesis.md`](../../swarm-thesis.md). This document translates it into YC-specific gaps and actions.

## The honest read

SWARM already has unusually deep engineering for its stage:

- end-to-end autonomous coordination in simulation;
- a real mission allocator;
- multi-agent state and orchestration;
- a production-shaped backend and operator Console;
- real CV components;
- shadow-mode safety logic;
- strong security and audit discipline;
- a MAVLink/PX4 path that is **PX4 SITL-validated**.

That is the strongest founder signal.

The company-side evidence is much weaker.

SWARM still does **not** have:

- a validated first market;
- meaningful customer evidence;
- a pilot;
- revenue;
- physical-aircraft proof;
- a short demo that makes the coordination primitive obvious to a reviewer.

The next work should close those gaps rather than add speculative platform breadth.

---

## Ranked gaps

| # | Gap | Why it matters | Severity |
|---|---|---|---|
| 1 | **No validated wedge / insufficient user evidence** | YC will ask how we know anyone urgently needs this. The previous wildfire/vineyard assumption was not sufficiently evidence-backed. | 🔴 Critical |
| 2 | **No YC-grade multi-agent demo** | The strongest technical asset is difficult to understand from repo depth alone. Reviewers need to see autonomous allocation and re-tasking in under two minutes. | 🔴 Critical |
| 3 | **No physical-aircraft proof** | SITL is real engineering evidence but not field evidence. The distinction must be clear. | 🟠 High |
| 4 | **No pilot / revenue** | Not mandatory at this stage, but one credible pilot signal would materially improve the company case. | 🟠 High |
| 5 | **Founder commitment / school framing** | The application must make clear whether SWARM is a serious company and how university plans interact with it. | 🟠 High |
| 6 | **Cofounder unresolved** | Hard-tech execution benefits from complementary flight/hardware/field depth, but a weak cofounder is worse than a strong solo story. | 🟡 Medium |
| 7 | **Regulatory deployment path** | A reviewer will ask how autonomous drone operations can move from bounded supervised pilots toward broader deployment. | 🟡 Medium |
| 8 | **Bottoms-up market case depends on the wedge** | TAM should follow the first validated workflow rather than be reverse-engineered around a favorite vertical. | 🟡 Medium |

---

## Key strategic correction

The old YC plan assumed:

> private high-value land → wildfire-risk patrol → vineyards / estates.

That is no longer the canonical strategy.

Wildfire remains a possible application and existing technical scenario, but the first market is now an explicit discovery problem.

The company-level thesis is broader:

> SWARM coordinates distributed autonomous units so software can create fast physical presence and response in the real world.

The YC application should therefore avoid pretending the market has already been solved.

The better story is:

> We built the coordination core. We can prove it in multi-vehicle PX4 SITL today. We are now identifying the highest-frequency physical-verification workflow where this coordination produces obvious economic value.

---

## Gap #1 — discover the wedge

### Goal

Find a workflow that is:

- frequent;
- painful or expensive;
- geographically bounded enough for early operations;
- owned by a clear buyer;
- improved by mobile autonomous observation/verification;
- better with coordinated units than with one manually piloted drone;
- repeatable across many sites.

### Who to interview

Do not over-concentrate on one vertical initially.

Target operators and buyers across:

- industrial facilities;
- logistics yards;
- mines and quarries;
- energy infrastructure;
- ports and large compounds;
- infrastructure inspection companies;
- large private/semi-private sites;
- drone-service operators who already perform manual inspection or verification.

### Opening question

> **What situations on your site currently require a person to physically go and check what is happening?**

Then quantify:

- frequency;
- current response time;
- number/type of people involved;
- current tool stack;
- cost of verification;
- cost of delay;
- whether a drone is already used;
- whether simultaneous events happen;
- whether battery/coverage/dispatch coordination matters;
- who owns the budget;
- what proof would justify a pilot.

### Evidence threshold

Do not name a first wedge because one person likes the idea.

A stronger threshold is repeated evidence from several independent operators that:

1. the same workflow recurs;
2. the current process is meaningfully slow/costly/risky;
3. they can describe a budget owner;
4. autonomous mobile verification would improve the workflow;
5. at least one would seriously evaluate a supervised pilot.

---

## Gap #2 — build the YC-grade demo

### The demo should not be wildfire-specific

Use a neutral environment such as a synthetic industrial site.

Example event:

`VERIFY anomaly at sector C7`

### Target sequence

1. Three or more PX4 SITL vehicles exist with different position, battery and availability states.
2. An event enters SWARM.
3. SWARM ranks the fleet.
4. The best unit is selected automatically.
5. A MAVLink/PX4 mission is dispatched.
6. While the mission is active, a second higher-priority event or asset-state change occurs.
7. SWARM re-tasks, replaces, adds, or returns a unit.
8. The Console exposes the decision rationale.
9. The mission concludes and the fleet state recovers.

### What the reviewer must understand

> **The autopilot flies the aircraft. SWARM decides what the fleet should do.**

### Honesty rule

Label the environment clearly as PX4 SITL/simulation.

Do not use stock or simulated footage in a way that implies real hardware flight.

The fact that it is SITL is not a weakness if the coordination path is real and the claim is precise.

---

## Gap #3 — physical proof

Do **not** buy drones merely to make the application look more serious.

The sequence should be:

1. prove the multi-agent control path in SITL;
2. find a real customer problem;
3. then get access to compatible hardware through the lowest-friction credible route.

Potential routes:

- borrowed PX4/ArduPilot aircraft;
- university lab;
- maker/robotics group;
- drone-service operator;
- hardware partner;
- purchased hardware only when justified.

The next physical milestone is modest:

> the same SWARM mission path that controls SITL successfully controls at least one real aircraft under supervised conditions.

No need to pretend this must be a fully autonomous multi-drone field deployment immediately.

---

## Gap #4 — pilot evidence

After the wedge becomes clearer, seek one concrete pilot conversation.

Useful evidence:

- a written note that a buyer would test the system if specific conditions are met;
- access to a site for a supervised demonstration;
- access to operational data or workflows;
- a paid or unpaid pilot with explicit success metrics.

Avoid fake LOIs or vague “sounds cool” endorsements.

---

## Gap #5 — founder commitment

The application should answer the school question directly.

Bad framing:

> I am trying this while studying and will see what happens.

Better framing, if true:

> I built SWARM before university, I am continuing to push it aggressively, and if the company demonstrates the signal required to justify going all-in, I will make the company decision accordingly.

The answer must match the founder's actual willingness. Do not manufacture commitment language that is not true.

---

## Gap #6 — cofounder

Do not add a cofounder only because YC statistically prefers teams.

A useful cofounder should materially increase the company's ability to execute in one or more of:

- robotics / controls;
- embedded systems;
- flight operations;
- hardware integration;
- drone regulation;
- industrial operations / customer access.

Until that person exists, the solo-founder technical output is itself a strong signal and should be presented cleanly.

---

## Gap #7 — regulatory answer

Keep the answer narrow and credible:

- early tests are supervised and bounded;
- deployment design follows the applicable EASA/FAA operating regime;
- broader BVLOS/autonomy is a scaling problem, not something to hand-wave away;
- the company can start in environments and operating modes where supervised testing is feasible;
- regulation affects deployment speed but does not invalidate the coordination-layer thesis.

Do not make legal claims beyond what has actually been verified for the target jurisdiction and operation.

---

## Gap #8 — market sizing

Do not size “all drones” or “all physical infrastructure.”

Once a wedge is selected, build a bottoms-up model:

`number of target sites × annual contract value × realistic initial penetration`

Then explain why the same coordination primitive expands into adjacent workflows and markets.

The long-term market can be enormous, but the first YC answer should be grounded in a buyer and a workflow.

---

## Immediate execution order

### A. Demo

Build and record the neutral multi-agent PX4 SITL coordination scenario.

### B. Discovery

Complete 15–25 serious cross-vertical conversations and log the workflows, not just reactions to SWARM.

### C. Pattern recognition

Rank candidate wedges using:

- frequency;
- urgency;
- budget clarity;
- deployment feasibility;
- multi-agent advantage;
- sales-cycle length;
- repeatability;
- willingness to pilot.

### D. Pilot hypothesis

Choose the first wedge only after enough evidence exists, and write a one-page pilot spec with measurable success criteria.

### E. Physical bridge

Arrange access to compatible hardware after the first customer signal, not before.

### F. YC application

Update the final application from real evidence. No stale wildfire/vineyard positioning, no simulated claims presented as physical proof, no invented customer traction.

---

## Current YC-readiness scorecard

| Dimension | Current state |
|---|---|
| Founder technical signal | **strong** |
| Product/engineering depth | **strong** |
| Multi-agent coordination proof | **real but not yet packaged clearly enough** |
| PX4 integration | **SITL-validated** |
| Physical hardware proof | **missing** |
| Customer evidence | **weak / missing** |
| Wedge clarity | **intentionally open pending discovery** |
| Pilot/revenue | **missing** |
| Vision | **strong** |

The goal is not to maximize every row before applying.

The goal is to turn the two weakest high-leverage rows — **visible proof** and **customer evidence** — into unmistakable signals.
