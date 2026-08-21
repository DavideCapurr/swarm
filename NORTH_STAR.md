# SWARM North Star

Status: **permanent strategic north star**.

This document exists to prevent the company from being accidentally redefined by its first MVP, demo, customer, hardware integration, or market wedge.

SWARM may begin narrowly. The company should not think narrowly.

The current implementation proves a small but necessary primitive. The long-term thesis is much larger:

> **Make physical capacity programmable.**

The permanent product invariant remains:

> **SwarmOS decides. Physical agents execute.**

The permanent strategic rule is:

> **Narrow wedge. General ontology. Large destination.**

A narrow first product is acceptable. A narrow definition of the company is not.

---

## 1. What SWARM is ultimately about

SWARM is not fundamentally a drone fleet management company.

SWARM is not fundamentally a wildfire company, security company, inspection company, port company, or consumer emergency-response company.

Those may be wedges, applications, or deployment environments.

The deeper company thesis is that the physical world will contain a growing amount of autonomous and semi-autonomous capacity:

- aerial drones;
- ground robots;
- autonomous vehicles;
- marine systems;
- mobile sensors;
- fixed sensing and infrastructure;
- specialized machines that do not yet exist as mature products today.

These systems will differ in:

- capabilities;
- sensors;
- payloads;
- mobility;
- range;
- endurance;
- cost;
- reliability;
- location;
- availability;
- certification;
- operating environment;
- autonomy level;
- ownership and authorization boundaries.

The important abstraction is therefore not machine identity.

It is **available physical capability**.

A future software system should be able to express an objective without manually selecting the exact physical machines that will perform it.

Conceptually:

```text
objective
    ↓
required capabilities
    ↓
available physical capacity
    ↓
SwarmOS composition
    ↓
ExecutionGroup
    ↓
execution
    ↓
evidence
    ↓
adaptation / recomposition
```

That is the company trajectory.

---

## 2. The world SWARM is betting on

The core bet is not simply that there will be more drones.

The bet is that AI will progressively move from information work into the physical world.

The first phase of modern AI primarily makes cognition and software more programmable:

```text
human
  ↓
AI / software
  ↓
information
```

The next phase increasingly connects software intelligence to physical execution:

```text
human / software / AI agent
             ↓
          objective
             ↓
      physical systems
             ↓
        physical world
```

The physical systems are unlikely to become one uniform class of general-purpose machine overnight.

A more plausible intermediate world contains many specialized autonomous systems operating together:

- inspection drones;
- thermal drones;
- long-endurance aircraft;
- warehouse robots;
- quadrupeds;
- autonomous vehicles;
- delivery systems;
- agricultural machines;
- subsea robots;
- surface vessels;
- security systems;
- fixed cameras and sensors.

As individual machines become more capable, a second problem becomes more important:

> **Which available physical capability should own a changing objective?**

That is the layer SWARM intends to own.

---

## 3. The division of intelligence

SWARM should not try to replace every intelligence layer inside every machine.

Individual machines, autopilots, robot foundation models, navigation stacks, vendor runtimes, and local controllers can become dramatically smarter over time.

That progress can make SWARM more useful, not less.

The division should remain:

### Executor intelligence

The physical machine handles the bounded local problem of execution:

- stabilization;
- motion control;
- navigation;
- obstacle avoidance;
- manipulation where applicable;
- local safety behavior;
- sensor operation;
- execution of assigned primitives.

### SwarmOS intelligence

SwarmOS owns the mission-level problem:

- what objective currently matters;
- what capabilities it requires;
- which capacity is eligible;
- which combination of agents should provide it;
- how many agents are required;
- what roles they receive;
- who owns the mission;
- what capacity must remain in reserve;
- when an executor should be replaced;
- when capacity should be reallocated;
- how simultaneous objectives compete for scarce resources;
- whether execution actually satisfied the objective;
- what happens next when the world changes.

The more capable physical executors become, the more SwarmOS can operate at the level of outcomes instead of low-level commands.

---

## 4. Drones are the first executor, not the final category

Drones are the correct place to prove the current architecture because they already expose many properties required by the long-term system:

- remote physical execution;
- constrained endurance;
- location-dependent usefulness;
- heterogeneous sensors and payloads;
- concurrent missions;
- scarce capacity;
- failures;
- dynamic availability;
- meaningful mission ownership;
- a clean separation between mission-level decisions and local autopilot execution.

Therefore the near-term path can remain very narrow:

```text
drones
  ↓
heterogeneous drones
  ↓
multiple fleets / vendors
  ↓
aerial + ground
  ↓
cross-domain physical systems
  ↓
programmable physical capacity
```

Do not skip these layers merely to make the product look more ambitious.

But do not confuse the first layer with the destination.

The current MVP is evidence for the architecture, not the definition of the company.

---

## 5. Expected strategic progression

Dates are directional, not commitments. The important thing is the sequence of abstractions.

### Phase A — mission-level control for drone fleets

The immediate product proves:

- centralized mission authority;
- objective ownership;
- eligibility and allocation;
- capability-aware selection;
- multi-agent composition;
- concurrent objectives;
- reserve capacity;
- failure replacement;
- execution evidence;
- adaptation when the world changes.

The question is:

> Can SwarmOS decide what a drone fleet should do next better than a manually managed or platform-bound workflow?

### Phase B — capacity pools instead of individual aircraft

The system increasingly reasons in terms of capability rather than machine identity.

A mission does not request `drone-17`.

It requests something like:

```text
VERIFY INFRASTRUCTURE ANOMALY

requires:
- thermal observation
- close visual inspection
- communications relay
- persistence
```

SwarmOS selects the valid providers.

If one machine disappears, the question is not merely "what replaces machine X?"

It is:

> **Which required capability disappeared, and what valid composition can restore it?**

### Phase C — heterogeneous autonomous fleets

The capacity pool expands beyond one executor class.

An objective may be satisfied by:

```text
long-endurance aircraft
+ thermal multirotor
+ ground inspection robot
+ communications relay
+ fixed sensor
```

The unit of reasoning becomes the capability contribution to the objective.

### Phase D — physical capacity control plane

SwarmOS becomes a common mission-level layer above heterogeneous execution systems.

The stack becomes conceptually:

```text
human / enterprise software / AI agent
                  ↓
              objective
                  ↓
               SwarmOS
       capacity selection
       composition
       priorities
       policy
       adaptation
       verification
                  ↓
          execution runtimes
                  ↓
     drone / robot / vehicle / USV / ...
```

The requester increasingly does not need to know which machine will perform the work.

### Phase E — distributed physical infrastructure

If trust, regulation, economics, safety, authorization, and interoperability are earned, the available capacity pool can eventually extend across docks, depots, sites, organizations, municipalities, contractors, private owners, and other networks.

At this stage, docking or charging infrastructure is best understood as a set of **physical-capacity nodes**, not merely drone garages.

A node can expose capabilities such as:

```text
location: X
available:
  visual_observation ×2
  thermal_observation ×1
  payload_5kg ×1
```

SwarmOS reasons over the authorized capacity exposed by the network.

This is where the phrase **Make physical capacity programmable** becomes literal.

---

## 6. The physical-cloud analogy — and its limit

A useful internal analogy is cloud computing.

In software infrastructure, an application can request computation without caring about the identity of the exact physical server that runs it.

A future physical system may increasingly request an outcome without caring about the identity of the exact executor.

Conceptually:

```text
software world:
run(workload)
    ↓
compute control plane
    ↓
physical compute

physical world:
achieve(objective)
    ↓
SwarmOS
    ↓
physical capacity
```

But the analogy must never imply that physical agents are perfectly fungible.

A thermal drone is not equivalent to a quadruped. A truck is not equivalent to a USV. Location, capabilities, energy, safety, regulation, cost, ownership, and environment all matter.

That makes capability-aware composition more important than a simplistic "Kubernetes for robots" framing.

Use the cloud analogy to understand the trajectory, not as a substitute for the actual product thesis.

---

## 7. Where SWARM can matter first

The first strong environments are likely to be places where physical capacity already has clear economic value and operational authority is concentrated.

Examples include:

- industrial and energy campuses;
- utilities;
- ports and maritime operations;
- mining and remote industrial sites;
- offshore infrastructure;
- search and rescue;
- disaster response;
- wildfire intelligence;
- critical infrastructure inspection;
- security and perimeter operations.

These environments can be better first wedges than cities because they often have:

- bounded geography;
- one operational owner;
- measurable response or inspection costs;
- repeated missions;
- existing physical assets;
- clearer authority boundaries;
- a more direct path to physical deployment.

A city-scale response network remains a possible end-state, not a requirement for the first product.

See also:

- [`swarm-thesis.md`](swarm-thesis.md)
- [`docs/shared-physical-capacity-network.md`](docs/shared-physical-capacity-network.md)
- [`docs/final-urban-response-vision.md`](docs/final-urban-response-vision.md)

---

## 8. The city-scale end-state

If the architecture succeeds and the necessary trust layers emerge, cities and regions could eventually contain distributed autonomous capacity across many physical nodes.

The important picture is not "thousands of identical SWARM drones."

It is:

```text
many capacity owners
many executor types
many physical nodes
many authorization domains
        ↓
authorized available capacity
        ↓
      SwarmOS
        ↓
objective-aware composition
        ↓
verified physical response
```

A water-main failure, infrastructure anomaly, search-and-rescue event, fire, environmental incident, logistics request, or other authorized objective could require several capabilities at once.

The software might ask for:

```text
respond(event, constraints)
```

and SwarmOS would determine:

- required capabilities;
- eligible providers;
- response time;
- composition;
- role assignment;
- reserve capacity;
- policy and authorization;
- adaptation;
- verification.

The application generating the objective should eventually need less knowledge of the specific machines underneath it.

That is a physical infrastructure thesis, not a drone-feature thesis.

---

## 9. The moat cannot be "we coordinate drones"

If the world evolves in this direction, several categories can move toward the same layer:

- hardware manufacturers;
- autonomy-stack companies;
- robot foundation-model companies;
- fleet-management systems;
- industrial software platforms;
- vertical operators;
- open interoperability systems.

Therefore the durable value cannot be merely:

- dispatching drones;
- supporting multiple vendors;
- showing several machines on one map;
- translating natural language into waypoints;
- assigning the nearest available executor.

SWARM should progressively own deeper mission-level primitives.

### Canonical physical state

A trustworthy representation of available capacity:

```text
identity
capabilities
state
availability
location
constraints
cost
risk
reliability
```

### Capability model

A way to express what an objective requires and what different agents can contribute.

### Mission authority

The ability, within explicit boundaries, to make real allocation, composition, replacement, retasking, and prioritization decisions.

This is one of the most important commercial proofs.

A technically excellent allocator is not enough if meaningful decisions can never be delegated to software.

### Policy and safety

The control plane must eventually reason about:

```text
is this allowed?
is this agent certified?
is this use authorized?
what human approval is required?
what safety boundary applies?
what jurisdiction applies?
what is the objective priority?
```

### Execution and evidence

SWARM must know whether the objective was actually achieved.

The loop cannot end at "command dispatched."

It must end at verified outcome or explicit failure.

---

## 10. The anti-collapse rule

Every time SWARM becomes more concrete, there is a risk that the company thesis shrinks to match the latest implementation.

Examples of dangerous reasoning:

- "The demo only uses PX4, therefore SWARM is PX4 fleet software."
- "The first customer is an industrial site, therefore SWARM is industrial inspection software."
- "The current objective is intrusion verification, therefore SWARM is a security-drone company."
- "The first revenue comes from drones, therefore robots and vehicles are irrelevant."
- "The MVP needs only one allocator, therefore the long-term capability model is unnecessary."

These conclusions are invalid unless new evidence disproves the broader thesis.

The correct interpretation is:

```text
CURRENT WEDGE
what must be narrow enough to prove and sell now

CURRENT PRIMITIVE
what technical capability the wedge proves

NORTH STAR
what category of infrastructure the company can become
```

Do not allow those three layers to collapse into one another.

---

## 11. Decision filter for product work

For any important roadmap, architecture, demo, or market decision, ask four questions.

### 1. Does this strengthen the current proof?

Does it make SwarmOS more clearly responsible for mission-level decisions instead of presentation logic, adapters, or scripted scenarios?

### 2. Does this create real customer evidence?

Does it help discover or prove a real objective where automated physical-capacity allocation matters?

### 3. Does it preserve the general ontology?

Can the core concept still be expressed as objective, capability, capacity, constraint, composition, execution, evidence, and adaptation rather than a hard-coded vertical or machine-specific primitive?

### 4. Are we accidentally building the 2040 product before earning the 2026 product?

Do not add speculative marketplace, city-network, cross-owner authorization, robot-domain, or infrastructure layers merely because they fit the north star.

The north star should guide architecture and strategic direction.

It should **not** justify premature complexity.

---

## 12. What not to build yet

Preserving ambition does not mean implementing everything immediately.

Do not build without evidence:

- a citywide capacity marketplace;
- consumer subscriptions;
- thousands of docking nodes;
- generalized cross-owner billing;
- every robot protocol;
- autonomous municipal dispatch;
- speculative defense-specific core primitives;
- a universal physical-agent ontology that blocks shipping;
- a giant policy system before real authority constraints are known.

Near-term execution should stay ruthless and narrow.

The correct rule is:

> **Do not build the final world today. Build primitives that remain valid if the final world arrives.**

---

## 13. What the current repository means in this trajectory

The current repository is important because it attempts to prove the first invariant in executable form:

> **SwarmOS decides. Physical agents execute.**

Central allocation, mission ownership, BUSY exclusion, capability-aware selection, `ExecutionGroup` composition, replacement, runtime evidence, and failure handling matter because they are early primitives of the larger control plane.

PX4 SITL is not the final product.

It is an execution environment in which the architecture can currently be falsified or validated.

The demo should therefore answer:

> Can SwarmOS observe the world, decide what physical capacity should own an objective, issue work, observe execution, and adapt when conditions change?

If yes, the demo has proven a primitive.

It has not proven the entire company.

---

## 14. The key commercial question

The long-term technical vision only matters if mission-level authority exists in the real world.

The decisive near-term question is:

> **Is there already an environment where an operational objective requires a changing combination of physical capabilities, those capabilities exist across available agents, and operators are willing to delegate meaningful composition or adaptation decisions to software within defined constraints?**

Strong evidence progresses from:

```text
we use several assets
        ↓
we manually coordinate them around one objective
        ↓
changes and failures force recomposition
        ↓
this creates measurable operational cost or delay
        ↓
software could own specific decisions within our rules
        ↓
here is the mission where we would test it
```

Finding that first environment is more important than making the demo look futuristic.

---

## 15. Permanent language

The following phrases express the strategic identity of the company and should remain stable unless evidence disproves the thesis.

### Product invariant

> **SwarmOS decides. Physical agents execute.**

### Architecture thesis

> **Mission intelligence should be separable from individual machines.**

### Capacity thesis

> **Physical agents should be addressable by capability, not only by identity.**

### Wedge rule

> **Narrow wedge. General ontology. Large destination.**

### Long-term vision

> **Make physical capacity programmable.**

---

## 16. What success ultimately looks like

The mature version of SWARM is not successful because it controls many drones.

It is successful when software can reliably turn an objective into verified use of the right available physical capacity without requiring the requester to manually orchestrate every machine.

The long-term transition is:

```text
"these are the machines I own"
              ↓
"this is the physical capacity available to me"
              ↓
"this is the outcome I need"
```

At that point, physical capacity becomes an addressable software primitive.

That is the north star.

---

## 17. Governance of this document

This file is intentionally strategic rather than a claim of current capability.

It must not be used to overstate what the repository has validated.

For present technical truth, validation boundaries, and current proof, use the architecture, status, bench, and validation documents.

For near-term customer discovery, preserve the distinction between hypothesis and evidence.

For long-term strategic decisions, this document exists specifically to prevent local optimization around the MVP from erasing the company-scale thesis.

If a future wedge succeeds, ask how it proves the north star.

If a future wedge fails, change the wedge before casually abandoning the north star.

If evidence shows the north star itself is wrong, change it explicitly and deliberately.

Do not let it disappear accidentally.