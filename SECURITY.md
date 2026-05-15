# Security Policy

SwarmOS operates real drone fleets in real environments. Security is a
non-negotiable invariant of the product. This document describes how to
report a vulnerability and what to expect in return.

## Reporting a vulnerability

**Do not open a public GitHub issue for a suspected vulnerability.**

Use GitHub's Private Vulnerability Reporting:
https://github.com/DavideCapurr/swarm/security/advisories/new

Include in your report:

1. The component / file path / commit SHA affected.
2. A description of the issue (impact, attack vector, prerequisites).
3. Reproduction steps or proof of concept.
4. Suggested mitigation if you have one.

We acknowledge reports within **3 business days** and provide a
status update within **10 business days**.

## Scope

In scope:

- `core/`, `swarm_os/`, `orchestrator/`, `adapters/`, `sim/`, `backend/`
  (SwarmOS backend)
- `frontend/` (Console)
- `infra/`, `scripts/`, `.github/` (build + deployment)
- Any documented public API endpoint
- Authentication / authorization / session management (Phase 6+)
- Drone command pipeline (geofence, safety policy)

Out of scope:

- Issues in third-party services (Docker Hub, GitHub, etc.) unless caused
  by our configuration.
- Issues that require already-privileged access (e.g. root on the host
  running the backend).
- Denial of service via large-volume traffic from a single source (we have
  rate limits but local DoS is not a vulnerability we'll pay attention to
  unless it bypasses those limits).
- Social engineering or phishing of contributors.
- Theoretical issues without a working proof of concept.

## Supported versions

| Version | Status                |
|---------|-----------------------|
| `main`  | Supported             |
| Tags    | Supported for 12 months from release |

Pre-1.0 (current): only `main` is supported. After 1.0 we will publish a
support policy with explicit version windows.

## Disclosure timeline

- Day 0: report received, acknowledgement sent.
- Day 1-10: triage + reproduction + impact assessment.
- Day 10-30: fix developed + reviewed.
- Day 30: fix landed in `main`, advisory published.
- We will not embargo a fix for more than 90 days without explicit
  agreement.

If a fix is non-trivial we will keep the reporter updated weekly.

## What you can expect

- Acknowledgement of your report.
- Public credit in the advisory if you want it.
- No legal action for good-faith research under the scope above.
- Coordination on a disclosure timeline.

## Security controls in this repository

Live controls — these are part of the product, not aspirational:

- Lockfiles committed (`package-lock.json`, `uv.lock`).
- `npm ignore-scripts=true` to disable lifecycle scripts on install.
- GitHub Actions pinned by 40-char SHA.
- Docker images pinned by `@sha256:` digest.
- Dependabot weekly for npm, pip, Docker, GitHub Actions.
- Dependency Review on every PR.
- CodeQL, Bandit, Semgrep, ESLint security plugin in CI.
- gitleaks + detect-secrets in pre-commit and CI.
- Trivy image scan in CI.
- CORS allowlist (env-driven, never `*` in prod).
- WebSocket Origin validation.
- Security response headers (CSP, X-CTO, X-Frame-Options DENY,
  Referrer-Policy, Permissions-Policy, HSTS in prod).
- Pydantic strict mode on all API bodies.
- Rate limit on action endpoints.
- Body size + request timeout middleware.
- No stack traces in HTTP responses.

Threat model and incident response procedure:

- [`docs/security/threat-model.md`](docs/security/threat-model.md)
- [`docs/security/incident-response.md`](docs/security/incident-response.md)

## Contact

For non-vulnerability security questions, open a discussion at
https://github.com/DavideCapurr/swarm/discussions/categories/security
or reach out via the channel listed on the project README.
