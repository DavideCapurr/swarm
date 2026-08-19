# SwarmOS decision capability audit — 2026-08-19

This audit exists to enforce the product invariant:

> **SwarmOS decides. Physical agents execute.**

It audits control logic, not what the Console is capable of drawing. `Take C`
is an acceptance scenario only and is not evidence for a capability unless the
state it renders was produced by the planner/orchestrator.

## Architecture traced

The relevant path on `main` before this change was:

```text
Anomaly / MissionTask
  -> Orchestrator._auction_and_dispatch
     -> idle central allocator
     -> special continuous-PATROL -> single VERIFY diversion fallback

COOPERATIVE_VERIFY / COVER objective
  -> ExecutionGroupOrchestrator.dispatch_execution_group
     -> role plans
     -> _select_group_candidate
        -> _eligible_fleet (idle-only; rejects _busy/current_mission_id)
     -> ExecutionGroup
     -> child awards / adapter execution
     -> group progress
        -> failure -> _replace_failed_member (idle-only)
     -> periodic review_reinforcements
        -> shortfall_reinforcement_policy
        -> second ExecutionGroup (idle-only)
```

The important boundary was real and confirmed: the single-executor VERIFY path
could divert an airborne PATROL owner, but `ExecutionGroup` composition could
not consume that same committed capacity because `_eligible_fleet()` rejected
`_busy` and `current_mission_id != None`.

This branch adds:

```text
ObjectiveDemand
  -> evaluate_capacity
       idle + explicitly preemptible committed capacity
       donor priority + donor minimum-capacity floor
  -> AdaptiveExecutionGroupOrchestrator
       composition / reinforcement / replacement
       -> diversion provenance
       -> donor COVER/PATROL recomputation
       -> periodic reconciliation
```

The bus-backed runtime now derives from the adaptive orchestrator. The alarm
policy is separately reusable: an `Anomaly` is external world truth; SwarmOS
derives the response objective and demand from it.

## Capability matrix

| # | Capability | Before this branch | After this branch | Evidence / boundary |
|---|---|---|---|---|
| 1 | Allocate an idle executor to an objective | **IMPLEMENTED** | **IMPLEMENTED** | `service.py::_auction_and_dispatch`, allocator tests |
| 2 | Allocate several executors to one objective | **IMPLEMENTED** | **IMPLEMENTED** | `execution_groups.py::_form_and_dispatch_group` |
| 3 | Compose an ExecutionGroup / swarm | **IMPLEMENTED** | **IMPLEMENTED** | ExecutionGroup tests + prior PX4 SITL evidence |
| 4 | Compose a swarm when insufficient idle capacity exists | **PARTIALLY IMPLEMENTED** (partial idle strength only) | **IMPLEMENTED** for idle + preemptible capacity | adaptive capacity tests |
| 5 | Consider already-committed but preemptible capacity | **PARTIALLY IMPLEMENTED** (special single VERIFY diversion) | **IMPLEMENTED** | `capacity.py` |
| 6 | Divert an airborne executor from another mission | **IMPLEMENTED** only for single VERIFY/PATROL path | **IMPLEMENTED** through reusable capacity policy for adaptive groups; legacy single path still exists | `test_diversion_truth.py`, adaptive tests |
| 7 | Divert multiple airborne executors | **NOT IMPLEMENTED** | **IMPLEMENTED** with donor-floor accounting across a composition | `planned_preemptions` + adaptive multi-agent test |
| 8 | Divert an airborne executor directly into an ExecutionGroup | **NOT IMPLEMENTED** | **IMPLEMENTED** | `AdaptiveExecutionGroupOrchestrator._select_group_candidate` |
| 9 | Rebalance the mission it was taken from | **NOT IMPLEMENTED** | **IMPLEMENTED** for COVER and adaptive continuous PATROL | `_recompute_cover_group`, `_recompute_continuous_patrol` |
| 10 | Detect an under-strength swarm | **IMPLEMENTED** | **IMPLEMENTED** | requested vs committed members |
| 11 | Decide whether reinforcement is required | **IMPLEMENTED** | **IMPLEMENTED** | `shortfall_reinforcement_policy` |
| 12 | Find reinforcement capacity | **PARTIALLY IMPLEMENTED** (idle only) | **IMPLEMENTED** for idle + preemptible capacity | adaptive `_observe_objective` |
| 13 | Add a second swarm to an existing objective | **IMPLEMENTED** | **IMPLEMENTED** | `reinforces_group_id` + tests |
| 14 | Coordinate several swarms against one objective | **PARTIALLY IMPLEMENTED** | **PARTIALLY IMPLEMENTED** | first-class objective/group relationship exists; full physical cross-group disposition retask is not yet wired |
| 15 | Recompute formation/disposition when composition changes | **DEMO-ONLY** in Take C | **PARTIALLY IMPLEMENTED** | `core/swarm_core/disposition.py` derives geometry from active roles; physical retask of already-on-station members remains open |
| 16 | Detect executor failure | **IMPLEMENTED** | **IMPLEMENTED** | group progress FAILED / executor exception |
| 17 | Replace a failed executor | **IMPLEMENTED** | **IMPLEMENTED** with adaptive candidate policy available | `_replace_failed_member` + existing tests |
| 18 | Preserve role/replacement provenance | **IMPLEMENTED** | **IMPLEMENTED** + diversion provenance | `role`, `replaces_agent_id`, `diverted_from_*` |
| 19 | Continue unrelated missions during adaptation | **IMPLEMENTED** | **IMPLEMENTED** | concurrent task model; adaptive donor survivor test |
| 20 | Return released capacity to available pool | **IMPLEMENTED** for normal task cleanup | **IMPLEMENTED** for tracked commitments; recovery of all arbitrary donor objectives is still policy-specific | tracking cleanup test |
| 21 | Recompute allocations after an objective completes | **PARTIALLY IMPLEMENTED** | **PARTIALLY IMPLEMENTED** | capacity becomes eligible and patrol/reinforcement loops re-evaluate; no global all-objective optimizer |
| 22 | Resolve competing objectives using explicit priorities/policies | **PARTIALLY IMPLEMENTED** | **IMPLEMENTED for preemption decisions; PARTIAL globally** | strict higher-priority preemption + donor floors; no general utility solver |

## The corrected diversion claim

The current `docs/STATUS.md` row saying:

> `Same-aircraft preemption/diversion | not implemented / not claimed`

is too broad for the code already on `main`.

The exact boundary is:

- **same-aircraft diversion from continuous PATROL to a single-executor VERIFY:** IMPLEMENTED and covered by `test_diversion_truth.py`;
- **preemption/diversion directly into ExecutionGroup composition:** NOT IMPLEMENTED on pre-change `main`; IMPLEMENTED in this branch through `capacity.py` + `AdaptiveExecutionGroupOrchestrator`;
- **general optimal preemption across arbitrary mission types:** NOT CLAIMED.

Until `docs/STATUS.md` is edited, this audit is the more precise statement and
the stale row must not be quoted externally.

## What is automatic on this branch

- alarm confidence -> single- vs multi-executor objective demand;
- idle-vs-preemptible capacity selection;
- preemption eligibility from explicit policy;
- donor minimum-capacity protection;
- deterministic candidate ranking from distance/battery/priority;
- multi-executor diversion into a group;
- under-strength detection;
- reinforcement decision and second-group provenance;
- replacement candidate selection through the same group candidate path;
- COVER/PATROL recomputation after capacity loss;
- role, replacement, reinforcement and diversion provenance;
- capacity release when execution tasks complete;
- disposition geometry as a pure function of active roles.

## What remains intentionally external / scripted

A deterministic simulation or acceptance scenario may still specify facts about
the world, for example:

- fleet size and initial availability;
- a coverage objective and its explicit minimum/desired policy;
- an alarm appearing at a location with a confidence/severity;
- an executor becoming unavailable or failing;
- capacity becoming available later;
- deterministic clock/seed.

It must not specify:

- aircraft selected for response;
- which sweep aircraft are diverted;
- group/swarm membership;
- reinforcement member identity;
- replacement identity;
- a formation transition;
- a statement that reinforcement is required.

Those are SwarmOS outputs.

## Remaining gaps

1. `compute_disposition()` is production-side deterministic geometry, but
   already-on-station physical children are not yet retasked when combined
   membership changes. A replay may use the computed geometry, but that is not
   yet a field/SITL proof of formation reconfiguration.
2. The system has explicit priority/preemption policy, not a global utility
   optimizer. This is deliberate for the current product proof.
3. The new adaptive preemption/reconciliation path is test/simulator logic until
   separately run through PX4 SITL. Existing phase 11/12 SITL evidence remains
   valid but does not automatically validate these new branches.
4. No physical-aircraft proof is added by this change.
