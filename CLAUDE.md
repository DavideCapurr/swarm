# SWARM / SwarmOS — context for Claude Code sessions

This file is read automatically by Claude Code at the start of every session
in this repo. Read it first, then act according to the rules below.

## What this product is

- **SWARM** — the brand/project. The wordmark is uppercase. Repo path: `swarm/`.
- **SwarmOS** — the **product**: the autonomous operating layer that
  decides, plans, and coordinates the drone fleet. SwarmOS is the source of
  operational truth. **SwarmOS is the entire backend of this repo**: every
  directory except `frontend/` is part of SwarmOS (`core/`, `swarm_os/`,
  `orchestrator/`, `adapters/`, `sim/`, `backend/`, `infra/`, `scripts/`).
- **Console** — the operator-facing surface. It lives **only** in
  `frontend/`. Console renders state and sends intent. Console **never
  decides**.
- **operator** — the human using the Console. Sends intents
  (`/actions/verify`, `/actions/hold-patrol`), never manual drone commands.

## The hard rule

**SwarmOS decides. Console supervises.** No UI ever invents operational
truth. Every number on screen comes from SwarmOS or the honest simulator.
Any field temporarily derived client-side must be flagged `derived: true`
and rendered with the eyebrow `DERIVED`.

## Source of truth for this project

The full development plan covering Phase 0 → Phase 6 lives at
[`docs/plan/swarmos-roadmap.md`](docs/plan/swarmos-roadmap.md).
Current execution status lives at [`docs/STATUS.md`](docs/STATUS.md). When
starting a session, read STATUS first to see which phase is current and
what's pending.

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
- **No fake video.** `LiveFeedFrame` renders `UNIT 003 VIEWPORT PENDING`
  or `STREAM OFFLINE`. Never a stock clip.
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

## Repository layout (current)

```
swarm/
├── core/swarm_core/           # shared types, geometry, voice, fsm primitives
├── swarm_os/                  # Phase 1+ kernel package (state, fsm, scheduler, …)
├── orchestrator/swarm_orchestrator/  # auction + dispatch loop
├── adapters/                  # base + simulated + vendor stubs
├── sim/swarm_sim/             # world + perception + runner
├── backend/app/               # FastAPI + WS + security middleware
├── frontend/                  # Next.js Console (the ONLY non-SwarmOS area)
├── infra/                     # postgres, redis, sites config
├── scripts/                   # dev_up.sh, demo_wildfire.sh
├── docs/                      # plan, security, ops, operator, compliance, dev
├── tests/                     # cross-cutting tests (fuzz, e2e, load)
└── .github/                   # workflows, dependabot, codeql
```

## Standard make targets

```
make setup                # python venv + pnpm install
make bootstrap-auth-dev   # Phase 6.C — generate JWT secret + dev operators
make demo                 # boot sim + backend + frontend
make lint                 # ruff + mypy + tsc
make test                 # pytest + frontend tests
make audit                # pip-audit + pnpm audit + bandit + semgrep
make clean                # remove caches and node_modules
```

## Auth (Phase 6.C)

Auth is in place since Phase 6.C: pure JWT HS256, three roles
(viewer < operator < commander), MFA mandatory for commander at login
and `mfa=true` claim re-checked on every commander-only call. Design
note: [`docs/security/auth.md`](docs/security/auth.md). Operator-store
schema + CLI helpers documented there too.

Local dev expects two pieces of state:

- `SWARM_JWT_SECRET` in `.env` (≥ 32 bytes).
- `infra/config/operators.yaml` (gitignored — the example template is
  at `infra/config/operators.example.yaml`).

`make bootstrap-auth-dev` provisions both idempotently. The transitional
`X-Operator-Id` header gate (Phase 1) and the `X-Admin-Token` gate
(Phase 6.B) are gone — anything that touches a protected endpoint must
go through `Authorization: Bearer <jwt>` (REST) or `?token=<jwt>` (WS).

## Branch + commit

- Develop on the branch named in the system reminder for the session.
- Never push to `main`.
- Never amend a previous commit; always create new commits.
- Commit messages: `phase-N: <short subject>` where N is the phase number.
- Do not create a PR unless the user asks for one.

## When the user asks you to start a new phase

1. Read [`docs/STATUS.md`](docs/STATUS.md) to confirm the current
   completed phase.
2. Read the corresponding section of
   [`docs/plan/swarmos-roadmap.md`](docs/plan/swarmos-roadmap.md).
3. Update STATUS.md with the new phase as `in_progress`.
4. Execute the milestone exactly as scoped (no scope creep).
5. At the end of the phase, run `make lint && make test && make audit`,
   commit, push, and update STATUS.md with the phase as `done`.

## When the user asks for a readiness check on a phase (NEVER just trust STATUS.md)

A previous readiness check missed real Phase 4 blockers because it
cross-referenced STATUS.md to the code instead of actually running the
phase end-to-end. STATUS.md describes what was implemented, **not what
works**. Follow this list every time the user asks "is phase N ready?":

1. **Re-run the gates from a clean state**, not from a warm venv. If `.venv`
   already exists, that proves nothing — a transitive dep may have been
   installed by accident. Use `rm -rf .venv && make setup` then
   `make lint && make test && make audit`.
2. **Exercise the real infra, not just SQLite/in-memory stubs.** For Phase 4+
   spin up `docker compose up -d postgres redis`, run
   `alembic upgrade head` against the live Timescale container, and
   verify the schema actually applies. SQLite-only tests **do not** catch
   dialect-specific failures (Timescale unique-index rules, asyncpg SSL,
   redis ACLs, etc.).
3. **Read scripts critically.** `|| echo "continuing"`, `|| true`,
   `--no-verify`, and other failure-swallowing patterns are blockers — flag
   them. The same goes for `try/except: pass` in startup paths.
4. **Verify config files are effective, not just present.** Examples:
   `pnpm config get <key>` from inside the relevant dir, `psql -c '\d'`
   to confirm a table really has the constraints the migration claims,
   `python -c "import x"` to confirm an extra was actually pulled.
5. **Check that dependencies are explicit, not just transitive.** Run a
   `make setup` in a fresh worktree on a different machine if possible;
   an env where the lib "happens to be there" hides a missing dep.
6. **The phase is ready only if a fresh clone can boot the next phase.**
   Treat the gate as "would a new contributor running `git clone && make
   setup && make demo` get to the next phase's starting line?", not "is
   the checklist ticked?".
7. **Cite evidence, not claims.** When reporting readiness, quote the
   command output (`make test → 225 passed`), not the STATUS.md line. If
   you didn't run a real Timescale container, say so.
