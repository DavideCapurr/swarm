# SWARM Patrol Cell — historical product hypothesis

> **Status: hypothesis / non-canonical.**
>
> This document records the earlier Patrol Cell concept. It is no longer the canonical first product or wedge.
>
> The current company strategy lives in [`../../swarm-thesis.md`](../../swarm-thesis.md): SWARM is the coordination layer for autonomous physical response, and the first commercial workflow is being discovered through customer evidence.

## What Patrol Cell was

Patrol Cell was conceived as a mobile territorial-awareness and incident-verification product for private high-value land.

The idea used drones as mobile sensors and response units without requiring SWARM-owned fixed camera towers or proprietary ground-sensor infrastructure in the MVP.

The core loop was:

1. patrol or receive a cue;
2. prioritize the event;
3. allocate the best available drone;
4. dispatch;
5. verify;
6. create evidence;
7. escalate to an operator;
8. return / recharge.

That loop remains technically relevant because it exercises the same coordination primitives SWARM needs across other domains.

## Why it is no longer the default wedge

The earlier plan assumed wildfire-risk patrol for vineyards, estates, resorts and other private land would be the first beachhead.

That assumption was not supported by enough real buyer evidence.

The company should not let a technically convenient demo scenario define the market.

Therefore:

- wildfire is a **possible application**, not company identity;
- private-land patrol is a **candidate workflow**, not the default first product;
- existing wildfire / intrusion / search scenarios remain useful simulation fixtures;
- no external material should describe Patrol Cell as a validated market unless new customer evidence earns that conclusion.

## What survives from the concept

Several ideas remain useful and portable:

- mobile observation instead of depending only on fixed sensors;
- rapid verification of uncertain events;
- fleet allocation based on location, battery and capability;
- evidence packaging and auditability;
- human supervision;
- bounded operating environments as easier early deployment settings;
- the ability to reuse one coordination loop across different event types.

These are SWARM primitives, not wildfire-specific features.

## Current replacement question

Instead of asking:

> How do we sell Patrol Cell?

ask:

> **What situations on a large physical site currently require a person to go and check what is happening, and where would coordinated autonomous units reduce that delay enough to create measurable value?**

Candidate environments currently include industrial sites, logistics yards, mines/quarries, energy infrastructure, ports, inspection workflows, large private sites, and other bounded environments.

The first wedge should be selected from repeated customer evidence, not from this archived hypothesis.

## Demo status

Patrol Cell scenarios may still be used to exercise and test the codebase.

For the next YC/investor demo, however, prefer a neutral multi-agent PX4 SITL scenario that highlights the coordination layer itself:

- multiple available vehicles;
- autonomous allocation;
- mission dispatch through MAVLink/PX4;
- a mid-mission priority or availability change;
- re-tasking / replacement / RTL;
- visible reasoning and audit trail.

The demo should be labeled honestly as SITL/simulation.

---

This document remains in the repo for historical context and because some existing tests, scenarios and architecture references still use Patrol Cell terminology. It should not override the canonical thesis.
