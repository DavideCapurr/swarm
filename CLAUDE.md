# SWARM / SwarmOS — context for Claude Code sessions

This file is read automatically by Claude Code at the start of every session
in this repo. Read it first, then act according to the rules below.

## Canonical strategy source

Before making product, roadmap, architecture, or positioning decisions, read
[`swarm-thesis.md`](swarm-thesis.md).

It is the canonical source of truth for SWARM's startup thesis, company
objective, problem definition, dual-use boundary, first wedge, low-cost fleet
economics, and long-term vision. When any other strategic document conflicts
with it, `swarm-thesis.md` wins. Current technical implementation/proof claims
must be grounded in [`docs/STATUS.md`](docs/STATUS.md), accepted ADRs and the
corresponding `docs/bench/` evidence.

## What this product is

- **SWARM** — the brand/project. The wordmark is uppercase. Repo path: `swarm/`.
- **SwarmOS** — the **product**: the autonomous operating layer that
  decides, plans, and coordinates the physical-agent fleet. SwarmOS is the
  source of operational truth. **SwarmOS is the entire backend of this repo**:
  every directory except `frontend/` is part of SwarmOS (`core/`, `swarm_os/`,
  `orchestrator/`, `adapters/`, `sim/`, `backend/`, `infra/`, `scripts/`).
- **physical agent** — a drone/robot/autopilot endpoint. It executes
  SwarmOS-issued objectives and reports telemetry/evidence. It may retain
  bounded low-level flight/safety behavior, but it never owns fleet mission
  decisions.
- **Console** — the operator-facing surface. It lives **only** in
  `frontend/`. Console renders state and sends intent. Console **never
  decides**.
- **operator** — the human using the Console. Sends intents
  (`/actions/verify`, `/actions/hold-patrol`), never manual drone commands.

## The hard rule

**SwarmOS decides. Physical agents execute. Console supervises.**

Mission-level authority stays in SwarmOS: objective selection, event
response, eligibility, allocation, mission ownership, retasking, abort/RTL,
payload policy, escalation, `ExecutionGroup` composition/role assignment and
replacement. An adapter/aircraft must not elect itself, allocate peers, create a
fleet action from a local observation, or run allocator/autonomy/scheduler
logic.

The onboard autopilot may still own the bounded behavior required to execute
safely: stabilization, actuator control, waypoint following, local obstacle
avoidance, geofence/altitude enforcement, low-battery and lost-link failsafes,
and emergency RTL/landing when central control is unavailable. Those answer
"how do I execute safely?", not "what should the fleet do next?".

ADR [`docs/adr/0011-central-decision-authority.md`](docs/adr/0011-central-decision-authority.md)
is the canonical architecture boundary for physical agents.

No UI ever invents operational truth. Every operational number on screen comes
from SwarmOS or the honest simulator. Any field temporarily derived client-side
must be flagged `derived: true` and rendered with the eyebrow `DERIVED`.

## Current demo boundary

The definitive investor/demo surface is `/demo/intrusion`. The legacy `/`
dashboard must not be modified for demo presentation work.

The recording source of truth is
[`docs/bench/final-demo-rehearsal.md`](docs/bench/final-demo-rehearsal.md).

The demo may use stock CCTV/drone imagery only as **explicitly labeled simulated
visualization**. It must never be presented as a live camera feed or runtime
evidence. PX4 output may be called confirmed only where the backend actually
observed the configured SITL output state. Speaker playback remains
`SIMULATED`.

## Source of truth for this project

The full development plan covering Phase 0 → Phase 6 lives at
[`docs/plan/swarmos-roadmap.md`](docs/plan/swarmos-roadmap.md).
The current forward execution order lives at
[`docs/plan/swarm-roadmap-evidence-to-scale.md`](docs/plan/swarm-roadmap-evidence-to-scale.md).
Current execution status lives at [`docs/STATUS.md`](docs/STATUS.md). When
starting a session, read STATUS first to see what is actually implemented and
validated.

## Hard rules every change must respect

### Design system (PDF §5.2)

- **No red.** Escalation is amber. Errors are amber. Never red.
- **No decorative shadow.** Only hairline gunmetal + inset highlights:
  `inset 0 1px 0 rgba(238,240,243,0.06)`.
- **No glassmorphism.** Radial mist is brand asset only, not chrome UI.
- **85% monochrome.** Accent colors only for state — Orbital Blue,
  Signal Green, Launch Amber.
- **No external icon kit.** Named inline SVG 24px, stroke 1.5px, round caps.
  Lucide is fallback only.
- **No unlabeled fake live feed.** Production/live surfaces must render real
  state or an honest offline/pending state. `/demo/intrusion` may use simulated
  imagery only when it is clearly labeled as simulation and never used as
  operational evidence.
- **No external chart / modal / toast / snackbar libraries.**

### Voice (PDF §5.2)

Use confidence-bound language only. Examples:
- `low-confidence anomaly`, `elevated anomaly`, `verified hotspot`
- `sector requires verification`, `sector confidence 064%`
- `verify sector`, `return Unit 003`, `hold patrol`

**Forbidden words** (CI greps for these and fails on hits):
`Intruder`, `Manual`, `fly drone`, `alarm`, `red-alert`, `red state`.

### Operator wording

Operator actions are **intents**, never manual drone commands. ✓
"Verify sector", "Hold patrol", "Return Unit 003". ✗ "Pilot drone",
"Manual override", "Land now".

### Security (360°)

Cybersecurity is non-negotiable. No vulnerabilities may be opened. The
threat model and controls are in
[`docs/security/threat-model.md`](docs/security/threat-model.md). Key
invariants:
- Dependencies pinned + lockfiles committed (`uv.lock`, `pnpm-lock.yaml`).
- pnpm `ignore-scripts=true` (no postinstall arbitrary execution).
- GitHub Actions SHA-pinned (full 40 char).
- Docker images digest-pinned (`@sha256:…`).
- CORS allowlist (env-driven), never `*`.
- WS origin check enforced.
- Security headers on every response (CSP, X-Content-Type-Options,
  X-Frame-Options DENY, Referrer-Policy, Permissions-Policy).
- No secrets in repo (gitleaks + detect-secrets in pre-commit + CI).
- Pydantic strict mode on every API body.
- Rate limit + body size limit + request timeout on all routes.
- No stack traces in HTTP responses.

### Root-cause discipline

Fix problems at the root. Never silence, suppress, or work around an error
to make a gate pass:
- Banned to get-to-green: `|| true`, `|| echo …`, `--no-verify`,
  `try/except: pass`, blanket `# noqa` / `# type: ignore`, skipped/`xfail`
  tests, or audit `--ignore` / allowlist entries.
- A failing test, lint finding, audit CVE, or red CI check is a real
  signal. Fix the underlying cause — bump the vulnerable dependency,
  correct the code, fix the type — do not mask it.
- A genuine false positive is the rare exception: document *why* inline
  with evidence next to the suppression. Suppression is never the default.

### Anti-overreach (PDF §10)

- No Timescale before Phase 4.
- No JWT/auth before Phase 6 (X-Operator-Id regex is the transitional gate
  in Phase 1).
- No PDF report generation.
- No external weather/NOTAM integrations before Phase 6.
- No additional real adapter beyond the Phase 5 MAVLink/PX4 path unless the
  current phase explicitly asks for it.
- No autonomy that isn't verifiable.
- Don't add features or refactors beyond the current phase. Three
  similar lines is better than a premature abstraction.

For the current demo-frozen state, these historical phase guards do not override
`docs/STATUS.md`: do not reopen completed demo/runtime scope merely because an
older phase instruction describes it as future work.

## Repository layout (current)

```
swarm/
├── core/swarm_core/           # shared types, geometry, voice, fsm primitives
├── swarm_os/                  # kernel package: state, fsm, scheduler, policy
├── orchestrator/swarm_orchestrator/  # central allocation + dispatch + groups
├── adapters/                  # thin execution boundary + vendor integrations
├── sim/swarm_sim/             # world + perception + runner
├── backend/app/               # FastAPI + WS + security middleware
├── frontend/                  # Next.js Console (the ONLY non-SwarmOS area)
├── infra/                     # postgres, redis, sites config
├── scripts/                   # development, demo and validation probes
├── docs/                      # architecture, evidence, ops, security, plans
├── tests/                     # cross-cutting tests (fuzz, e2e, load)
└── .github/                   # workflows, dependabot, codeql
```

## Standard make targets

```
make setup                # python venv + pnpm install
make bootstrap-auth-dev   # generate JWT secret + dev operators
make demo                 # boot sim + backend + frontend
make lint                 # ruff + mypy + tsc
make test                 # pytest + frontend tests
make audit                # pip-audit + pnpm audit + bandit + semgrep
make clean                # remove caches and node_modules
```

## Auth

Auth is in place: pure JWT HS256, three roles
(viewer < operator < commander), MFA mandatory for commander at login
and `mfa=true` claim re-checked on every commander-only call. Design
note: [`docs/security/auth.md`](docs/security/auth.md). Operator-store
schema + CLI helpers documented there too.

Local dev expects two pieces of state:

- `SWARM_JWT_SECRET` in `.env` (≥ 32 bytes).
- `infra/config/operators.yaml` (gitignored — the example template is
  at `infra/config/operators.example.yaml`).

`make bootstrap-auth-dev` provisions both idempotently. Protected endpoints use
`Authorization: Bearer <jwt>` (REST) or `?token=<jwt>` (WS).

## Branch + commit

- Develop on the branch named in the system reminder for the session.
- Never amend a previous commit; always create new commits.
- Commit messages should be terse and describe the scoped change.
- Do not create a PR unless the user asks for one.

## When the user asks you to start a new phase

1. Read [`docs/STATUS.md`](docs/STATUS.md) to confirm the current completed work.
2. Read the corresponding roadmap section.
3. Update STATUS.md with the new phase as `in_progress` when phase work is
   actually being started.
4. Execute the milestone exactly as scoped (no scope creep).
5. At the end, run the relevant gates, commit, push, and update STATUS.md with
   evidence rather than checklist claims.

## When the user asks for a readiness check (NEVER just trust STATUS.md)

A previous readiness check missed real blockers because it cross-referenced
STATUS.md to the code instead of actually running the phase end-to-end.
STATUS.md describes implemented/validated state, but readiness claims still need
the requested evidence. Follow this list:

1. **Re-run the requested gates from a clean state** when the user asks for a
   fresh readiness proof. A warm venv alone proves nothing.
2. **Exercise real infra when the claim depends on it.** SQLite/in-memory tests
   do not prove Timescale/Redis/PX4 behavior.
3. **Read scripts critically.** Failure-swallowing patterns are blockers.
4. **Verify config files are effective, not just present.**
5. **Check that dependencies are explicit, not just transitive.**
6. **Treat fresh-clone bootability as a meaningful contributor gate** when that
   is in scope.
7. **Cite evidence, not claims.** Bench documents and artifacts define the
   supported hardware/SITL claim boundary.
