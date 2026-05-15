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
3. **SwarmOS backend ↔ bus (Redis)** — internal, mTLS in prod
   (Phase 5/6).
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
| Spoofing (CSRF) | SameSite=Strict cookies + CSRF token on state-changing endpoints (Phase 6). For Phase 0-5 the operator handle header is rotated per session. |
| Tampering (XSS) | React safe defaults + CSP (`script-src 'self'`, no `unsafe-inline` from Phase 6) + no `dangerouslySetInnerHTML`. |
| Repudiation | Every operator command audit-logged server-side (Phase 4). |
| Information disclosure | No localStorage tokens (Phase 6 cookie HttpOnly). No third-party scripts. |
| Denial of service | Rate-limit on actions (Phase 1). |
| Elevation of privilege | RBAC server-side (Phase 6). UI hides actions the role lacks but the source of truth is server-side. |

### SwarmOS backend (FastAPI + WS)

| Threat | Mitigation |
|--------|------------|
| Spoofing | CORS allowlist (Phase 0). WS Origin check (Phase 0). JWT + OIDC (Phase 6). |
| Tampering | Pydantic strict + parameterized SQL (Phase 0/4). |
| Repudiation | structlog + audit log with hash chain (Phase 4). |
| Information disclosure | No stack traces (Phase 0). IDOR check per `site_id` (Phase 6). PII redaction in logs (Phase 4). |
| Denial of service | Rate-limit + body size + request timeout (Phase 0/1). |
| Elevation of privilege | RBAC + MFA for `commander` (Phase 6). |

### Bus (Redis)

| Threat | Mitigation |
|--------|------------|
| Spoofing | mTLS (Phase 5/6). Network segmentation. |
| Tampering | TLS (Phase 5/6). Pub/sub topics scoped per service. |
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
| Spoofing (vendor impersonation) | Pin vendor SDK version + verify signature when available. |
| Tampering (telemetry injection) | Rate-limit inbound Hz cap + sanity bounds. |
| Information disclosure (creds) | Vault for adapter credentials. |
| Denial of service | Vendor rate limits + circuit breaker per adapter. |
| Elevation of privilege | Adapter runs as least-privilege user. |

### Supply chain (CI + dependencies)

| Threat | Mitigation |
|--------|------------|
| Malicious npm package (TanStack-class) | `ignore-scripts=true` + lockfile + audit + Dependabot + dependency review. |
| Compromised GitHub Action | SHA-pin actions (40 char) + `permissions: contents: read`. |
| Compromised Docker base image | Digest-pin + Trivy scan + Dependabot for docker. |
| Compromised CI runner | GitHub-hosted runners only (no self-hosted in Phase 0-6). |
| Compromised maintainer token | Branch protection + required reviews + signed commits encouraged. |

## Attack scenarios considered

### Scenario A — npm postinstall exfiltration (TanStack-style)

Path: a transitive npm dep is compromised; its postinstall script reads
`GITHUB_TOKEN` from env and exfiltrates.

Mitigation:
- `frontend/.npmrc` has `ignore-scripts=true`.
- `npm install --ignore-scripts` in CI.
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

Mitigation:
- Short-lived JWT (15 min) + refresh token in HttpOnly cookie (Phase 6).
- Revocation list (Phase 6).
- MFA for `commander` (Phase 6).
- Geofence enforcement is server-side — a stolen viewer/operator
  account can't fly outside policy.

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
