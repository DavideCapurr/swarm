# SWARM roadmap - evidence to scale

Updated on 2026-06-16. This is the execution roadmap from the current
Phase 7 state onward. The Phase 0-6 technical plan remains in
[`swarmos-roadmap.md`](swarmos-roadmap.md); the older Phase 7-30 draft in
that file is retained as historical context only.

## Decisions

1. SWARM keeps the big destination: autonomous coordination
   infrastructure for time-critical territorial events.
2. The first attack stays narrow: SWARM Patrol Cell for private
   high-value territories. Wildfire-risk patrol is the first beachhead,
   not the product boundary. The product is mobile patrol, verification,
   evidence and escalation across supported territorial event classes,
   not a fixed sensor network.
3. The roadmap must earn the later platform. Market learning, the flight
   path and pilot evidence move before city-scale software, citizen apps,
   payload logic and geographic expansion.
4. Claims stay typed. External material must say whether an outcome is
   validated in `sim`, `SITL`, `bench`, `supervised field`, `pilot` or
   `commercial production`.
5. YC Summer 2026 is not the target. The founder has Italian maturita in
   June 2026 and expects to start BIEF Bocconi in September 2026. A YC
   path now means a future batch / Early Decision unless a later decision
   explicitly changes that.
6. UAE, HAX, B4i and similar programs are options to validate, not
   automatic pivots, applications or relocation decisions.
7. The MVP does not require SWARM-owned fixed cameras, fixed thermal
   towers or proprietary ground sensors. It uses drones as mobile
   sensors plus lightweight cues: weather/fire-risk feeds, public
   satellite or hotspot signals where available, human reports,
   guard/owner call-ins, previous drone patrol observations and
   stale-sector routines.

## Founder calendar

| Window | Default focus | Output expected |
|---|---|---|
| 2026-05-22 to maturita | Phase 7 closure plus light customer discovery | Repeatable demo, clear wedge, no school-risk heroics |
| July-August 2026 | Evidence sprint | User learning, SITL/bench proof, pilot candidates, future-batch application pack |
| Before BIEF starts | Decision gate | Choose acceleration mode or semester mode from real signals |
| First BIEF semester | Semester mode unless a real trigger changes it | Fixed SWARM cadence, customer/pilot progress, no roadmap sprawl |

Acceleration mode requires a concrete trigger: an accepted program that
requires full-time founder attention, a credible pilot with a real buyer
path, or financing that changes the opportunity cost. Without one of
those triggers, start BIEF and run SWARM with a disciplined semester
cadence.

## Work lanes

Every phase from now until the first pilot has four lanes. A phase is not
done when only code moved.

| Lane | Question it answers |
|---|---|
| Product and autonomy | Can SWARM show mobile patrol, stale-sector coverage, verification and evidence clearly and repeatedly? |
| Real-world de-risk | Does the sim path survive SITL, bench and supervised hardware reality? |
| Market validation | Who has the urgent problem, who buys, and what pilot would they accept? |
| Capital and ecosystem | Which program, investor, advisor or geography accelerates evidence rather than distracts from it? |

## Phase map

| Phase | State | Focus | Gate |
|---|---|---|---|
| 0 | done | Repo discipline, security baseline, shared types | Baseline quality gates |
| 1 | done | SwarmOS sim kernel | State, events and actions work |
| 2 | done | Console operating shell | Operator surface works |
| 3 | done | Truth layer | No fake client truth |
| 4 | done | Persistence and audit | History survives |
| 5 | partial | MAVLink/PX4 adapter path | CI ready; SITL and hardware evidence still needed |
| 6 | done | Production OS foundations | Policy, auth, ops and security foundations |
| 7 | current | Investor-readable Patrol Cell sim demo | One-command wildfire proof plus coverage/evidence metrics |
| 8 | next | Patrol Cell wedge and customer validation | Learning memo plus pilot candidates |
| 9 | next | Flight-path and bench de-risk | SITL proof plus hardware bench plan/evidence |
| 10 | next | Summer evidence pack and founder decision | Future-batch YC pack plus BIEF mode decision |
| 11 | planned | Supervised field proof | First honest field bundle |
| 12 | planned | Pilot design and partner path | Pilot spec a buyer can accept |
| 13 | planned | Pilot-grade loop | Field workflow repeatable enough for pilot |
| 14 | planned | Capital, team and advisor proof | Raise/program choice based on evidence |
| 15 | post-proof | Product hardening from field data | Reliability backlog closes highest pilot risks |
| 16 | post-proof | Multi-territory and business layer | Second territory does not fork the product |
| 17 | post-proof | CV/data intelligence calibration | Models improve on owned evidence |
| 18 | post-proof | Multimodal and persistence hardware | Sensors/dock choices earn their cost |
| 19 | post-proof | Multi-cell coordination | Federation solves measured scale pain |
| 20 | post-proof | Handoffs and external interfaces | Users/partners get the right surface |
| 21 | post-proof | Compliance, privacy and resilience pack | Pilot can be audited and operated |
| 22 | capital | Seed close and core hires | Company can execute deployed pilots |
| 23 | scale | First deployed pilot cell | Partner deployment works in one target geography |
| 24 | scale | Regulatory and authority integration | Written operating path for target airspace/use case |
| 25 | scale | Dock/network infrastructure | Persistent coverage is physically maintainable |
| 26 | scale | Physical security and cyber hardening | Field system resists realistic failure/attack |
| 27 | scale | Local acceptance and trust | Community and customer trust loop exists |
| 28 | scale | Operations and support | Repeatable operating model |
| 29 | scale | Expansion inside chosen market | Second deployment repeats with less friction |
| 30 | scale | Geographic/platform expansion | New market or use case reuses the core |

## Phase 7 - Patrol Cell sim demo

Goal: turn the current simulated software into a proof a customer,
advisor or accelerator reviewer can understand in under two minutes.

Current verified status:
- 7.A scenario set exists.
- 7.B baseline autonomy exists.
- 7.C Console autonomy surface exists.
- 7.D opt-in CV baseline exists.
- 7.E one-command demo targets remain the immediate closure item.

Scope:
- Finish `make demo-wildfire-sim` first, reframed as a Patrol Cell
  proof: mobile drone patrol, coverage freshness, suspicious cue,
  verification mission, evidence packet and escalation. Intrusion and
  search remain valid extension demos because Patrol Cell is not limited
  to wildfire; wildfire-risk patrol is simply the first front door.
- Capture event-to-detection and detection-to-verification/escalation
  timings, command/event logs, failure cases and replay instructions.
- Show the no-fixed-sensor input model in the demo language: patrol
  observation, stale-sector routine, human/guard cue or public-risk cue
  can all create verification work. Do not imply SWARM installed a fixed
  camera network.
- Produce one short demo artifact and a truth table of what is sim,
  SITL, bench and field validated.
- Keep the Console as an observatory for autonomy decisions, not a
  cinematic pitch surface.

Gate:
- A clean checkout can run the wildfire demo by documented command.
- The demo shows sector freshness, patrol, cue/anomaly, verification,
  evidence, verify/escalate decision and operator-visible audit trail.
- No external pitch claims field or hardware validation from Phase 7.

## Phase 8 - Patrol Cell wedge and customer validation

Goal: learn whether the first wedge deserves the next technical risk.

Scope:
- Run 20 serious conversations before broadening the product:
  territory owners/managers, wildfire or land-risk experts, drone
  operators, insurance/risk contacts and possible pilot partners.
- Record problem frequency, current alternative, budget owner, false
  alarm cost, late-response cost, flight/operations objections and
  pilot acceptance criteria.
- Test the no-fixed-sensor wedge explicitly: would the buyer pay for
  seasonal mobile patrol coverage and evidence reports without installing
  cameras, towers or proprietary ground sensors? Which event classes make
  the service worth using weekly, not only during a wildfire scare?
- Record the useful patrol interval by buyer type: target coverage
  freshness, worst-sector staleness they can tolerate, high-risk windows,
  acceptable operator workload and what evidence would justify escalation.
- Produce a buyer map, competitor/alternative map and a one-page wedge
  memo. The memo must say why wildfire-risk coverage is first, why fixed
  sensors are not a prerequisite for the MVP, which additional event
  classes reuse the same Patrol Cell loop, and which adjacent use cases are
  explicitly deferred.
- Find at least two pilot candidates or two credible introductions to
  pilot decision makers. Interest must be written down honestly; do not
  manufacture LOIs.
- Run a light UAE lane only as discovery: targeted one-pager, ecosystem
  calls and buyer/pilot signal checks. No relocation decision here.

Gate:
- There is evidence from real conversations that sharpens product,
  pricing or pilot design.
- The next field proof is attached to a buyer hypothesis, not just a
  founder demo wish.

## Phase 9 - flight path and hardware de-risk

Goal: remove the risk that SWARM is only convincing inside its simulator.

Scope:
- Close the PX4/SITL evidence missing from Phase 5: mission dispatch,
  telemetry ingest, status/failure visibility and safety path.
- Write the minimum hardware bench bill of materials and test plan.
  Prefer the smallest supervised Patrol Cell proof that validates the
  adapter, mobile patrol loop, sector freshness tracking, verification
  capture and return/abort behavior without fixed sensor infrastructure.
- Validate bench connectivity, telemetry, mission upload/abort/return
  handling and evidence capture before seeking ambitious field autonomy.
- Prepare the first supervised field test with an explicit safety and
  regulatory checklist for the actual location, aircraft, pilot and
  flight profile.

Gate:
- SITL run is reproducible and logged.
- Hardware bench evidence exists, or the exact blocker and replacement
  plan are documented.
- The claim ladder moves only as far as the evidence moved.

## Phase 10 - summer evidence pack and founder decision

Goal: enter September with options grounded in evidence.

Scope:
- Build the application pack: one-line answer, problem/wedge answer,
  founder answer, technical proof answer, demo link, truth table and
  progress timeline.
- YC material targets a future batch / Early Decision, not Summer 2026.
  The application must explain current school status and the BIEF plan
  honestly.
- Prepare a short deck and one-pager for advisors, HAX-style hard-tech
  conversations, B4i evaluation and targeted investors. Reuse facts;
  change emphasis only where the audience changes.
- Decide before BIEF between:
  - acceleration mode, if a real trigger exists;
  - semester mode, with fixed weekly SWARM blocks and milestone review.

Gate:
- The founder can answer what SWARM is, who wants the first product,
  what has been built, what is not yet proven and what the next 30 days
  prove.
- September starts with a selected operating mode, not with every path
  half-open.

## Phase 11 - supervised field proof

Goal: collect the first honest physical evidence without pretending it is
a commercial pilot.

Scope:
- Run a small supervised field scenario attached to the Patrol Cell wedge:
  map sectors, patrol them, create a cue manually or from patrol
  observation, verify it and produce an evidence packet. Wildfire-risk is
  the preferred first cue; the procedure should not hard-code wildfire as
  the only possible event class.
- Capture telemetry, video/images if appropriate, autonomy logs, manual
  interventions, safety events and post-run lessons.
- Compare sim and field assumptions: coverage freshness, detection
  conditions, battery/time envelope, link quality, observer workload,
  false-positive sources and evidence quality.

Gate:
- A field evidence bundle can be reviewed by an expert.
- The roadmap changes if the physical proof contradicts the sim.

## Phase 12 - pilot design and partner path

Goal: turn learning into a pilot someone can say yes to.

Scope:
- Define pilot site, event classes, responsibilities, success metrics,
  supervision model, data handling, insurance/regulatory path and price
  hypothesis.
- Define the patrol service level before defining new hardware:
  priority sectors, target freshness interval, high-risk windows,
  supported event classes, cue sources, evidence packet format,
  escalation criteria and reporting cadence.
- Choose one first geography from evidence and feasibility. Italy/EU,
  UAE or another target is a decision here, not an inherited slogan.
- Keep public-safety or authority handoffs bounded unless a partner
  explicitly pulls them forward.

Gate:
- A pilot spec has a named target partner, owner of the problem and
  acceptance metrics.

## Phase 13 - pilot-grade loop

Goal: make the chosen pilot workflow repeatable.

Scope:
- Harden demo paths that the pilot actually uses: onboarding a
  territory, patrol plan, detection/verification path, operator audit,
  abort/return behavior and evidence export.
- Add only the minimum hardware, CV calibration and Console work needed
  for the pilot.
- Run rehearsal days and capture defects as field-priority backlog.

Gate:
- The same pilot workflow works across repeated runs with known
  supervision and recovery behavior.

## Phase 14 - capital, team and advisor proof

Goal: choose capital and people from evidence instead of from anxiety.

Scope:
- Use pilot proof to decide the primary capital path: YC future batch,
  hard-tech accelerator such as HAX, local Bocconi/B4i support, targeted
  angels/pre-seed investors or a strategic pilot-first path.
- Add advisors only for real gaps: flight/hardware safety, wildfire/land
  domain, buyer access or regulatory execution.
- Evaluate a cofounder as a high bar addition, not application theater.
- Incorporate and allocate budget when financing, contracts or liability
  make it useful.

Gate:
- There is a chosen capital path, a ranked team gap list and an
  evidence-backed use of funds.

## Phase 15 - field-driven reliability

Goal: harden what first evidence says matters.

Scope:
- Close reliability issues from Phase 11-13.
- Add scenario coverage from field failure modes.
- Establish field metrics and regression gates for autonomy, CV and
  adapter behavior.

Gate: pilot blockers are measured and trending down.

## Phase 16 - multi-territory and business layer

Goal: support a second territory without a product fork.

Scope:
- Multi-site configuration, territory onboarding and per-site policy.
- Billing/pricing primitives only after the buyer path is understood.
- Customer-facing reporting for pilot outcomes and operator evidence.

Gate: a second territory or second buyer type can be onboarded with the
same product core.

## Phase 17 - intelligence on owned data

Goal: improve detection and decision quality on evidence SWARM owns.

Scope:
- Field-data curation, CV calibration, tracking and model evaluation.
- Shadow mode for learned decisions under deterministic safety policy.
- Drift, calibration and explainability artifacts for review.

Gate: learned components beat the baseline on a held-out, relevant set
without weakening safety claims.

## Phase 18 - multimodal and persistent sensing

Goal: add sensors and persistence only where they change pilot economics
or reliability.

Scope:
- Evaluate thermal, fixed sensors, weather feeds and dock/power options.
- Fuse sources for wildfire verification when the validation data says
  the extra modality reduces delay or false positives.
- Keep payload-heavy active intervention out unless a partner and safety
  case pull it forward.

Gate: each added modality has a measured reason to exist.

## Phase 19 - multi-cell coordination

Goal: make federation solve scale pain rather than precede it.

Scope:
- Multi-cell coordination, load balancing and mission handoff.
- Mesh/fallback interfaces where real deployment constraints justify
  them.
- Chaos and backpressure tests around the chosen topology.

Gate: measured coverage or resilience improves versus one-cell operation.

## Phase 20 - external handoffs

Goal: expose the right surfaces to people outside the operator Console.

Scope:
- Customer notification and evidence views for the first product.
- Partner/API handoff for drone operators, land managers or responders.
- Citizen app or public alert surfaces only if the selected business path
  requires them.

Gate: each external surface has a user and a workflow already observed.

## Phase 21 - compliance, privacy and resilience pack

Goal: make the pilot system audit-ready for the chosen geography and use
case.

Scope:
- Data retention, privacy masking where needed, explainability and
  decision-log review.
- Operational resilience, incident response, backups and safety drills.
- Written regulatory and insurance checklist for the chosen deployment
  profile with counsel/expert review where required.

Gate: the pilot can survive buyer, safety and diligence questions without
inventing facts.

## Phase 22 - seed close and core hires

Goal: convert proof into execution capacity.

Scope:
- Close the financing path selected in Phase 14 when evidence supports
  it.
- Hire for bottlenecks: flight/hardware, CV/data, product/field ops and
  business/regulatory access.
- Set company structure, vesting, cap table hygiene and spend controls.

Gate: the team and budget can execute a deployed pilot without relying
on founder-only heroics.

## Phase 23 - first deployed pilot cell

Goal: run one partner deployment in the chosen market.

Scope:
- Deploy the smallest cell that exercises the paid/partner workflow.
- Track reliability, response time, false positives, operator burden and
  customer value.
- Maintain an honest safety and intervention ledger.

Gate: partner review confirms whether to expand, repeat or stop.

## Phase 24 - authority and regulatory integration

Goal: unlock the operating envelope required for the next deployment.

Scope:
- Work with the relevant aviation, safety, insurance and emergency
  stakeholders for the selected geography.
- Turn handoffs and flight permissions into written operating paths.
- Do not generalize one jurisdiction into another.

Gate: next deployment has a documented legal and operational path.

## Phase 25 - docking and network infrastructure

Goal: make persistent coverage physically maintainable.

Scope:
- Dock, power, weatherproofing, connectivity, maintenance and inventory.
- Placement models against actual territory and operating constraints.
- Vendor strategy that keeps SwarmOS independent of one aircraft.

Gate: persistence lowers cost or response time in field evidence.

## Phase 26 - physical security and cyber hardening

Goal: defend the deployed system against realistic field failure and
attack modes.

Scope:
- Link-loss, spoofing/jamming assumptions, command integrity, device
  lifecycle and red-team exercises appropriate to the deployment.
- Keep software supply-chain and cloud security gates alive from Phase
  0-6.

Gate: deployment has tested recovery paths and a tracked security risk
register.

## Phase 27 - local acceptance and trust

Goal: make expansion socially durable.

Scope:
- Transparent communication, customer/community feedback, incident
  communication and measurable trust signals.
- Product defaults that minimize unnecessary surveillance and overclaim.

Gate: expansion has stakeholder consent path, not just technical
permission.

## Phase 28 - operations and support

Goal: remove founder-only operation from repeat deployments.

Scope:
- Runbooks, support tiers, training, maintenance, monitoring and field
  incident review.
- Hiring and partner model for the chosen footprint.

Gate: operations can support more than one active deployment.

## Phase 29 - expansion inside the chosen market

Goal: prove repeatability before chasing geography.

Scope:
- Second and third deployments in the first strong market.
- Compare sales cycle, deployment cost, regulatory friction and field
  reliability against the first cell.

Gate: repeated deployments improve speed or unit economics.

## Phase 30 - geographic and platform expansion

Goal: expand only when the core repeats.

Scope:
- Choose the next geography from buyer pull, regulation, capital and
  operational leverage.
- Re-open adjacent use cases such as infrastructure sensing, search or
  public-safety response only where the coordination core transfers.
- Add APIs, SDKs or marketplace surfaces after partner demand exists.

Gate: expansion reuses the core product and does not hide a new startup
inside a roadmap item.

## Immediate queue

The next queue is deliberately short:

1. Close Phase 7.E around the wildfire one-command demo.
2. Write the Phase 7 truth table and short demo artifact.
3. Start Phase 8 customer discovery while Phase 9 SITL work is prepared.
4. Decide by the BIEF gate from signals, not from roadmap ambition.
