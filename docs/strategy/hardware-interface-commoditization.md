# Hardware-interface commoditization

## Strategic assumption

SWARM must remain valuable even if heterogeneous physical agents become trivially discoverable and controllable through standardized interfaces.

Hardware interoperability is not the product boundary. Compatible execution interfaces sit below SWARM.

SWARM begins at mission-level authority: given an objective, available capacity and operational constraints, it decides which capabilities are required, which physical agents should provide them, how those agents are composed into an ExecutionGroup, how scarce capacity is allocated across concurrent objectives, how the group changes when reality changes, and what evidence is sufficient to conclude or escalate the objective.

This assumption should be treated as deliberately adversarial to the company thesis. If a generic AI agent with a standardized hardware interface can reliably perform allocation, composition, recomposition, authority enforcement and outcome verification under real operational constraints, SWARM's independent product value is materially weaker.

## Product boundary

```text
objective / policy / constraints
            ↓
         SwarmOS
            ↓
mission allocation + capability composition
+ ownership + reserves + recomposition
+ verification + escalation
            ↓
compatible execution interface
            ↓
drone / robot / vehicle / vessel / sensor
```

SWARM should not try to own the universal hardware protocol unless deployment evidence later shows that doing so is necessary.

Vendor adapters remain execution plumbing. A future common hardware standard may replace some or all of that plumbing without changing the reason SwarmOS exists.

## What must not become the moat

Do not rely on any of the following as the company moat:

- discovering heterogeneous devices;
- translating between vendor command APIs;
- exposing a common read/write interface;
- describing hardware capabilities in a common schema;
- basic tool calling against physical devices;
- a generic LLM loop that happens to send device commands.

Assume these capabilities commoditize.

The defensible layer, if it exists, must come from the operational decision system required to safely and reliably resolve objectives into physical action across real constraints, scarce capacity, concurrent work, failures, policy and evidence.

## Customer-discovery falsification test

Add this question to strategic discovery after the operator has explained the current workflow:

> If every aircraft, robot or other physical asset exposed the same clean capability-aware API tomorrow, what mission-level decisions would still be difficult to automate?

Follow with concrete probes:

- who decides which capabilities an objective requires;
- how scarce capacity is allocated when several objectives compete;
- how reserves are maintained;
- how assets from different teams or systems are combined;
- what happens when a required capability disappears mid-mission;
- which reallocations can happen automatically and which require approval;
- what operational, regulatory or safety constraints must be enforced centrally;
- what evidence is required before the system can declare an objective complete;
- whether a generic AI agent would be trusted to make those decisions directly.

### Strong evidence for SWARM

The operator says that even with perfect interoperability, mission ownership, priority, resource allocation, composition, adaptation, policy enforcement or verification would remain a meaningful operational problem.

### Weak evidence

The main difficulty is connecting to hardware or translating between vendor systems.

### Fatal evidence

Once all hardware is exposed through one standard interface, a generic agent can make the relevant mission decisions reliably enough and there is no meaningful need for a separate authoritative control plane.

## Architecture rule

Do not add speculative MHS/MCP/common-hardware adapters, provider layers or new abstraction classes solely because a hardware standard exists.

The current architecture should preserve a clean boundary between:

1. mission-level decision authority owned by SwarmOS; and
2. physical execution performed through adapters/interfaces.

Implement a new standard only when it creates real deployment leverage or is required by a concrete integration.

## Strategic consequence

A successful hardware standard is potentially an accelerant for SWARM rather than a threat: it can reduce integration cost and make more physical capacity addressable.

But it also raises the bar for the thesis. SWARM must prove that the hard problem survives after interoperability becomes cheap.

The recurring question is therefore:

> Assume hardware integration is free. What is still hard enough that someone needs SWARM?

The intended answer is mission-level allocation and authority over heterogeneous physical capacity. Customer and field evidence, not additional speculative software, must prove that answer.
