# SWARM roadmap — evidence to scale

Updated 2026-08-15.

This is the forward execution roadmap from the current evidence state. The canonical company thesis is [`../../swarm-thesis.md`](../../swarm-thesis.md). If this roadmap conflicts with it, the thesis wins.

The Phase 0–6 technical foundation remains documented in [`swarmos-roadmap.md`](swarmos-roadmap.md). Older post-Phase-6 plans are historical context only.

## Current decisions

1. **The company is the coordination layer, not a wildfire product.**
   Wildfire, private-land patrol, inspection, security and other verticals are candidate applications until customer evidence proves a first wedge.

2. **The current technical demo proof is complete enough to freeze.**
   Dynamic multi-event PX4 SITL allocation, first-class multi-agent `ExecutionGroup` composition, live member replacement, and the final `/demo/intrusion` rehearsal are validated. Do not add features merely to broaden the demo.

3. **The next market proof is workflow-first customer discovery.**
   Ask operators where someone must physically go and check what is happening today. Find repeated, frequent, costly workflows before naming the wedge.

4. **The next technical evidence gap is physical hardware.**
   The first physical bridge can use borrowed, partnered or later purchased aircraft. Buying hardware just for optics is not a milestone.

5. **Claims remain typed.**
   Keep `sim`, `SITL`, `bench`, `supervised field`, `pilot`, and `commercial production` distinct.

6. **More code is not automatically more progress.**
   New engineering must improve physical proof, customer discovery, pilot readiness, or a blocker revealed by those activities. The demo runtime is feature-frozen.

7. **The long-term vision remains large.**
   SWARM can evolve from drone-fleet coordination toward a runtime for distributed autonomous physical agents, but that platform must be earned through real deployments.

---

## Current evidence state

| Area | Current evidence |
|---|---|
| Core mission / fleet model | working |
| Centralized fleet-state allocation | working |
| End-to-end simulation | working |
| Console / backend / audit | working |
| Autonomy + shadow logic | working |
| MAVLink/PX4 integration | **SITL-validated** |
| Dynamic multi-event allocation | **live two-PX4 SITL-validated** |
| Verified `MISSION_ITEM_REACHED` arrival semantics | **validated** |
| Bounded PX4 payload output | **SITL output-confirmed; speaker simulated** |
| First-class multi-agent `ExecutionGroup` | **live four-PX4 SITL-validated** |
| Live `ExecutionGroup` member replacement | **validated with active PX4 process SIGKILL** |
| Final `/demo/intrusion` rehearsal | **3 consecutive clean PASS takes, ~62 s each** |
| Physical-aircraft proof | missing |
| Validated first wedge | missing |
| Customer evidence | weak / insufficient |
| Pilot | none |
| Revenue | none |

Authoritative technical evidence:

- [`../bench/phase10-dynamic-multi-event-validation.md`](../bench/phase10-dynamic-multi-event-validation.md)
- [`../bench/payload-presence-sitl-validation.md`](../bench/payload-presence-sitl-validation.md)
- [`../bench/phase11-execution-group-validation.md`](../bench/phase11-execution-group-validation.md)
- [`../bench/phase12-execution-group-live-failover.md`](../bench/phase12-execution-group-live-failover.md)
- [`../bench/final-demo-rehearsal.md`](../bench/final-demo-rehearsal.md)

---

## Phase map

### Phase 7 — technical foundation proof

**State: done.**

Existing outputs include the coordination core, operator system, simulation scenarios, autonomy/shadow logic and a PX4/MAVLink path validated in SITL.

Do not reopen Phase 7 merely to add polish unless a later proof exposes a blocker.

### Phase 8 — multi-agent SITL proof + investor demo

**State: done / feature-frozen for the current demo.**

The original goal was to make the coordination primitive understandable in roughly one minute without buying aircraft. That gate is now satisfied by a set of separate but compatible proofs:

- dynamic allocation while another mission is active;
- exact `BUSY` exclusion and different second owner;
- verified `ON_STATION` through `MISSION_ITEM_REACHED`;
- bounded payload output with explicit simulation boundaries;
- one logical objective composed into a three-role `ExecutionGroup` across three of four PX4 SITL agents;
- central replacement after one active selected PX4 is SIGKILLed;
- three consecutive deterministic final-demo rehearsal passes.

The definitive demo surface is `/demo/intrusion`; the authoritative recording runbook is [`../bench/final-demo-rehearsal.md`](../bench/final-demo-rehearsal.md).

#### Gate result

A technically literate viewer should be able to answer:

> “What does SWARM do that the autopilot does not?”

with:

> “SwarmOS decides what the fleet should do, composes the required physical agents, and adapts ownership as conditions change. The autopilots execute locally.”

Do not expand Phase 8 with new runtime features, frontend redesign, dependency work, or unrelated platform scope merely for demo presentation.

---

### Phase 9 — cross-vertical workflow discovery

**State: next market priority.**

Goal: identify repeated physical-verification workflows, not reactions to a drone pitch.

#### Initial interview pool

- industrial sites;
- logistics yards;
- mines/quarries;
- energy infrastructure;
- ports / large compounds;
- infrastructure inspection companies;
- drone-service operators;
- large private / semi-private sites.

#### Core question

> What situations on your site currently require a person to physically go and check what is happening?

#### Minimum evidence to capture

- exact workflow;
- last real example;
- frequency;
- current response time;
- people involved;
- current tools;
- current cost / budget line;
- cost of delay;
- drone use today;
- simultaneous-event / coverage problem;
- budget owner;
- pilot success metric;
- willingness / conditions for a test.

#### Gate

Do not select a wedge until repeated independent interviews show the same or closely related workflow with:

- meaningful frequency;
- meaningful cost/urgency;
- a clear buyer;
- feasible early deployment;
- a real advantage from autonomous mobile coordination;
- at least one credible pilot conversation.

---

### Phase 10 — wedge selection + pilot hypothesis

**State: blocked on Phase 9 evidence.**

Goal: turn discovery into one narrow first commercial attack.

#### Output

A one-page wedge memo containing:

- target buyer;
- site type;
- exact workflow;
- current alternative;
- quantified pain;
- why a drone helps;
- why coordination helps beyond one manually operated drone;
- deployment assumptions;
- pilot scope;
- success metric;
- expected budget source;
- reasons this wedge could still fail.

#### Gate

The wedge becomes canonical only when the memo is supported by real customer evidence.

Until then, all verticals remain hypotheses.

---

### Phase 11 — physical control-path bridge

**State: next technical evidence priority.**

Goal: prove the same command path that works in PX4 SITL can control physical aircraft under supervised conditions.

Hardware can come from:

- borrowing;
- university / lab access;
- maker / robotics groups;
- drone operators;
- partners;
- purchasing, if justified.

#### Minimum proof

- one compatible aircraft;
- supervised operation;
- SWARM sends a mission through the same adapter path;
- telemetry returns correctly;
- safe abort / return path works;
- evidence is recorded honestly.

#### Gate

At least one physical-aircraft proof bundle with no implication of broader field validation than actually achieved.

---

### Phase 12 — supervised pilot design

**State: planned.**

Goal: define a test a real buyer can say yes or no to.

Pilot spec should contain:

- site;
- workflow;
- operating hours;
- human supervision model;
- aircraft / payload;
- regulatory assumptions;
- event trigger;
- success metric;
- baseline comparison;
- data retention / privacy;
- failure / abort conditions;
- duration;
- buyer decision at the end.

The pilot should measure a business or operational outcome, not just “the drone flew.”

---

### Phase 13 — first supervised pilot

**State: future.**

Goal: produce customer and field evidence together.

Useful metrics depend on the wedge, but may include:

- time-to-verification;
- labor minutes avoided;
- false callouts avoided;
- area / assets covered;
- mission completion rate;
- operator interventions;
- battery / availability performance;
- evidence quality;
- buyer willingness to continue.

#### Gate

A real buyer decides whether the result is valuable enough to continue, pay, expand, or reject.

A rejection with clear learning is better than ambiguous “interest.”

---

### Phase 14 — first commercial proof

**State: future.**

Goal: move from pilot to repeatable spend.

Possible outputs:

- paid pilot extension;
- annual site software contract;
- managed deployment;
- integration agreement;
- repeat deployment across similar sites.

The business model should be chosen from the selected workflow, not imposed in advance.

---

### Phase 15+ — earn the platform

Only after the first workflow works should SWARM aggressively expand into:

- multi-site orchestration;
- more vendor adapters;
- dock / charging optimization;
- larger fleet scheduling;
- stronger automated reasoning;
- external task APIs;
- physical-agent abstractions beyond drones;
- adjacent verticals;
- government / defense ISR where lawful and strategically justified.

Platform breadth is earned by repeated coordination needs across deployments.

---

## Work lanes

Every active phase should move at least one of these lanes.

| Lane | Question |
|---|---|
| Coordination product | Does SWARM make better fleet-level decisions? |
| Visible proof | Can a reviewer/customer understand that quickly? |
| Physical de-risk | Does the control path survive real hardware? |
| Market validation | Is there a frequent workflow someone will pay to improve? |
| Pilot / commercial | Can a buyer test and then buy it? |
| Capital / ecosystem | Does a program, investor or partner accelerate evidence? |

Do not count activity that advances none of these lanes.

---

## Explicitly deferred work

Unless a customer, hardware, regulatory, pilot, or verified demo blocker requires it, defer:

- speculative ML expansion;
- federation for hypothetical future cells;
- additional vendor stubs with no deployment target;
- more compliance documentation beyond current needs;
- city-scale consumer apps;
- generalized robot orchestration abstractions;
- autonomous dock networks at scale;
- extra dashboard polish;
- broad defense productization;
- proprietary airframes.

---

## YC evidence pack

The technical repo/demo component is now materially ready at the SITL claim level. Any future investor pack may reference the validated demo and bench evidence above, but must preserve the simulation/SITL/physical distinction.

Customer, wedge, physical-aircraft, and pilot evidence remain separate future evidence categories; this roadmap does not upgrade them based on software progress.

---

## Founder decision discipline

University, accelerator and full-time decisions should be tied to real company signals rather than abstract ambition.

Useful triggers include:

- strong recurring customer evidence;
- a credible pilot with a real buyer;
- accelerator acceptance that materially changes execution speed;
- financing tied to a credible plan;
- physical/technical proof that unlocks a real market path.

Until a trigger exists, SWARM should still move with a fixed cadence rather than becoming a vague side project.

---

## North-star sequence

**Coordination proof → workflow proof → wedge → physical proof → pilot → revenue → platform.**

The coordination proof is now feature-frozen for the current demo. The sequence continues with workflow evidence and a physical control-path bridge rather than more speculative demo code.
