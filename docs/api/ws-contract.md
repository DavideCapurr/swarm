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

## Compatibility note
- Consumers should ignore unknown fields for forward compatibility.
- `kind` values are contract-critical and versioned through frontend/backend changes.
