# SwarmOS deployment guide (Phase 6.E)

This document is the canonical guide for taking SwarmOS from
**code-complete** to **running on a real cluster** or **on a single-node
bench host**. It covers:

1. The two supported deploy modes — Kubernetes (Helm) and
   `docker-compose.prod.yml` single-node.
2. Image build + signing pipeline.
3. Release strategy (canary via Helm rolling update).
4. Smoke tests and rollback.

The Phase 6.E work shipped here is **code-complete**. Real provisioning
(GHCR push credentials, Sigstore identity, DNS + TLS cert, off-site
backup destination) is documented in
[`drone-day-checklist.md`](drone-day-checklist.md) §2.E.

> Audience: SRE / on-call deploying SwarmOS. If you've never read
> [`../CLAUDE.md`](../../CLAUDE.md) or [`../STATUS.md`](../STATUS.md),
> start there — this guide assumes you know what "site" means and that
> the truth always lives in SwarmOS, not the Console.

---

## 0. Topology

```
              ┌──────────────────────────────┐
              │    Browser / Console UI      │
              └──────────────┬───────────────┘
                          HTTPS │ (TLS 1.2/1.3)
                                ▼
              ┌──────────────────────────────┐
              │  Ingress (nginx + cert-mgr)  │  Kubernetes
              │  OR proxy + certbot (compose)│  OR compose-prod
              └──────────┬─────────┬─────────┘
                /api,/ws/│         │ /
                         ▼         ▼
                ┌────────────┐  ┌──────────────┐
                │  Backend   │  │  Frontend    │
                │ (FastAPI,  │  │  (Next.js    │
                │  port 8765)│  │  standalone, │
                └────┬───────┘  │  port 3000)  │
                     │          └──────────────┘
            ┌────────┴────────┐
            ▼                 ▼
      ┌────────────┐    ┌──────────┐
      │  Postgres  │    │  Redis   │
      │ (Timescale)│    │  (bus)   │
      └────────────┘    └──────────┘
            ▲
            │ pg_dump | gpg
            │
      ┌────────────┐
      │  Backup    │  CronJob (k8s) / sidecar (compose)
      │  (alpine)  │  → /backups/swarm-YYYYMMDD-HHMMSSZ.sql.gpg
      └────────────┘
```

Both deploy modes use **nginx** as TLS terminator and reverse proxy.
Kubernetes uses `ingress-nginx`; compose-prod uses an `nginx:1.27-alpine`
container with a certbot sidecar. The runtime behavior is identical — same
security headers, same WS upgrade handling, same `/api`/`/ws/` split.

---

## 1. Image build + signing

Image build is automated by
[`.github/workflows/image-build.yml`](../../.github/workflows/image-build.yml).
On every branch/PR push it builds the backend + frontend + backup
Dockerfiles to verify they compile; on `v*` tag push it builds and pushes
to GHCR:

```
ghcr.io/<owner>/swarmos-backend:<tag>
ghcr.io/<owner>/swarmos-frontend:<tag>
ghcr.io/<owner>/swarmos-backup:<tag>
```

Each image is scanned with Trivy at build time (HIGH/CRITICAL blocking)
and gets a CycloneDX SBOM uploaded as a workflow artifact.

### Signing

The follow-up workflow
[`.github/workflows/image-sign.yml`](../../.github/workflows/image-sign.yml)
runs after `image-build` succeeds on a tag and signs each image with
`cosign sign --yes` (keyless OIDC). Verification:

```bash
COSIGN_EXPERIMENTAL=1 cosign verify \
  ghcr.io/<owner>/swarmos-backend@<digest> \
  --certificate-identity-regexp '^https://github.com/<owner>/swarm/.+$' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

Drone-day §2.E binds the real Sigstore identity. Until then, on branch
pushes the sign workflow is a no-op (no tag, no sign).

### Local image builds

```bash
make docker-build   # builds backend + frontend + backup with :dev tags
```

The Dockerfiles use multi-stage builds; the final stage runs as
non-root (uid 10001 for backend, uid 1001 for frontend) with a
read-only-rootfs-compatible layout. Run with `--read-only --tmpfs /tmp`
to validate before deploy.

---

## 2. Kubernetes (Helm) — the supported production path

### 2.1 Prerequisites

The cluster must have:

- [`ingress-nginx`](https://kubernetes.github.io/ingress-nginx/)
  controller installed.
- [`cert-manager`](https://cert-manager.io/) v1.14+. Apply the two
  ClusterIssuers under
  [`infra/cert-manager/`](../../infra/cert-manager/):

  ```bash
  kubectl apply -f infra/cert-manager/issuer-letsencrypt-staging.yaml
  kubectl apply -f infra/cert-manager/issuer-letsencrypt-prod.yaml
  ```

  Edit the email + ACME endpoint per the [Let's Encrypt rate limits doc](https://letsencrypt.org/docs/rate-limits/);
  start with staging, swap to prod when the issuance flow works end-to-end.

- A CNI that enforces `NetworkPolicy` (Calico, Cilium, Antrea,
  Weave-net 2.6+).
- A `StorageClass` that supports `ReadWriteOnce` for the backup PVC.
- For Prometheus scrape: kube-prometheus-stack OR a plain Prometheus
  with the `swarmos-backend` Service added to its `static_configs`.

### 2.2 Secrets

The chart deliberately does NOT fold production secrets into Helm
values. Choose one of:

- [`sealed-secrets`](https://github.com/bitnami-labs/sealed-secrets) +
  the example template at
  [`infra/k8s/secret.example.yaml`](../../infra/k8s/secret.example.yaml).
- [External Secrets Operator](https://external-secrets.io/) pointing at
  AWS Secrets Manager / Vault / GCP Secret Manager.
- Kustomize with SOPS-encrypted overlays.

The Secrets the backend expects (all under `Secret/swarmos`):

| Key                            | Source                                                       |
|--------------------------------|--------------------------------------------------------------|
| `SWARM_JWT_SECRET`             | `openssl rand -hex 32` (drone-day §2.C)                      |
| `DATABASE_URL`                 | `postgresql+asyncpg://...` for the cluster Postgres          |
| `REDIS_URL`                    | `rediss://...` (mTLS for prod — drone-day §2.E)              |
| `SWARM_ALLOWED_ORIGINS`        | `https://<ingress-host>`                                     |
| `SWARM_SITE_ID`                | matches `siteId` in Helm values                              |
| (optional) `SWARM_METRICS_IP_ALLOWLIST` | CIDR of the Prometheus pod IP range                  |

A second Secret `Secret/swarmos-operators` holds `operators.yaml` (the
role roster — see [`../security/auth.md`](../security/auth.md)). A third
`Secret/swarmos-backup` holds backup credentials.

### 2.3 Install

```bash
helm upgrade --install swarmos infra/helm/swarmos \
  -f infra/helm/swarmos/values-vineyard-01.yaml \
  --namespace swarmos \
  --create-namespace \
  --set image.backend.digest=sha256:$(cat _digests/swarmos-backend.digest) \
  --set image.frontend.digest=sha256:$(cat _digests/swarmos-frontend.digest) \
  --set image.backup.digest=sha256:$(cat _digests/swarmos-backup.digest)
```

The digests come from `image-build.yml`'s upload-artifact step. Pinning
by digest (rather than tag) ensures the rollout can't drift if the tag
is later overwritten.

After the chart is applied, run the migration job manually (see
[`migrations.md`](migrations.md)):

```bash
kubectl run swarmos-migrate \
  --image=ghcr.io/<owner>/swarmos-backend:<tag> \
  --restart=Never \
  --rm -it \
  --command -- /opt/venv/bin/alembic upgrade head
```

### 2.4 Smoke tests

After install, verify:

```bash
# Readiness probe should converge in <60s
kubectl -n swarmos rollout status deploy/swarmos-backend
kubectl -n swarmos rollout status deploy/swarmos-frontend

# /ready must be 200 with every subsystem ok
kubectl -n swarmos exec deploy/swarmos-backend -- \
  wget -qO- http://127.0.0.1:8765/ready

# Ingress TLS valid
curl -fsS https://swarmos.<host>/api/health

# WebSocket upgrades
echo -e "GET /ws/telemetry HTTP/1.1\r\nHost: swarmos.<host>\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n" | openssl s_client -connect swarmos.<host>:443 -quiet 2>/dev/null | head -10
```

---

## 3. Single-node (compose-prod) — the bench path

```bash
cp .env.example .env
# Fill in:
#   TLS_SERVER_NAME=swarmos.bench.example.com
#   TLS_EMAIL=ops@example.com
#   POSTGRES_PASSWORD=$(openssl rand -hex 24)
#   REDIS_PASSWORD=$(openssl rand -hex 24)
#   SWARM_JWT_SECRET=$(openssl rand -hex 32)
#   BACKUP_GPG_RECIPIENT=<your-key-fingerprint>
#   Redis TLS files:
#     infra/config/redis/ca.crt
#     infra/config/redis/server.crt
#     infra/config/redis/server.key
#     infra/config/redis/client.crt
#     infra/config/redis/client.key

docker compose -f docker-compose.prod.yml --profile letsencrypt --profile backup up -d
```

For a quick dry-run without ACME:

```bash
TLS_MODE=self-signed TLS_SERVER_NAME=localhost \
  docker compose -f docker-compose.prod.yml up -d postgres redis backend frontend proxy

curl -k https://localhost/api/health
curl -k https://localhost/ready
```

The same image digests built by `image-build.yml` work here — set
`SWARMOS_BACKEND_IMAGE` / `SWARMOS_FRONTEND_IMAGE` in `.env` to pull
from GHCR instead of building locally.

Keep `infra/config/sites`, `infra/config/operators.yaml`, and
`infra/config/redis` owned by the deploy user, not writable by the app
containers, and backed by your normal secret/config-management workflow.
Compose mounts them read-only into backend/Redis; host-side write access is
the deployment control plane.

---

## 4. Release strategy — canary via Helm rolling update

SwarmOS uses **Kubernetes rolling updates** as the release strategy:

- `maxSurge: 1, maxUnavailable: 0` — never drop a healthy backend pod
  during a roll.
- The readiness probe gates traffic switchover. The Phase 6.D `/ready`
  probe checks DB + Redis + auth, so a pod cannot accept traffic until
  all three are live.
- Helm tracks revisions; rollback is `helm rollback swarmos <revision>`.

### Release pipeline

```
1. git tag v0.X.Y
2. push tag
3. image-build.yml → builds + scans + pushes to GHCR
4. image-sign.yml  → cosign sign keyless (drone-day §2.E)
5. operator runs:
   helm upgrade --install ... --set image.<svc>.digest=<sha256>
6. rollout completes when readiness gates green for every pod
7. smoke test (§2.4)
```

### Rollback

```bash
helm history swarmos -n swarmos
helm rollback swarmos <previous-revision> -n swarmos
```

The migration history rollback is more involved — see
[`migrations.md`](migrations.md) §"Rolling back".

### Why not blue/green or traffic-percentage canary?

A 5%/25%/100% traffic split canary requires a service mesh
(Istio/Linkerd) and adds an ingress-side controller layer that the
current Phase 6 scope does not justify. The roadmap explicitly defers
service-mesh-level canary to a future phase; for now the readiness-gated
rolling update gives us most of the safety with none of the operational
overhead.

---

## 5. Day-2 operations

- **Backups**: the daily CronJob (k8s) or sidecar (compose-prod) writes
  GPG-encrypted dumps to `/backups`. Drone-day §2.E binds the off-site
  sync (S3, rsync to a NAS, etc.).
- **Hot-reload site config**: `POST /admin/reload-site-config` with a
  commander JWT. See [`../security/auth.md`](../security/auth.md).
- **Operator rotation**: rotate `operators.yaml` via your secret backend,
  then `kubectl rollout restart deploy/swarmos-backend` (auth ingests
  the file at startup).
- **Cert renewal**: cert-manager handles k8s renewals automatically;
  the certbot sidecar handles compose-prod renewals every 12 h.

---

## 6. Verification checklist (drone-day-ready)

A SwarmOS deploy is "drone-day ready" only when ALL of these are true:

- [ ] `helm template ... -f values-<site>.yaml | kubectl apply --dry-run=client` clean
- [ ] `make docker-build` succeeds locally for backend + frontend + backup
- [ ] `cosign verify` succeeds on the published images
- [ ] cert-manager issued a real Let's Encrypt cert (not staging)
- [ ] `kubectl -n swarmos get pods` shows backend + frontend Ready
- [ ] `/ready` is 200 with `db: ok`, `redis: ok`, `auth: ok`
- [ ] `/metrics` reachable from the Prometheus scraper (commander JWT
      or IP allowlist)
- [ ] One backup CronJob run completed in `/backups`
- [ ] One quarterly restore drill recorded in the runbook
      (see [`migrations.md`](migrations.md) §"Restore drill")

Tick every box, link the evidence in
[`drone-day-checklist.md`](drone-day-checklist.md) §5.
