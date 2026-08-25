# WebSocket Contract (`/ws/telemetry`)

## Connection
- Endpoint: `ws(s)://<host>/ws/telemetry`
- Authentication: access token via query string `?token=<jwt>`.
- Origin policy: backend origin allowlist is enforced before acceptance.

## Envelope
All frames are JSON objects with shape:

```json
{ "kind": "<event-kind>", "data": { "...payload..." } }
```

## Event kinds
Derived from `frontend/lib/ws.ts` union:

- `session`
- `unit`
- `dock`
- `sector`
- `awareness`
- `mission`
- `anomaly_view`
- `event`
- `operator`
- `stream`
- `allocation`
- `execution_group`
- `mission_runtime`
- `payload`
- `mission_authority_grant`
- `mission_decision`
- `mission_decision_review`
- `objective_state`

Mission-authority frames are server truth. In particular:

- `mission_decision` is immutable and includes the exact objective revision,
  candidate assessments, selected assignments, constraint snapshot, grant
  revision, and authority verdict;
- `mission_decision_review` carries the authenticated server-derived actor;
- `objective_state` is semantic objective truth and must not be inferred from
  `execution_group.state` or a child mission's terminal phase.

## Compatibility note
- Consumers should ignore unknown fields for forward compatibility.
- `kind` values are contract-critical and versioned through frontend/backend changes.
