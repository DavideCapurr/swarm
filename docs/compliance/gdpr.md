# GDPR — Data Protection (Phase 6.I)

This document is the SwarmOS data-protection baseline. It maps every
personal datum SwarmOS handles to a storage location, a legal basis, a
retention period, and a path for exercising the rights of the data
subject. The technical controls listed here are implemented in this
phase; the operational, contractual, and regulatory items that depend on
external assets (a signed DPA, a DPO appointment, an EASA/FAA
registration, a real pen-test) are catalogued in
[`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md) §2.I.

For the incident-handling path (responsible disclosure, customer
notification, regulator notification) see
[`docs/security/disclosure.md`](../security/disclosure.md). For the
underlying threat model and security controls see
[`docs/security/threat-model.md`](../security/threat-model.md). For the
canonical retention table see
[`docs/compliance/retention.md`](retention.md). For a template Article 28
processor agreement see
[`docs/compliance/dpa-template.md`](dpa-template.md).

## 1. Controller / processor posture

SwarmOS is deployed as **on-premises software on the site operator's
infrastructure**. The operator (the site owner running SwarmOS against
their own drones, on their own land, in their own jurisdiction) is the
**data controller** for every personal datum collected via the system.
The SwarmOS vendor is a **data processor** only when SwarmOS is offered
as a managed service; the self-hosted deployment shipped from this
repository involves no processor relationship by default.

No third-party sub-processors are wired by default. Optional integrations
(real weather API, NOTAM feed, OpenTelemetry exporter, GHCR image
pulls, Sigstore signing) are off by default and listed in
`drone-day-checklist.md` so the operator can run the relevant DPIA before
turning them on.

## 2. Personal data inventory

The table below is the canonical inventory. Every personal field landing
in the SwarmOS data plane is listed; "personal" follows GDPR Art. 4(1) —
anything that can identify a natural person directly or indirectly.

| Field            | Storage                              | Category               | Legal basis (Art. 6) | Retention            | Source                          |
|------------------|--------------------------------------|------------------------|----------------------|----------------------|---------------------------------|
| `operator_id`    | `operator_commands.operator_id`      | Identifier             | 6(1)(b) Contract     | 7 years (audit)      | JWT `sub` on every accepted intent |
| `operator_id`    | `events.body` (system audit lines)   | Identifier             | 6(1)(c) Legal obligation (audit) | 1 year   | Audit log emitted on login / refresh / admin actions |
| `operator_id`    | `infra/config/operators.yaml`        | Identifier + auth      | 6(1)(b) Contract     | While account active | Operator store (provisioned by commander CLI) |
| `password_hash`  | `infra/config/operators.yaml`        | Authentication secret  | 6(1)(b) Contract     | While account active | PBKDF2-HMAC-SHA256, 600 000 it. |
| `mfa_secret`     | `infra/config/operators.yaml`        | Authentication secret  | 6(1)(b) Contract     | While account active | TOTP seed for commander accounts |
| `refresh_jti`    | In-process revocation store          | Session metadata       | 6(1)(f) Legitimate interest (session integrity) | 8 h (refresh TTL) | Issued by `JWTService` |
| HTTP client IP   | Structured request log (stdout)      | Identifier (indirect)  | 6(1)(f) Legitimate interest (security) | 30 days (log retention by ops) | `RequestIDMiddleware` |

Telemetry fields (`lat`, `lon`, `alt_m`, `velocity_mps`, `battery_pct`,
`link_quality`) describe the **drone**, not a natural person. They become
personal data only if a drone is consistently tied to an identified
individual — which is not the case in the operational model (a single
operator supervises a fleet). They are kept as **operational data**
under Art. 6(1)(f) with the 30-day retention enforced by the Phase 4
Timescale policy.

Camera frames / on-board video are **not stored by SwarmOS today**. When
the camera payload is wired (drone-day), the resulting frames become
personal data if they capture identifiable people and must be governed
by a site-level policy (purpose, lawful basis, retention, blurring at
ingest, etc.) before ingest is enabled. The placeholder for this
control is in `drone-day-checklist.md` §2.I.

## 3. Data flow

```
operator (browser)
  │  HTTPS + Authorization: Bearer <jwt>
  ▼
nginx (TLS terminator, security headers)
  │
  ▼
FastAPI backend ── structlog JSON → stdout (request log, redacted)
  │   │
  │   └─ /actions/*           ──► coordinator.apply_command ──► state.commands
  │   │                                                        ──► repository.write_operator_command
  │   ▼
  │  WS hub broadcast (events / unit / mission frames)
  │
  └─ bus_consumer ──► Redis (in-process or remote) ──► repository.write_events/telemetry
                                                       │
                                                       ▼
                                              PostgreSQL + Timescale
                                              (events, telemetry, operator_commands, …)
```

* PII enters the system at the JWT login (`/auth/login`). The
  `operator_id` rides on every protected call thereafter as a claim.
* It is persisted only at the points marked in §2: `operator_commands`,
  `events.body`, and the request log on stdout.
* No PII is broadcast on the public WebSocket: the Console fetches
  operator history via the authenticated REST `/operator/commands` route
  and the action timeline via `/events`; the WS frames carry
  `operator_id` only inside `event.body` strings that are explicitly
  generated for audit purposes.
* Backups (`pg_dump | gpg --encrypt`, Phase 6.E) inherit the same data
  inventory. The GPG recipient and off-site sync target are operator-
  managed; see `docs/ops/deploy.md`.

## 4. Data subject rights (Art. 15–22)

SwarmOS exposes two admin-mediated endpoints for the controller to
honour data subject requests. Both are gated by the JWT commander role
with an MFA-bound access token; both append a `system` audit event with
the actor commander and the targeted `operator_id`.

| Right                       | Article | Mechanism                                                              |
|-----------------------------|---------|------------------------------------------------------------------------|
| Access (subject access)     | 15      | `POST /admin/export` returns a JSON document with every row in `operator_commands` and every audit event referencing the subject. |
| Rectification               | 16      | The operator store CLI (`python -m backend.app.auth.cli`) updates the YAML row; password rotation rehashes; MFA re-enrolment regenerates the seed. |
| Erasure (right to be forgotten) | 17  | `POST /admin/forget` anonymises `operator_commands.operator_id` to `op-erased-<sha256_short>` and emits an audit event. The operator-store entry is removed via the CLI in the same maintenance window. |
| Restriction                 | 18      | The commander disables the operator account in the YAML (sets `disabled: true` in the CLI). New logins fail; in-flight tokens are revoked. |
| Portability                 | 20      | The `/admin/export` JSON document is structured and machine-readable. |
| Object                      | 21      | The operational logging legal basis is Art. 6(1)(f) — the data subject may object via the controller's documented channel; the controller assesses whether the legitimate interest still overrides. |
| Automated decision-making   | 22      | SwarmOS does not take legally significant automated decisions about the operator. Auto-RTL on low battery / link is a drone-state decision, not an individual decision. |

The two endpoints are **admin-mediated**: there is no public DSAR
portal in Phase 6.I (anti-overreach — a self-service portal needs a
separate identity proofing step that belongs to a later phase). The
controller's documented DSAR procedure is expected to authenticate the
data subject out-of-band and then dispatch the commander to invoke
`/admin/export` / `/admin/forget`.

### Erasure semantics

`operator_commands` rows are **anonymised, not deleted**, on erasure:
the audit trail must remain consistent (a missing row is a worse
compliance posture than a redacted one), and the columns that carry
PII (`operator_id`) are rewritten to a deterministic pseudonym
`op-erased-<sha256_short>`. Foreign references (`mission_id`,
`anomaly_id`) are kept because they refer to operational artefacts, not
to a person. The same erasure path appends a `system` event recording
the action — that audit row itself does not carry the original
`operator_id`. This satisfies Art. 17(1) read with Art. 17(3)(b) and (e)
(retention required for compliance with a legal obligation and for the
defence of legal claims).

## 5. Retention

The canonical retention table lives in
[`docs/compliance/retention.md`](retention.md). Enforcement is by
Timescale `add_retention_policy` for hypertables (`telemetry` 30 days,
`events` 365 days); permanent tables are governed by the documented
retention plus the erasure endpoint. Backup retention is set by
`BACKUP_RETENTION_DAYS` (`scripts/backup_postgres.sh`); the default is
30 days and rotates the GPG-encrypted dumps on a single schedule.

## 6. Security measures (Art. 32)

SwarmOS controls map to the threat model
([`docs/security/threat-model.md`](../security/threat-model.md)):

* Transport: HTTPS + HSTS at the nginx terminator, mTLS on the Redis
  bus when `SWARM_BUS_TLS=required`.
* Authentication: JWT HS256, MFA on the commander role, PBKDF2-HMAC-
  SHA256 password hashing with 600 000 iterations.
* Authorisation: three-role hierarchy enforced by FastAPI dependencies;
  RBAC re-checked server-side on every request; commander-only routes
  re-verify the `mfa=true` claim.
* Audit: every intent, login, refresh, logout, admin action, export,
  and erasure is persisted as a `system` event and broadcast on WS.
* Integrity: composite primary keys (`events`, `telemetry`) and
  upsert-with-`ON CONFLICT` semantics; signed images via Sigstore on
  release; SBOM + provenance attestations.
* Confidentiality of secrets: `password`, `totp`, `mfa_secret`,
  `refresh_token`, `access_token`, `authorization`, `cookie`,
  `api_key`, `private_key` are stripped from every log line by the
  structlog redactor.
* Backups: `pg_dump | gpg --encrypt`, no plaintext intermediate;
  retention pruning is fingerprint-checked.

## 7. Breach notification (Art. 33–34)

The internal flow is documented in
[`docs/security/disclosure.md`](../security/disclosure.md). Operational
checklist:

1. Detection → on-call engineer raises the incident in the operator
   chat (no PII in the channel).
2. Containment → revoke affected JWT secrets (`SWARM_JWT_SECRET`),
   rotate the GPG recipient, kill compromised sessions
   (`POST /auth/logout` per subject, or `RevocationStore.clear()` for
   the whole process if a breach is suspected).
3. Assessment → controller's DPO decides whether the breach is likely
   to result in a risk to the rights and freedoms of natural persons
   (Art. 33(1)).
4. Notification → if so, controller notifies the supervisory authority
   within 72 hours, and the data subjects "without undue delay" if the
   risk is high (Art. 34).
5. Post-mortem → recorded in `docs/ops/runbook.md`, referenced from the
   audit log.

## 8. DPIA (Art. 35)

A DPIA is required because:

* SwarmOS handles location data (drone telemetry) at high frequency,
  which may relate to identifiable people if a drone is consistently
  associated with one operator.
* The system supports systematic monitoring of publicly accessible
  areas when the camera payload is wired.

The DPIA itself is operator-specific and not shipped with this
repository — the controller must run it against their concrete
deployment. The reference inputs (data inventory, flow, retention,
controls) are this document, `threat-model.md`, and `retention.md`.

## 9. Out of scope this phase (anti-overreach)

* PDF report generation — forbidden by the Phase 6 anti-overreach
  rules; the export endpoint emits JSON only.
* Public DSAR portal — the controller's documented procedure handles
  data-subject authentication; SwarmOS only provides the admin tools.
* Real NOTAM / U-space / weather provider integration — drone-day.
* External DPIA management tools — operator's choice.
* External DPO appointment workflow — operator's choice.
