# ADR 0013 — Delegated mission authority and immutable decision records

**Status**: Accepted  
**Date**: 2026-08-25  
**Relates to**: [`0011-central-decision-authority.md`](0011-central-decision-authority.md), [`0012-partial-strength-composition-and-reinforcement.md`](0012-partial-strength-composition-and-reinforcement.md)

## Context

ADR-0011 makes SwarmOS the sole mission-level control plane. That establishes
where a decision is made, but not whether SwarmOS currently has authority from
the mission/risk owner to commit it.

The prior compatibility policy was binary at objective level. It did not make
launch, replacement, and reinforcement authority explicit, did not bind review
to an authenticated mission approver, and did not persist the complete facts
behind an execution-group composition. The single-executor path also bypassed
the objective approval seam.

Operator feedback supports progressive delegation with deterministic rationale.
It does not justify a pivot or a global four-mode autonomy system.

## Decision

> SwarmOS remains the sole mission-level control plane, but it may execute a
> decision only under authority delegated by the mission/risk owner.

### Mission-scoped authority

`MissionAuthorityGrant` is revisioned and scoped to one objective. It records
the holder, allowed approvers, a default effect, and typed delegated rules for
exactly three implemented decision kinds:

- `LAUNCH_COMPOSITION`;
- `REPLACE_FAILED_EXECUTOR`;
- `REINFORCE_CAPACITY`.

The grant is not enterprise RBAC and does not add product modes. Existing
policies remain compatibility projections:

- `AUTONOMOUS`: all three decision kinds are auto-authorized within hard
  constraints;
- `APPROVAL_REQUIRED`: initial launch requires review; replacement and
  reinforcement retain their existing automatic behavior within hard
  constraints.

### One decision pipeline

Initial composition, single-executor selection, replacement, and reinforcement
follow one boundary:

```text
recommend composition
→ evaluate hard constraints and exact authority revision
→ publish immutable MissionDecision
→ exact review when required
→ revalidate facts and authority
→ atomically claim capacity
→ dispatch physical missions
```

A recommendation cannot call an adapter, publish an award, or claim capacity.
An exact approval can commit only its still-current decision. Reject commits no
physical effect. Override creates a new decision with
`supersedes_decision_id`; the original is never mutated.

### Immutable audit records

Every `MissionDecision` records:

- objective and revision;
- decision kind;
- requirement and constraint snapshots;
- every candidate's capabilities, availability, score, and exclusion reasons;
- selected role assignments;
- full versus partial requirement satisfaction;
- authority grant and revision, verdict, and deterministic reasons;
- replacement/supersession provenance.

Grant revisions, decisions, and authenticated reviews are append-only in
persistence. Replayed IDs cannot update prior payloads. UI rationale is rendered
from these records; no LLM generates operational truth.

### Identity and safety boundaries

The review actor is derived from the authenticated JWT principal. Request bodies
cannot supply or spoof it. Explicit grants accept review only from the holder or
a listed approver.

Hard site constraints and delegated-authority constraints are different:

- geofence and altitude limits are non-waivable and produce `DENIED`;
- grant-envelope limits such as allowed executors or maximum group size may
  move an otherwise safe decision to review;
- both are snapshotted and re-evaluated at the claim boundary.

### Objective truth is separate from execution truth

`ExecutionGroup.COMPLETED` and executor `DONE` mean physical execution ended.
They do not directly set `ObjectiveStatus.SATISFIED`. SwarmOS publishes a
separate objective-state frame; absent semantic acceptance evidence, a completed
execution leaves the objective `UNRESOLVED`.

## Consequences

- Progressive delegation is explicit and testable without additional modes.
- Single- and multi-executor recommendations share the authority boundary.
- Replacement and reinforcement explain which capability was lost/restored and
  under which rule they proceeded.
- Approval cannot legalize an unsafe mission or a stale grant revision.
- The Console can show exact approve/reject controls and deterministic reasons.
- Cancellation of an already-active objective and an automatic trust-promotion
  model remain future decisions; neither is implied by this ADR.
