# Mission-authority control-plane replay

**Recorded:** 2026-08-25

**Surface:** development-only `/dev/replay?take=b`

**Artifact:** `frontend/lib/fixtures/mission-authority-replay.json`

This replay closes the demo boundary in ADR-0013: authority rationale is read
from control-plane records, not authored as frontend copy.

## Provenance

`scripts/record_mission_authority_replay.py` runs the real
`ExecutionGroupOrchestrator` with `InMemoryBus`. Fake physical adapters only
emit executor progress so the group can fail, replace a member, and complete.
They do not construct any authority record.

The committed artifact contains the exact bus payloads for:

1. `D1 LAUNCH_COMPOSITION` — `review_required`;
2. the append-only `approve` review by `risk-owner`;
3. objective state `waiting_for_approval → active`;
4. `D2 REPLACE_FAILED_EXECUTOR` — `auto_authorized` under the exact delegated
   replacement rule;
5. objective state `active → unresolved` after physical completion without
   semantic acceptance evidence.

The scenario IDs, roles, and child mission IDs match take B. Replay timing is
scripted around those immutable records; the records themselves are consumed
unchanged.

## Reproduce

```bash
uv run python scripts/record_mission_authority_replay.py
cd frontend
pnpm test -- components/console/__tests__/take-invariance.test.ts \
  components/console/__tests__/authority-panel.test.tsx
```

Any regenerated artifact must retain the D1/review/D2 sequence and pass the
invariance tests before it replaces the committed recording.

## Claim boundary

This is an in-process control-plane recording, not PX4 SITL, hardware, field,
or customer validation. It proves that the replay renders records produced by
the implemented authority pipeline; it does not prove operator acceptance or
physical fault tolerance.
