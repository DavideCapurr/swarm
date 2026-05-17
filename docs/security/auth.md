# Auth + RBAC (Phase 6.C)

This document captures the design and runbook for SwarmOS operator
authentication, role-based access control, and MFA for the commander
role. It complements
[`docs/security/threat-model.md`](threat-model.md) (controls S49–S52)
and [`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md)
§2.C (the deployment checklist).

## 1. Model in one paragraph

SwarmOS issues pure JWTs (HS256). Three roles form a strict
hierarchy — `viewer < operator < commander`. The Console authenticates
once via `POST /auth/login`, then carries `Authorization: Bearer <jwt>`
on every REST call. The WebSocket upgrade carries the same token as a
query parameter (the browser API forbids custom WS headers). Refresh
tokens rotate on every use. The commander role requires a TOTP code at
login and the access-token claim `mfa=true` is re-checked on every
commander-only call.

## 2. Tokens

- **Algorithm**: HS256. The shared secret comes from env
  `SWARM_JWT_SECRET` (≥ 32 bytes). Boot refuses to start in prod if
  it's missing or too short.
- **Issuer / audience**: `swarm-os` / `swarm-console` (overridable via
  env). Mismatch → 401 `invalid_issuer` / `invalid_audience`.
- **Access TTL**: 15 minutes.
- **Refresh TTL**: 8 hours. Each use is a rotation: the spent refresh
  is added to the revocation list immediately so it can't be replayed.
- **Required claims**: `iss`, `aud`, `sub`, `exp`, `iat`, `jti`, `typ`,
  `role`. Optional, but always present: `site`, `mfa`.
- **Algorithm substitution**: the decoder allowlists exactly `HS256`,
  closing the classic `alg=none` / `HS384-key-as-public-key` confusion
  attacks.

## 3. Roles

| Role        | GET reads | `/actions/verify|hold-patrol|dismiss|return` | `/admin/*` |
|-------------|-----------|-----------------------------------------------|-----------|
| viewer      | yes       | 403                                           | 403       |
| operator    | yes       | yes                                           | 403       |
| commander   | yes       | yes                                           | yes (with MFA) |

- `/health` and `/` are unauthenticated (orchestrator liveness probes).
- `/auth/login` and `/auth/refresh` are unauthenticated.
- Every other route requires at least the viewer role.

## 4. MFA (commander only)

The commander login flow demands a 6-digit TOTP code (RFC 6238) on top
of the password. The store row carries a base32 secret produced by:

```
python -m backend.app.auth.cli new-mfa op-alice01
```

The CLI prints both the secret and an `otpauth://totp/SWARM:…` URI
ready for QR enrolment in any standard authenticator. The Console
exposes a `totp_code` field on the login page; viewers and operators
leave it blank.

The access token's `mfa` claim is True iff the login satisfied the
TOTP challenge. Commander-only endpoints re-check this on every
request, so a stolen access token from a non-MFA flow can't be
escalated.

## 5. Revocation

`backend/app/auth/revocation.py` keeps a `jti -> expires_at` dict in
process memory. On a successful logout we revoke the access token's
JTI; refresh rotation revokes the spent refresh JTI. Expired entries
are swept periodically so the table doesn't grow unbounded.

The Redis-backed implementation (per the original roadmap §6.C bullet
"Revocation list (Redis-backed)") is queued for Phase 6.E together
with the rest of the secure-bus rollout. The current in-process store
is the single-instance fallback; multi-replica deploys must wait for
the Redis swap before scaling out.

## 6. Operator identity store

A YAML file on disk holds the operator set. Default path is
`infra/config/operators.yaml`; env var `SWARM_OPERATORS_CONFIG`
overrides. The store is parsed at boot and validated strictly — an
unknown key, duplicate operator id, missing MFA secret on a
commander row, or unsupported role are all hard errors.

The example template lives at
[`infra/config/operators.example.yaml`](../../infra/config/operators.example.yaml).
The real file is in `.gitignore`.

Password hashes use PBKDF2-HMAC-SHA256 with 600,000 iterations
(matches OWASP 2023). Argon2 or bcrypt would be stronger but require
extra deps; the drone-day checklist documents the upgrade path for
when an OIDC bridge takes over local auth.

## 7. Storage on the client

The Console keeps both the access and refresh tokens in
`localStorage`. CSP restricts `script-src` to `'self'`, no third-party
scripts run, and the access TTL is 15 minutes — the XSS exposure
window is narrow. Moving the refresh token to an HttpOnly cookie is
the Phase 6.E hardening pass (it requires a CSRF strategy + SameSite +
a server-side cookie issuer pipe).

## 8. Audit

Every login (success or failure), refresh (success or failure), logout,
and revocation appends a `system` Event to the SwarmOS event deque,
broadcasts it on the WS hub, and persists it via the bus consumer.
Bodies are confidence-bound and PII-free: the operator id is recorded,
the password and TOTP code are not.

## 9. Rate limiting

`/auth/login` and `/auth/refresh` share the same per-(IP, operator_id)
token bucket as the action endpoints (default 30 req/min). Brute-force
attempts trip 429 well before they can probe meaningful passwords.

## 10. Anti-patterns we did NOT take

- No `alg=none`.
- No transitive-dep dependency on PyJWT — the lib is now in
  `pyproject.toml` directly.
- No third-party MFA library; TOTP is RFC 6238 over stdlib hmac/hashlib.
- No OIDC bridge yet — pure JWT only. The bridge is a Phase 6.E
  follow-up if a customer needs SSO.
- No `X-Admin-Token` shim left behind. The 6.B transitional gate was
  removed when 6.C landed.

## 11. CLI helpers

```
# Generate a password envelope to paste into operators.yaml:
python -m backend.app.auth.cli hash-password

# Provision MFA for a commander:
python -m backend.app.auth.cli new-mfa op-commander01

# Lint an operators.yaml without booting the backend:
python -m backend.app.auth.cli verify infra/config/operators.yaml
```

## 12. Env vars

| Name                          | Purpose                                       | Required in prod |
|-------------------------------|-----------------------------------------------|------------------|
| `SWARM_JWT_SECRET`            | HS256 signing secret (≥ 32 bytes)             | yes              |
| `SWARM_OPERATORS_CONFIG`      | Path to the operator store YAML               | optional         |
| `SWARM_JWT_ACCESS_TTL_S`      | Override access-token TTL (default 900 s)     | optional         |
| `SWARM_JWT_REFRESH_TTL_S`     | Override refresh TTL (default 28 800 s)       | optional         |
| `SWARM_JWT_ISSUER`            | Override `iss`                                | optional         |
| `SWARM_JWT_AUDIENCE`          | Override `aud`                                | optional         |
| `SWARM_AUTH_DISABLED`         | Dev-only escape hatch — fail closed otherwise | never in prod    |

## 13. Outstanding (Phase 6.E / 6.F)

- Redis-backed revocation list (multi-replica).
- HttpOnly cookie pipe for the refresh token (CSRF + SameSite).
- OIDC bridge for SSO customers.
- Hardware-backed signing key (HSM / KMS) instead of an env-mounted
  HS256 secret.
- Pen-test pass; the Phase 6 verification matrix gates that gate.
