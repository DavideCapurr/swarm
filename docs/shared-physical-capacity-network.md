# Shared Physical Capacity Network

Status: **long-term thesis extension, not current product scope or roadmap commitment**.

This document makes explicit one consequence already implicit in [`swarm-thesis.md`](../swarm-thesis.md): if SwarmOS reasons over physical agents as available capabilities rather than as fixed machine identities, the capacity pool does not ultimately need to be owned by one operator.

The strategic source of truth remains `swarm-thesis.md`. If this document conflicts with it, the thesis wins.

---

## Core idea

Today, the cleanest SWARM model is:

```text
operator-owned fleet
      ↓
available physical capacity
      ↓
SwarmOS
      ↓
ExecutionGroup
      ↓
verified execution
```

The long-term extension is:

```text
many owners / organizations / individuals
      ↓
authorized physical capacity
      ↓
SwarmOS
      ↓
objective-aware composition
      ↓
ExecutionGroup
      ↓
verified execution
```

Ownership is not the capability abstraction.

A mission should care about whether an agent can legally, safely and reliably provide a required capability under the current constraints. It should not need to care whether that agent belongs to the requester, a partner, a public agency, a private individual or a future capacity marketplace.

This does **not** mean that every connected machine becomes globally controllable. An owner exposes only the capacity and permissions they explicitly choose to make available.

---

## SwarmOS versus the network

These are two different layers.

**SwarmOS** is the mission-level control system. It decides what physical capacity is required, which eligible agents should provide it, how they should be composed, what should happen when conditions change, and how execution is verified.

**The SWARM Network** is a possible future supply layer. It expands where eligible physical capacity can come from.

The network does not replace the control system.

Without SwarmOS, a large network is only a directory of machines.

Without a wider network, SwarmOS can still be valuable inside one operator's fleet.

Therefore the correct order is:

1. prove the decision layer on controlled fleets;
2. prove physical deployment and delegated authority;
3. support multiple organizations and trust boundaries;
4. only then expand toward shared or market capacity where evidence justifies it.

---

## Capacity sources

A mature capacity pool could contain several classes of supply.

### 1. Owned capacity

Assets controlled by the organization requesting the objective.

Examples:

- company drones;
- municipal drones;
- utility robots;
- port or industrial autonomous systems.

This is the current and near-term model.

### 2. Shared partner capacity

Assets another trusted organization allows to be used under predefined conditions.

Examples:

- mutual-aid emergency fleets;
- contractor aircraft;
- neighboring industrial sites;
- shared infrastructure operators.

### 3. Public-service capacity

Assets exposed for approved public missions under the authority of the relevant agency or incident command structure.

Examples may include emergency response, search and rescue, disaster mapping or infrastructure assessment.

### 4. Private opt-in capacity

Individuals could eventually register compatible physical agents and choose whether selected capabilities may be used outside their own property or organization.

A private owner might expose a drone for:

- personal property inspection;
- perimeter verification;
- smoke or fire verification;
- search and rescue;
- disaster mapping;
- other explicitly authorized emergency missions.

The owner could independently refuse other categories of use.

### 5. Market capacity

A later-stage network could allow capacity to be purchased or compensated on demand.

A requester could express an objective and constraints while SwarmOS selects the best authorized combination of owned, shared or market capacity according to capability, response time, reliability, cost and policy.

This is a possible economic layer, not the current company thesis.

---

## Contribution must be permissioned

A machine joining the network should not mean handing unrestricted authority to SWARM.

Conceptually, an owner should be able to publish a bounded policy such as:

```text
agent: home-drone-184
capabilities:
  - rgb_observation
  - thermal_observation

private_use:
  allowed: true

shared_use:
  wildfire_verification: true
  search_and_rescue: true
  disaster_mapping: true
  commercial_jobs: false
  police_surveillance: false

constraints:
  max_radius: 5 km
  night_operations: false
  owner_recall: always
```

The exact policy model is future work. The important principle is that **capacity is exposed under constraints, not surrendered wholesale**.

A real implementation would also need to reason about jurisdiction, operator authority, airspace, certification, privacy, sensor permissions, insurance, trust, cybersecurity, compensation, revocation and incident command.

These are not small implementation details. They are prerequisites for any real cross-owner network.

---

## Emergency-response example

Consider a future objective:

```text
VERIFY POSSIBLE WILDFIRE
```

Required capabilities might include:

- thermal observation;
- visual observation;
- geolocation;
- communications;
- persistence.

The eligible capacity pool could theoretically include:

- a nearby private drone whose owner opted into wildfire verification;
- a municipal thermal aircraft;
- a fire-service long-endurance UAS;
- a communications relay platform;
- other authorized systems already operating nearby.

SwarmOS would not ask, "Which drone belongs to us?"

It would ask, "What authorized physical capacity can satisfy this objective under the current operational rules?"

For an actual wildfire response, aviation authority, incident command, deconfliction and emergency rules would determine what can legally participate. The example describes the long-term abstraction, not a claim that privately owned aircraft can be autonomously inserted into current fire operations.

---

## Home and property use

The same architecture can support a private physical agent whose default role is local.

A home, estate, farm or small site could use a compatible drone or robot for:

- alarm verification;
- perimeter inspection;
- roof or infrastructure checks;
- smoke detection;
- checking remote parts of a property;
- other bounded observation or inspection tasks.

If the owner chooses, selected capabilities could also be exposed to trusted or public-interest networks.

This is a possible application of the same capacity model. It is **not** the current wedge, and SWARM should not become a consumer security-drone company by default.

Any such use must preserve the existing product boundary: SWARM coordinates physical response; it is not an autonomous weapons system and should not autonomously cause harm to people.

---

## Architectural consequence

The current capability-aware architecture is directionally correct for this end-state because missions can reason about required capabilities rather than fixed machine IDs.

If cross-owner capacity ever becomes real product scope, `PhysicalAgent` or its surrounding resource model would also need concepts such as:

- owner / tenant;
- trust domain;
- sharing policy;
- authorization scope;
- jurisdiction;
- certification;
- provenance;
- compensation / cost;
- privacy constraints;
- revocation state;
- network availability.

Do **not** add these fields speculatively now.

The near-term architectural rule remains:

> **Beachhead narrow, ontology general.**

Do not build the marketplace, consumer network, cross-owner authorization system or emergency-sharing layer until the core SwarmOS decision loop has physical and customer evidence.

---

## Economic implication

A sufficiently trusted network could unlock unused physical capacity.

The analogy is not that drones become identical commodities. Different machines retain different capabilities, constraints and reliability.

The shift is from requesting a machine by identity to requesting a physical outcome:

```text
old:
  send drone-241

future:
  provide thermal + visual coverage here for 20 minutes
```

SwarmOS can then compose the valid capacity that exists at that moment.

At scale, this could improve:

- response time;
- utilization of idle assets;
- geographic coverage;
- resilience;
- access to specialized capability;
- economics of owning versus accessing physical machines.

A network effect is possible only after the decision layer, trust model and operational reliability work. The network itself is not a substitute for those foundations.

---

## Strategic invariant

The long-term trajectory can be expressed as:

```text
machine identity
      ↓
capability

single-owner fleet
      ↓
authorized capacity pool

owned capacity
      ↓
owned + shared + public + private opt-in + market capacity

manual assignment
      ↓
objective-level software composition
```

The end-state remains:

> **Make physical capacity programmable.**

A future contributor should be able to add a compatible physical agent to a network, define exactly what capacity it may expose and under what conditions, and let SwarmOS use that capacity only when an authorized objective requires it.

That is an extension of the existing thesis, not a change of direction.