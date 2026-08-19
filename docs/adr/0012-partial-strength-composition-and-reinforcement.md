# ADR 0012 — Partial-strength composition and swarm reinforcement

**Status**: Accepted
**Date**: 2026-08-19
**Relates to**: [`0011-central-decision-authority.md`](0011-central-decision-authority.md)

## Context

ADR-0011 established SwarmOS as the sole mission-level decision authority and
described `ExecutionGroup` formation as fail-closed: SwarmOS planned the full
required group, and if any single role could not be filled the group was marked
`FAILED` with `INSUFFICIENT_ELIGIBLE_CAPACITY` and zero child missions launched.

That contract had two consequences the runtime could not express:

1. **An objective SwarmOS could partly serve was refused entirely.** With two
   eligible executors and a three-role objective, nothing flew. Partial
   verification coverage is worth more than none, and refusing it discards
   capability the fleet actually has.
2. **A running objective could never gain strength.** The only path that added a
   member to an existing group was `_replace_failed_member` — a 1:1 repair
   carrying `replaces_agent_id`, bounded by `max_group_replacements_per_role`.
   When executors returned to eligibility, SwarmOS had no way to commit them to
   an objective already in progress.

Both are composition-contract limits, not decision-authority limits. Nothing
about relaxing them requires moving judgement out of SwarmOS.

## Decision

### 1. Composition is partial-strength; refusal means *no* role is fillable

SwarmOS plans every role, then dispatches the roles it can fill. A role with no
eligible executor is recorded as unfilled and the group proceeds without it.

`FAILED` / `INSUFFICIENT_ELIGIBLE_CAPACITY` with zero child missions is retained
exactly, but now applies only when **no role at all** can be filled.

Shortfall carries no new field. `requested_members` remains the strength the
objective asked for and `members` is what was committed, so
`len(members) < requested_members` is the shortfall, already readable by every
existing consumer of the `swarm:execution-groups` frame.

A partially composed group is `ACTIVE`, not `DEGRADED`. `DEGRADED` keeps its
existing meaning — a member failed while the group was running.

Group completion is judged over the roles the group actually dispatched. A group
that composed two of three roles completes when both of those complete. It never
claims to have satisfied a role it never filled; the counts on the frame state
the difference.

**This supersedes the ADR-0011 section "Formation is fail-closed", specifically:**

> SwarmOS plans the full required group before dispatching any child mission. If
> there are not enough eligible agents, the group is marked `FAILED` with
> `INSUFFICIENT_ELIGIBLE_CAPACITY` and zero partial child missions are launched.

Everything else in that section is unchanged: busy, mission-holding,
below-battery and otherwise unavailable agents remain ineligible, and one
physical agent still occupies at most one role in the same group.

### 2. Reinforcement adds a swarm, never members

When executors become eligible again and the policy calls for it, SwarmOS
composes and dispatches a **second `ExecutionGroup`** against the same objective
and the same anomaly. It does not append members to the running group.

The swarm is the unit of command. Reinforcement is therefore another unit, with
its own composition, its own lifecycle and its own `requested_members` — the
strength *that* group was asked to add. The originating group's membership is
left untouched, so its frame history stays a truthful record of what it
committed.

A reinforcing group never reinforces in turn: only originating groups carry an
objective's reinforcement record.

### 3. The relationship is published, never inferred

`ExecutionGroup` gains:

```python
reinforces_group_id: str | None = None
```

Set on the reinforcing group to the id of the group it reinforces; `None` on
originating groups. This follows the idiom `ExecutionGroupMember.replaces_agent_id`
already establishes — provenance is a field the runtime publishes.

A downstream reader must not have to infer the relationship from a shared
`anomaly_id` or `objective_mission_id`. Two groups can share an objective for
reasons other than reinforcement, and a reader that guesses would be inventing
operational truth.

### 4. Reinforcement judgement sits behind a policy seam

The mechanism (compose, dispatch, publish) is separated from the judgement (does
this objective need reinforcing, and at what strength).

The judgement is a **pure function** with an explicit input and an explicit
output, called by the orchestration path rather than written as a condition
inside it:

```python
def shortfall_reinforcement_policy(
    observation: ReinforcementObservation,
) -> ReinforcementDecision
```

`ReinforcementObservation` carries `objective_kind`, `objective_state`,
`requested_members`, `committed_members`, `eligible_agents`,
`reinforcements_dispatched` and `max_reinforcements`.
`ReinforcementDecision` carries `reinforce`, `strength` and a named `reason`
(`GROUP_NOT_RUNNING`, `REINFORCEMENT_LIMIT`, `AT_REQUESTED_STRENGTH`,
`NO_ELIGIBLE_CAPACITY`, `STRENGTH_SHORTFALL`).

The orchestrator holds the policy as a replaceable field
(`ExecutionGroupOrchestrator.reinforcement_policy`), typed
`ReinforcementPolicy = Callable[[ReinforcementObservation], ReinforcementDecision]`.

The default rule is deliberately simple and hand-written: reinforce a running
objective that is below its requested strength, at a strength clamped to
currently eligible capacity, bounded by `max_reinforcements_per_objective`.

**The seam is the decision, not the rule.** SWARM's decision layer is intended to
stop being hand-coded case by case. A condition tangled into dispatch cannot
later be replaced; a policy with an explicit input and output can. No model is
introduced here and none is implied. "No autonomy that isn't verifiable" applies
in full: the policy is a deterministic pure function with unit tests over each
branch, and the mechanism it gates publishes every decision as a structured
frame.

### 5. Replacement is untouched

`_replace_failed_member`, `max_group_replacements_per_role`,
`ROLE_FAILED:<role>:REPLACEMENT_LIMIT`, `ROLE_FAILED:<role>:NO_REPLACEMENT`, the
`REPLACED` member state and `replaces_agent_id` all keep their exact prior
behaviour and cap.

Replacement and reinforcement are distinct mechanisms and neither calls the
other:

- **Replacement** repairs a role that failed inside one swarm. Bounded per role.
- **Reinforcement** adds a swarm to an objective that never reached strength.
  Bounded per objective.

Reinforcement only fills roles the objective asked for and never got. It does
not re-fill a role lost to the replacement cap; that remains replacement's
bounded, fail-closed concern.

## Boundary with ADR-0011 — decision authority is unchanged

Every invariant in ADR-0011 holds. Specifically:

- Reinforcement is a **SwarmOS decision**. The trigger is a central, time-based
  review loop owned by the orchestrator (`_reinforcement_loop`), which calls
  `review_reinforcements()`.
- No agent, adapter or aircraft may request reinforcement, trigger it, or elect
  itself into it. Nothing agent-originated appears in `ReinforcementObservation`
  as authority: fleet state remains semi-trusted operational input subject to the
  same eligibility, range and freshness checks, exactly as ADR-0011 requires.
- The policy seam is a replaceable pure function **inside SwarmOS**. It is not
  onboard intelligence and creates no subordinate mission-level brain. A
  reinforcing group is composed centrally, its roles assigned centrally, and its
  members selected by the same central allocator.
- The parent objective still never reaches a physical agent. A reinforcing group
  decomposes into child missions the same way, and physical adapters still fail
  closed on an orchestration-only parent.
- Partial composition does not widen any agent's authority. It narrows what
  SwarmOS refuses, not who decides.

## Consequences

- SwarmOS serves what the fleet can actually do instead of refusing an objective
  it could partly meet.
- Under-strength operation is visible rather than hidden: the frame states
  requested versus committed, so the Console can render honest shortfall without
  deriving anything client-side.
- Objective strength becomes recoverable over time without disturbing a running
  swarm's composition or its published history.
- Two groups may now be live against one objective. Consumers that assumed one
  group per objective must read `reinforces_group_id` rather than group by
  `anomaly_id`.
- The reinforcement judgement can be changed, tuned or replaced without touching
  compose/dispatch/publish.
- A partially composed group can complete while the objective was never served
  at full strength. That is the honest outcome and the counts say so; it is not
  reported as full satisfaction.

## Validation boundary

Unit/integration tests prove: partial composition dispatches the fillable roles
and leaves `requested_members` intact; a fully unfillable objective still fails
closed with zero child missions; each policy branch returns its named reason and
clamps strength to eligible capacity; a reinforcing group is dispatched as a
separate group carrying `reinforces_group_id`, the same objective and the same
anomaly; a declining policy withholds reinforcement while capacity exists; and
the per-role replacement cap is unchanged.

Evidence is recorded in [`../STATUS.md`](../STATUS.md). This ADR makes no
hardware or SITL claim: the behaviour above is validated in the orchestrator test
suite only, and no physical-aircraft or PX4 SITL reinforcement run has been
observed.
