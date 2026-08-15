# SWARM roadmap — evidence to scale

Updated 2026-08-15.

This is the forward execution roadmap from the current evidence state. The canonical company thesis is [`../../swarm-thesis.md`](../../swarm-thesis.md). If this roadmap conflicts with it, the thesis wins.

The Phase 0–6 technical foundation remains documented in [`swarmos-roadmap.md`](swarmos-roadmap.md). Older post-Phase-6 plans are historical context only.

## Current decisions

1. **The company is the coordination layer, not a wildfire product.**
   Wildfire, private-land patrol, inspection, security and other verticals are candidate applications until customer evidence proves a first wedge.

2. **The next technical proof does not require owned drones.**
   Build a multi-vehicle PX4 SITL demonstration that makes autonomous allocation, mission dispatch and re-tasking obvious.

3. **The next market proof is workflow-first customer discovery.**
   Ask operators where someone must physically go and check what is happening today. Find repeated, frequent, costly workflows before naming the wedge.

4. **Physical hardware comes after useful signal, not before.**
   The first hardware bridge can use borrowed, partnered or later purchased aircraft. Buying hardware just for optics is not a milestone.

5. **Claims remain typed.**
   Keep `sim`, `SITL`, `bench`, `supervised field`, `pilot`, and `commercial production` distinct.

6. **More code is not automatically more progress.**
   New engineering must either improve the investor demo, customer discovery, physical proof, pilot path, or a blocker revealed by those activities.

7. **The long-term vision remains large.**
   SWARM can evolve from drone-fleet coordination toward a runtime for distributed autonomous physical agents, but that platform must be earned through real deployments.

---

## Current evidence state

| Area | Current evidence |
|---|---|
| Core mission / fleet model | working |
| Auction-based allocation | working |
| End-to-end simulation | working |
| Console / backend / audit | working |
| Autonomy + shadow logic | working |
| CV-backed demo scenarios | working |
| MAVLink/PX4 integration | **SITL-validated** |
| Multi-vehicle YC demo | not yet packaged |
| Physical-aircraft proof | missing |
| Validated first wedge | missing |
| Customer evidence | weak / insufficient |
| Pilot | none |
| Revenue | none |

---

## Phase map

### Phase 7 — technical foundation proof

**State: done enough to move on.**

Existing outputs include the coordination core, operator system, simulation scenarios, autonomy/shadow logic and a PX4/MAVLink path validated in SITL.

Do not reopen Phase 7 merely to add polish unless the next proof exposes a blocker.

### Phase 8 — multi-agent SITL proof

**State: next technical priority.**

Goal: make the coordination primitive understandable in 60–90 seconds.

#### Demo requirements

- 3+ PX4 SITL vehicles;
- different location / battery / availability states;
- neutral task such as `VERIFY anomaly at sector C7`;
- autonomous fleet ranking;
- selected-unit explanation;
- actual mission dispatch through the MAVLink/PX4 path;
- a second higher-priority event or state change;
- re-task / replace / add / RTL behavior;
- audit trail / reason view;
- visible `PX4 SITL / SIMULATION` labeling.

#### Gate

A technically literate viewer should be able to answer:

> “What does SWARM do that the autopilot does not?”

with:

> “It decides what the fleet should do and adapts that plan as the world changes.”

without needing a long founder explanation.

---

### Phase 9 — cross-vertical workflow discovery

**State: next market priority, parallel with Phase 8.**

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

**State: planned.**

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

Unless a demo, customer, hardware, regulatory or pilot blocker requires it, defer:

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

The YC/investor pack should eventually contain:

1. **60–90s multi-agent PX4 SITL video**
2. **public demo / simple landing page**
3. **repo / technical proof**
4. **customer discovery summary with exact patterns**
5. **selected wedge memo, if evidence supports one**
6. **physical-aircraft proof, if achieved**
7. **pilot evidence, if achieved**
8. **clear truth table of what is sim / SITL / physical / customer-proven**

The application should be submitted when the marginal value of waiting for another proof is lower than the value of applying now. Do not delay merely to make the codebase larger.

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

That order is the current operating strategy.
