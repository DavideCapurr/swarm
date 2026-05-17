# Redis — SWARM OS transport bus

Redis is used as the day-1 pub/sub transport for SWARM OS topics. The default
docker-compose service runs `redis:7-alpine` with no custom config; that
plaintext setup is **dev/demo only**.

## Secure transport gate

Phase 5 keeps MAVLink in-process for the supported demo path, but Phase 6 must
not allow production or out-of-process adapter traffic on plaintext Redis.
The bus layer now enforces that boundary:

- `SWARM_ENV=dev` and `SWARM_REQUIRE_SECURE_BUS=0`: local `redis://` and the
  in-memory fallback are allowed for tests/dev.
- `SWARM_ENV=prod` or `SWARM_REQUIRE_SECURE_BUS=1`: startup fails closed unless
  `REDIS_URL` uses `rediss://` and all three mTLS files exist:
  `REDIS_TLS_CA_CERTS`, `REDIS_TLS_CERTFILE`, `REDIS_TLS_KEYFILE`.
- When secure bus mode is required, Redis connection failure is fatal; the
  backend and standalone adapter runners do not fall back to `InMemoryBus`.

Example production shape:

```bash
SWARM_ENV=prod
REDIS_URL=rediss://redis.internal.example:6379/0
REDIS_TLS_CA_CERTS=/run/secrets/redis-ca.pem
REDIS_TLS_CERTFILE=/run/secrets/swarm-client.pem
REDIS_TLS_KEYFILE=/run/secrets/swarm-client.key
```

The local Compose Redis image is intentionally not a production mTLS service.
Use managed Redis with TLS client certificates or a hardened Redis deployment
with `tls-auth-clients yes`.

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
