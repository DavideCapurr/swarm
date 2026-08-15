# SWARM — YC supporting answers

> Updated 2026-08-15.
>
> Companion to [`application-draft.md`](application-draft.md) and [`readiness-and-gaps.md`](readiness-and-gaps.md).
>
> Canonical thesis: [`../../swarm-thesis.md`](../../swarm-thesis.md).

## “Why should we believe this can reach real aircraft?”

> SWARM deliberately separates the coordination problem from the airframe. The core product already runs end-to-end in simulation, and the MAVLink/PX4 adapter has been validated against PX4 SITL for connect, telemetry ingest, mission dispatch and return-to-launch.
>
> That does not equal physical-aircraft proof, and we do not claim that it does. The next bridge is supervised hardware validation using compatible aircraft accessed through the lowest-friction credible path: borrowing, a lab, a drone operator, a partner, or purchasing only if justified.
>
> The important architectural point is that the same adapter and mission path used in SITL is the path intended to control physical aircraft. We are de-risking the coordination layer first, then moving the evidence level from SITL to supervised hardware deliberately rather than building a custom airframe.

## “Why not just use PX4 / DJI / Skydio directly?”

> Those systems solve the single-aircraft flight problem. SWARM sits above them. It decides which unit should respond, how fleet state affects the mission, how multiple tasks are allocated, when one aircraft should replace another, and what happens when priorities or availability change.
>
> The autopilot flies the aircraft. SWARM decides what the fleet should do.

## “What is actually proven today?”

Current proof ladder:

- coordination logic: working in simulation;
- multi-agent state / allocation: working;
- operator Console / backend / telemetry / audit: working;
- MAVLink/PX4 path: **SITL-validated**;
- physical aircraft: **not yet validated**;
- customer wedge: **not yet validated**;
- pilot: none;
- revenue: none.

The final application should preserve those distinctions exactly.

## “Can you legally deploy this?”

> Early physical tests will be supervised and bounded under the applicable operating rules for the jurisdiction and mission. We are not assuming broad BVLOS autonomy is already solved. Wider autonomous operations are a real scaling constraint that has to be addressed market by market.
>
> That constraint does not prevent us from developing and validating the coordination layer in SITL and supervised operations while we identify a first workflow that justifies the regulatory work.

Do not submit jurisdiction-specific legal claims without re-verifying the current rules immediately before submission or deployment.

## “What about privacy?”

> The system is designed around explicit operator accountability, auditable decisions and minimizing unnecessary data collection. Privacy requirements depend heavily on the first deployed workflow and geography, so the final product policy should be shaped around the selected wedge rather than pretending one universal rule fits every site.

Use the repo's security/privacy documentation for implementation detail, but do not oversell existing controls as proof that every future public-space deployment is automatically acceptable.

## “What is the first market?”

> We have intentionally reopened that question. Earlier versions assumed wildfire-risk patrol on private land. That was too thesis-driven relative to the amount of real buyer evidence we had.
>
> We are now interviewing operators of large physical sites and asking where someone currently has to physically go and verify what is happening. The first wedge will be the repeated workflow with the best combination of frequency, cost/urgency, clear budget ownership, deployment feasibility and multi-agent advantage.

Candidate environments include industrial sites, logistics yards, mines/quarries, energy infrastructure, ports, inspection workflows and other bounded sites.

Wildfire remains one possible application, not the company identity.

## “How big can this be?”

Do not answer with “the global drone market.”

Once a wedge is selected, use a bottoms-up model:

`target sites × annual contract value × realistic early penetration`

Then explain the expansion ladder:

1. first workflow;
2. adjacent workflows on the same site;
3. more sites in the same vertical;
4. adjacent verticals using the same coordination primitive;
5. multi-vendor / multi-site fleet coordination;
6. external task/API layer;
7. broader physical-agent runtime.

The long-term market can be much larger than the first wedge, but the first number must come from a buyer and an existing workflow.

## “Why now?”

Potential tailwinds to verify with current sources before submission:

- increasingly capable and cheaper autonomous drones;
- mature commodity autopilots;
- more drone-in-a-box deployments;
- more AI systems capable of generating real-world tasks from sensor data;
- increased use of remote inspection and autonomous operations;
- growing complexity from fleets with multiple vehicles, vendors and simultaneous missions.

Do not submit stale funding/market statistics from old research files without re-checking them.

## “Why is coordination defensible?”

Do not claim that a scheduler or vendor-neutral adapter alone is a moat.

The defensibility thesis has to be earned through deployment:

- reliable multi-agent decision-making;
- deep workflow integration;
- operational data from real fleets;
- adapter maturity across real hardware;
- safety / audit / evidence tooling;
- increasingly complex fleet behavior that customers depend on;
- switching costs created by operational integration, not marketing language.

Today, the moat is a thesis plus unusual technical progress. It becomes real only through deployment and customer dependence.

## “Why not buy drones now?”

> Buying hardware only to make a prettier investor video is not the highest-value next step. We can prove the coordination behavior with multiple PX4 SITL vehicles today. Once customer discovery identifies a workflow worth deploying into, we can bridge the same control path to borrowed, partnered or purchased compatible aircraft with a much clearer reason for the hardware choice.

## “What would make you pick a wedge?”

Use repeated evidence, not enthusiasm.

A strong wedge signal looks like:

- several independent operators describe the same workflow;
- it happens frequently;
- the current verification process is slow, expensive or operationally painful;
- a clear buyer owns the budget;
- mobile autonomous observation materially improves it;
- coordination across multiple units matters;
- supervised deployment is plausible;
- at least one buyer will seriously evaluate a pilot against a measurable success criterion.

## “What is the long-term company?”

> SWARM starts as coordination software for autonomous drone fleets. The larger vision is to make physical presence programmable: software expresses an objective and SWARM coordinates the available autonomous agents that can carry it out.
>
> Drones are the first agent class because they are mobile, increasingly capable and replaceable. Over time the same coordination model could extend to other autonomous physical systems.

## Final rule

Before submission, replace generic answers with the strongest real evidence available at that moment.

Do not use this document as permission to sound more certain than the company actually is.
