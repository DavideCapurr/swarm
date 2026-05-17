# SwarmOS — code & process conventions

Short, prescriptive. If a rule conflicts with [`CLAUDE.md`](../CLAUDE.md),
CLAUDE.md wins (it's the front door).

## Python

- **3.11+**. Pinned via `pyproject.toml` `requires-python = ">=3.11"`.
- **Pydantic v2** for every domain message. New models use
  `ConfigDict(extra="forbid", strict=True)` unless they need looser
  parsing for performance reasons (document why if so).
- **FastAPI** for HTTP. Every body/query/path param goes through Pydantic.
- **Ruff** for lint + format. Config in `pyproject.toml`. No exceptions.
- **Mypy strict** for type checking. New code must pass
  `mypy --strict`.
- **structlog** for logging. JSON output, correlation IDs, never PII.
- **No `print()`** in shipped code. Use the logger.
- **No bare `except:`** Catch specific exceptions or `Exception` with a
  reason comment.
- **No `time.sleep()`** in async code. Use `asyncio.sleep()`.
- **datetime**: always tz-aware, default UTC via the `_now()` helper in
  `core/swarm_core/messages.py`.

## TypeScript / React

- **TypeScript strict**. `tsconfig.json` has `strict: true`.
- **No `any`** without a `// reason:` comment.
- **Functional components** + hooks only. No class components.
- **React 19 + Next.js 16** App Router. No Pages Router.
- **No `dangerouslySetInnerHTML`** ever.
- **No `eval`, `Function(...)`, `setTimeout(string)`**.
- **No inline styles** unless dynamic (use Tailwind classes).
- **Tailwind**: tokens from `frontend/lib/tokens.ts`. No arbitrary
  hex colors.
- **No external chart/modal/toast/snackbar libraries.**

## Security

- **Never commit secrets.** `.env*` is gitignored except `.env.example`.
- **No hard-coded URLs** for production endpoints. Use env vars.
- **Validate at boundaries** (HTTP body, WS message, file content, env
  vars). Trust internal code.
- **Never echo unvalidated user input** into logs, events, or responses.
- **Use `secrets`** module for randomness, not `random`.
- **Parameterized SQL only.** No string concatenation into queries.
- **Pin dependencies** with exact versions in lockfiles. PR review for
  any version bump.

## Commit messages

Format: `phase-N: <imperative subject under 70 chars>`

Examples:
```
phase-0: lock CORS to env-driven allowlist + enforce WS origin
phase-1: project Telemetry+FleetState into SwarmState.units
phase-3: drop DERIVED flags, compute mode server-side
```

Body (optional) explains the **why**, not the **what**. The diff shows
the what.

## Branches

- One branch per feature/phase. Branch name set by the user/system.
- Never push to `main`.
- Never force-push.
- Never amend a previously-pushed commit.

## PRs

- **Do not open a PR unless the user asks.** Push to the working branch
  and stop.
- When the user does ask, follow `gh pr create` with a template summary +
  test plan.

## Tests

- **Unit tests next to the code** (`<module>/tests/test_*.py`).
- **Integration / e2e / load / fuzz** under top-level `tests/`.
- Coverage targets per phase declared in
  [`docs/plan/swarmos-roadmap.md`](plan/swarmos-roadmap.md).
- Tests run via `make test`. CI runs `make lint && make test && make
  audit`.

## Documentation

- Architectural decisions go in `docs/architecture/adr/<NNN>-<slug>.md`.
- Operational runbooks in `docs/ops/`.
- Operator-facing docs in `docs/operator/`.
- Security docs in `docs/security/`.
- Compliance docs in `docs/compliance/`.
- Dev onboarding in `docs/dev/`.

## What we do NOT do

- We do **not** add comments that describe what the code does (the code
  does that). We add comments only when the *why* is non-obvious.
- We do **not** create docs unless the user asks or the plan requires
  them.
- We do **not** add backwards-compat shims unless the user explicitly
  asks.
- We do **not** invent operational truth in the UI.
- We do **not** skip security to land a feature.
- We do **not** use emojis in code or commits.
