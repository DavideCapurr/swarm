# SwarmOS — threat model

Living document. Updated as the architecture evolves. Last review:
Phase 0 baseline (2026-05).

## Assets being protected

| Asset                          | Why it matters |
|--------------------------------|----------------|
| Drone fleet                    | Physical safety. A hijacked drone causes property/people harm. |
| Operator decision integrity    | Wrong decision → wrong action → physical or business consequence. |
| Telemetry / sensor data        | Privacy + competitive intel + post-incident audit. |
| Camera / video data            | Privacy (GDPR) + potential PII exposure. |
| Operator identity & audit log  | Accountability + regulatory + forensic. |
| Adapter credentials (vendor)   | Compromise → drone takeover. |
| Sites / geofence configuration | Wrong polygon = drone in NFZ or hitting people. |

## Trust boundaries

1. **Internet ↔ Console (browser)** — public, hostile.
2. **Console ↔ SwarmOS backend** — over TLS in prod, authenticated
   (Phase 6).
3. **SwarmOS backend ↔ bus (Redis)** — internal; Phase 5 enforces a
   fail-closed Redis mTLS entry criterion for prod / required-secure runs
   (`rediss://` + client cert/key + CA), while local dev may use plaintext.
4. **SwarmOS backend ↔ database (Postgres)** — internal, TLS + auth
   (Phase 4).
5. **SwarmOS backend ↔ adapter** — internal, but the adapter talks to a
   vendor that lives on Internet or a separate radio link.
6. **Adapter ↔ drone** — vendor-specific. Trust depends on vendor link
   encryption.

## STRIDE per component

### Console (frontend)

| Threat | Mitigation |
|--------|------------|
| Spoofing (CSRF) | Bearer-token auth (Phase 6.C); JWTs are not auto-sent by the browser, so classic CSRF is mooted for now. HttpOnly cookie path + CSRF tokens are queued for 6.E. |
| Tampering (XSS) | React safe defaults + CSP (`script-src 'self'`, no `unsafe-inline` from Phase 6) + no `dangerouslySetInnerHTML`. |
| Repudiation | Every operator command audit-logged server-side (Phase 4); auth events (login / refresh / logout / revocation) audit-logged (Phase 6.C). |
| Information disclosure | Access + refresh tokens kept in `localStorage` (Phase 6.C); CSP keeps third-party scripts out, access TTL is 15 min. HttpOnly cookie pipe for refresh queued for 6.E. |
| Denial of service | Rate-limit on actions (Phase 1) + on login + refresh (Phase 6.C). |
| Elevation of privilege | RBAC server-side enforced via `require_role` (Phase 6.C). UI hides actions the role lacks but the source of truth is server-side. MFA-bit re-checked on commander routes. |

### SwarmOS backend (FastAPI + WS)

| Threat | Mitigation |
|--------|------------|
| Spoofing | CORS allowlist (Phase 0). WS Origin check (Phase 0). JWT HS256 with allowlisted algorithm + iss/aud/exp validation (Phase 6.C); WS upgrade requires a valid access token via `?token=` query or `Sec-WebSocket-Protocol: bearer, <jwt>`. OIDC bridge optional (Phase 6.E). |
| Tampering | Pydantic strict + parameterized SQL (Phase 0/4). |
| Repudiation | structlog + audit log with hash chain (Phase 4). |
| Information disclosure | No stack traces (Phase 0). IDOR check per `site_id` (Phase 6). PII redaction in logs (Phase 4). |
| Denial of service | Rate-limit + body size + request timeout (Phase 0/1). |
| Elevation of privilege | Three-role hierarchy (viewer/operator/commander) enforced by `require_role`; commander demands `mfa=true` claim on every request (Phase 6.C). |

### Bus (Redis)

| Threat | Mitigation |
|--------|------------|
| Spoofing | Redis client mTLS is enforced when `SWARM_ENV=prod` or `SWARM_REQUIRE_SECURE_BUS=1`; no in-memory fallback in secure mode. Network segmentation. |
| Tampering | `rediss://` required in secure mode. Pub/sub topics scoped per service. |
| Information disclosure | No PII on bus (telemetry is geo + state only). |
| Denial of service | Redis maxmemory + eviction policy. |

### Database (Postgres / Timescale, Phase 4+)

| Threat | Mitigation |
|--------|------------|
| Spoofing | sslmode=require + credentials from vault. |
| Tampering | Audit log hash chain. Append-only constraint on `events` table. |
| Repudiation | Hash chain + NTP-synced timestamps. |
| Information disclosure | Encryption at rest (file system / managed service). Connection encryption. |
| Denial of service | Connection pool limits + slow query monitor. |
| Elevation of privilege | DB user least privilege (no DDL outside migrations). |

### Adapter (vendor-specific, Phase 5+)

| Threat | Mitigation |
|--------|------------|
| Spoofing (vendor impersonation) | Pin vendor SDK version + offline package-integrity gate for `pymavlink`; publisher identity/Sigstore attestations remain outside the current PyPI evidence gate. |
| Tampering (telemetry injection) | Rate-limit inbound Hz cap + sanity bounds. |
| Information disclosure (creds) | Vault for adapter credentials. |
| Denial of service | Vendor rate limits + circuit breaker per adapter. |
| Elevation of privilege | Adapter runs as least-privilege user. |

### Supply chain (CI + dependencies)

| Threat | Mitigation |
|--------|------------|
| Malicious JavaScript package (TanStack-class) | `ignore-scripts=true` + lockfile + audit + Dependabot + dependency review. |
| Compromised GitHub Action | SHA-pin actions (40 char) + `permissions: contents: read`. |
| Compromised Docker base image | Digest-pin + Trivy scan + Dependabot for docker. |
| Compromised CI runner | GitHub-hosted runners only (no self-hosted in Phase 0-6). |
| Compromised maintainer token | Branch protection + required reviews + signed commits encouraged. |

## Attack scenarios considered

### Scenario A — JavaScript postinstall exfiltration (TanStack-style)

Path: a transitive frontend dependency is compromised; its postinstall script reads
`GITHUB_TOKEN` from env and exfiltrates.

Mitigation:
- `frontend/.pnpmrc` has `ignore-scripts=true`.
- `corepack pnpm install --ignore-scripts` in CI.
- CI workflow `permissions: contents: read` (no write to anywhere).
- Dependabot weekly catches known-bad versions.
- Dependency Review action blocks PRs that add a package with a known
  CVE.

### Scenario B — compromised GitHub Action

Path: action maintainer's account is compromised and they re-tag `v4` to
point at a malicious commit.

Mitigation:
- All actions pinned by full 40-char SHA, not tag.
- Workflow `permissions:` limited to `contents: read` (no write).

### Scenario C — drone hijack via vendor link

Path: attacker on RF link to drone replays or forges command.

Mitigation: vendor-dependent. Documented in
`docs/architecture/adr/0010-adapter-trust-boundary.md` (Phase 5).
SwarmOS treats the adapter as a semi-trusted source: validates state
ranges, rate-limits inbound, geofence-enforces outbound missions.

### Scenario D — operator credential theft

Path: phishing or session hijack of an operator account.

Mitigation (Phase 6.C):
- Short-lived JWT (15 min access, 8 h refresh, rotation on every use)
  — see [`docs/security/auth.md`](auth.md).
- Process-local revocation list keyed by JTI; spent refresh tokens
  revoked at rotation so leaked refresh can't be replayed. Redis-backed
  store is queued for Phase 6.E.
- MFA (TOTP, RFC 6238) is mandatory for the `commander` role at login
  and the `mfa=true` claim is re-checked on every commander-only
  endpoint.
- Geofence enforcement is server-side — a stolen viewer/operator
  account can't fly outside policy.
- Token storage: access + refresh in `localStorage`. CSP forbids
  third-party scripts; the XSS exposure window is the 15-min access
  TTL. HttpOnly-cookie pipe for the refresh token is the documented
  Phase 6.E hardening pass.

### Scenario E — geofence bypass via crafted mission

Path: attacker constructs a `MissionTask` with waypoints that cross a
no-fly zone.

Mitigation:
- Phase 6 `policy.py` validates every MissionTask against the site
  geofence polygon (segment intersection check, not just vertex
  containment).
- Missions can only be submitted via authenticated action endpoints.

### Scenario F — log tampering to hide misuse

Path: insider with DB write access deletes audit rows.

Mitigation (Phase 4):
- Hash chain on `events` table (each row hashes the previous).
- DB user that runs the app has INSERT-only on `events`.
- Off-site log replication.

### Scenario G — SSRF via stream URL

Path: vendor returns a stream URL `http://169.254.169.254/...` (AWS
metadata endpoint).

Mitigation (Phase 5):
- `LiveFeedFrame` only accepts URLs whose scheme is `rtsps://` or
  `https://`.
- Outbound HTTP allowlist for any backend fetch.

## Out of scope (current)

- Physical security of the dock / drone storage.
- Operator workstation security.
- ISP / network-level attacks on the customer site.
- Quantum-resistant crypto (not relevant in 2026 for this product).

## Review cadence

- Updated at the end of every phase.
- Pen-test pre-go-live (Phase 6).
- Continuous: dependabot + CodeQL + SAST findings reviewed weekly.
