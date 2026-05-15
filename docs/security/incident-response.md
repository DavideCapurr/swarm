# SwarmOS — incident response runbook

Triage and response procedure for security incidents. Pair with
[`threat-model.md`](threat-model.md).

## Severity definitions

| Severity | Definition | Response time |
|----------|------------|---------------|
| **SEV1** | Active exploitation; drone or operator safety at risk; data exfiltration in progress | < 30 min |
| **SEV2** | Credible exploit path; production impact likely within hours | < 2 h |
| **SEV3** | Vulnerability confirmed but not yet exploited; needs patching | < 1 business day |
| **SEV4** | Suspected issue under triage | < 3 business days |

## Roles

| Role | Responsibility |
|------|---------------|
| Incident Commander (IC) | Owns the incident end-to-end. Decides scope, comms, escalation. |
| Tech Lead | Reproduces, diagnoses, patches. |
| Comms Lead | Customer + public communication. SEV1/2 only. |
| Scribe | Timeline log in the incident channel. |

For a single-developer team, the same person can hold IC + Tech Lead. The
Scribe role is then a write-only doc you update as you go.

## Detection sources

- Alerting (Phase 6: Prometheus alert rules → on-call paging).
- GitHub Security advisories / Dependabot alerts.
- Vulnerability reports via `SECURITY.md` channel.
- Customer report.
- SAST / DAST / CodeQL output.
- Audit log anomaly (unexpected `OperatorCommand` pattern, auth failure
  spike).

## Response procedure

### 0. Confirm

- Is this a real security issue (not a bug)? Check the [threat model](threat-model.md).
- What's the severity? (See table above.)
- Open an incident channel / doc with timestamp.

### 1. Contain

Pick the minimum action that stops further damage:

- **Active exploit in production:**
  - Rotate affected credentials immediately (DB, JWT signing key, vendor
    API keys, GitHub PAT).
  - Block source IP at the reverse proxy if exploit is in-flight.
  - For drone-safety scenarios: send `EMERGENCY_RTL_ALL` to all units in
    the affected site (Phase 6 command).
- **Compromised dependency:**
  - Pin the previous-known-good version in the lockfile.
  - Push a security branch immediately. Do **not** wait for normal
    release cadence.
- **Leaked secret in repo:**
  - Rotate the secret first.
  - Then rewrite history via `git filter-repo` and force-push (this is
    the only situation where force-push is allowed; coordinate with all
    contributors).
  - Notify GitHub support to purge the cached copies.

### 2. Eradicate

- Identify the root cause. Don't stop at the symptom.
- Patch all affected code paths, not just the reported one.
- Add a regression test that proves the patch.
- Run `make lint && make test && make audit` before deploying the fix.

### 3. Recover

- Deploy the fix using the standard pipeline (no shortcuts that skip
  CI).
- Verify the fix in production (synthetic check + customer
  confirmation).
- Re-enable any temporarily disabled features.
- Monitor for 24 h before standing down.

### 4. Communicate

For SEV1/2:

- Internal: write a one-pager within 1 h: what happened, what's
  affected, what we did, what's next.
- Customer: notify within the SLA period (24 h for SEV1, 72 h for SEV2
  unless contract says otherwise).
- Public: if the issue had user-data impact, file a CVE and update
  `SECURITY.md` advisories.
- For GDPR-relevant data breaches (Phase 4+): notify the supervisory
  authority within 72 h.

### 5. Post-mortem

Within 5 business days of incident close:

- Document timeline (detection → containment → fix → recovery).
- Identify root cause (the actual bug, not just the immediate trigger).
- List action items with owners and deadlines.
- Update the threat model if a new threat class emerged.
- Add SAST/DAST/monitoring rule that would have caught it earlier.
- Share post-mortem internally (and externally if SEV1).

## Useful commands

### Rotate JWT signing key (Phase 6)

```bash
# Generate new key
openssl rand -base64 64 > /run/secrets/jwt-signing-key.new
# Atomic swap (the backend supports kid-based key rotation)
kubectl rollout restart deployment/swarm-backend
# After 16 minutes (max token TTL + buffer):
rm /run/secrets/jwt-signing-key.old
```

### Rotate Postgres password (Phase 4+)

```bash
psql -c "ALTER USER swarm WITH PASSWORD '<new>';"
# Update secret in vault, restart backend pods
kubectl set env deployment/swarm-backend POSTGRES_PASSWORD=<new>
```

### Block an IP at the reverse proxy

```bash
# Caddy
echo "  @blocked client_ip <ip>" >> Caddyfile
echo "  respond @blocked 403" >> Caddyfile
caddy reload
```

### Emergency stop all drones (Phase 6)

```bash
# As commander, requires MFA
curl -X POST \
  -H "Authorization: Bearer <commander-jwt>" \
  -H "X-MFA-Token: <totp>" \
  https://swarm.example.com/admin/emergency-rtl-all
```

### Force credential rotation in CI

Go to repo Settings → Secrets and variables → Actions → rotate the
`*_TOKEN` secrets. Re-run any in-flight workflows.

## Contact tree

| Situation | Who | How |
|-----------|-----|-----|
| Drone safety active issue | On-call + site owner | Phone (no IM) |
| Data breach | DPO + counsel | Email + phone |
| Public disclosure pending | Comms Lead | Email |
| Critical CVE patch | Tech Lead | GitHub issue + release |

## Lessons-learned archive

Post-mortems are kept under `docs/security/post-mortems/<YYYY-MM-DD>-<slug>.md`.

Templates: `docs/security/post-mortems/_template.md`.
