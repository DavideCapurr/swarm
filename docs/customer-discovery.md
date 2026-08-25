# SWARM Customer Discovery Playbook

This document defines how SWARM should approach operator outreach and how interview evidence should affect strategy.

It is subordinate to `swarm-thesis.md`. If there is a conflict, the thesis wins.

## Messaging rule

Do not frame SWARM as a thesis about **larger fleets of small autonomous aircraft**, cheap drones replacing larger aircraft, or fleet size for its own sake.

That framing is too leading and can pull the operator into debating airframe substitution instead of describing the real operational decision problem.

Preferred neutral framing:

> I’m building SWARM, software for coordinating autonomous aircraft around operational objectives.

For more technical operators:

> I’m building SWARM, software for deciding how available autonomous aircraft should be used across operational objectives.

The message should make the operator explain their current workflow before SWARM explains its solution.

## Opening questions

Prefer questions about real operating decisions, for example:

> When several mission requests arrive or priorities change, who decides which available aircraft should take each task: individual pilots, a central operations team, existing software, or another workflow?

Or, for inspection-heavy environments:

> When something needs to be checked in the field, how is it decided which available aircraft or team should handle it?

Do not ask whether they would buy a swarm, whether they want more drones, or whether small drones can replace larger aircraft.

## What to discover

The high-value unknowns are:

- what output or data product the customer actually needs;
- how that output is translated into sensor, payload, or other capability requirements;
- who owns mission-level allocation today;
- whether decisions are centralized or fragmented;
- whether capability requirements are explicit;
- how operators choose between assets with different sensors, payload, endurance, range, certifications, or roles;
- whether payloads are integrated, interchangeable, or dynamically configurable;
- whether several assets are ever combined for one objective;
- what happens when priorities change after dispatch;
- how unavailable, failed, or busy assets are handled;
- whether coordination is manual, rule-based, or software-driven;
- how much authority an operator would delegate to software;
- how often simultaneous objectives create contention for limited physical capacity.

## Capability-first interpretation

Treat aircraft and other physical agents as heterogeneous capacity, not interchangeable units.

A useful operator answer may reveal constraints such as:

- thermal or optical sensing;
- wide-area observation;
- mapping;
- relay/communications;
- payload capacity;
- endurance;
- range;
- cargo/person transport;
- specialized delivery capability;
- safety or regulatory eligibility.

The strategic question is not whether one hardware class replaces another. It is whether software must translate an objective into the right composition of available capabilities.

A useful real-world decomposition may be even more explicit:

`desired operational output / data product -> required sensor or payload capability -> compatible physical platform -> allocation / composition`

Do not hard-code this exact chain into the product because one operator described it. Use it as a discovery lens and look for repetition across operators and verticals.

## Evidence discipline

Do not change the architecture or market thesis because of one interview response.

Classify every meaningful response into:

- **supports**: evidence consistent with an existing hypothesis;
- **contradicts**: evidence against an existing hypothesis;
- **new lead**: a potentially useful workflow or vertical to investigate;
- **unknown**: something the response did not establish.

A single response can update outreach wording immediately, but product changes should normally require repeated evidence or a direct contradiction of a core assumption.

Do not convert one operator opinion into a validated wedge.

## Current evidence update — 2026-08-20

A DOI aviation/UAS operator response produced the following useful signal:

- airframe capability differences matter materially;
- small UAS are not a general substitute for larger aircraft with fundamentally different payload, endurance, transport, or suppression capabilities;
- small UAS can still be useful for hotspot identification, perimeter/intelligence work, rugged-area observation, mapping, facility inspection, bridge inspection, surveillance, and related missions;
- therefore the stronger SWARM framing is heterogeneous capability composition, not cheap-airframe substitution.

A follow-up from the same operator added a more specific workflow signal:

- the process starts by determining what data is required by the customer;
- the required data informs which camera or sensor is needed;
- the sensor requirement then informs which UAS is compatible with the mission;
- some platforms can change payloads while others have integrated sensors;
- determining the required data can involve back-and-forth between the operating team and the customer.

This is evidence **against** making small-aircraft substitution the pitch.

It is evidence **consistent with** the existing SwarmOS direction:

`objective -> required capabilities -> available physical capacity -> composition`

It also provides early evidence that a real operating workflow can contain the more specific causal chain:

`required data product -> sensor / payload requirement -> compatible aircraft`

It does **not** prove that aircraft allocation itself is manual, that several aircraft must be composed for one objective, that the workflow is painful enough to buy software for, that operators would delegate mission-level authority, or that wildfire is the first wedge.

## Evidence update — Georgios, 2026-08-25

Georgios's operator/expert feedback adds a distinct authority signal. It should
not be merged into the DOI evidence above because it answers a different
question.

Confirmed by the response:

- mission requirements are established before vehicle selection;
- a mission may require a heterogeneous combination of capabilities rather
  than one preferred vehicle type;
- the current process is largely human-led;
- more automation is plausible, but the acceptable level depends on the
  mission/risk owner's comfort;
- a system must explain why a composition or reassignment was selected;
- decision support is a credible entry point before broader delegation.

This supports progressive, mission-scoped delegation. It does **not** support a
new global autonomy mode or a four-mode product. The implementation question is
which exact decision kinds a mission/risk owner delegates, under which
constraints, and at which grant revision.

Still unproven:

- willingness to adopt or pay for SWARM;
- which decision kinds operators will delegate first;
- the exact geofence, altitude, executor, reserve, and mission constraints;
- decision frequency and the cost of the present process;
- integration feasibility and economic advantage in a live workflow;
- whether the same authority pattern repeats across operators and verticals.

Product changes from this evidence must remain generic: deterministic decision
records, exact approval/rejection/override, and delegated rules for launch,
replacement, and reinforcement. Do not infer a trust score, automatic expansion
of authority, or a vertical-specific workflow from one source.

## Product interpretation guardrail

The new evidence strengthens the reason to make capability-aware decisions visible in the product and demo. It does not yet justify:

- wildfire-specific product primitives;
- hard-coding cameras or payload models into the architecture;
- replacing generic capabilities with a sensor-only model;
- assuming all objectives originate as data products;
- implementing dynamic payload attachment as a core primitive from this response alone.

If repeated operator evidence shows that platform capability depends materially on interchangeable payload configuration, test a future model of:

`platform capabilities + attached payload capabilities -> current physical capacity`

Until then, keep the canonical capability model generic.

## Outreach allocation implication

Increase discovery emphasis on environments where heterogeneous inspection and verification capacity is likely to matter, especially:

- critical infrastructure;
- industrial inspection;
- utilities;
- mining and remote industrial sites;
- ports and large compounds;
- infrastructure inspection and anomaly verification.

Wildfire remains worth investigating, but should be approached as a coordination/composition problem rather than as a small-drone replacement thesis.

## Writing style

Messages should be short, specific, human, and easy to answer asynchronously.

Avoid:

- em dashes;
- inflated startup language;
- "revolutionize", "transform", "AI-powered", "next-generation";
- explaining the entire product before asking the question;
- leading the operator toward the answer we want;
- claiming a workflow problem has been validated when it has not.

Prefer one concrete question that can be answered in one or two lines.
