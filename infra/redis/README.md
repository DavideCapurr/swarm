# Redis — SWARM OS transport bus

Redis is used as the day-1 pub/sub transport for SWARM OS topics. The default
docker-compose service runs `redis:7-alpine` with no custom config — defaults
are sufficient for the demo.

## Topic namespacing

All SWARM topics live under `swarm:*`:

| Topic pattern                        | Direction                  |
|--------------------------------------|----------------------------|
| `swarm:telemetry:{agent_id}`         | adapter → backend          |
| `swarm:fleet:state`                  | orchestrator → backend     |
| `swarm:anomalies`                    | perception → orchestrator  |
| `swarm:missions:announce`            | orchestrator → adapters    |
| `swarm:missions:bid:{mission_id}`    | adapters → orchestrator    |
| `swarm:missions:award`               | orchestrator → adapters    |
| `swarm:missions:progress:{id}`       | adapter → orchestrator/backend |

## Migration path

The transport is encapsulated in `orchestrator/swarm_orchestrator/bus.py`.
Swapping Redis for NATS / MQTT / DDS is a single-module change.

## Production sizing

For commit 1 the in-process default is sufficient. At deployment scale, consider:
- managed Redis (AWS ElastiCache, Redis Cloud) with cluster mode for fan-out;
- `CONFIG SET maxmemory-policy allkeys-lru` (pub/sub doesn't persist anyway);
- separate Redis instance per environment.
