.PHONY: setup setup-python setup-frontend setup-cv lint test test-python test-frontend test-cv sim backend frontend demo demo-wildfire-sim demo-intrusion-sim demo-search-sim audit audit-python audit-frontend audit-bandit audit-pymavlink-integrity audit-cv-integrity phase5-sitl-gate bootstrap-auth-dev clean db-migrate db-revision docker-build docker-build-backend docker-build-frontend docker-build-backup helm-template helm-lint backup-dump-dry backup-drill load-smoke load-soak chaos-redis chaos-backend cv-generate-fixtures

PY := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python
UV := uv

# ── setup ───────────────────────────────────────────────────────────────────
setup: setup-python setup-frontend

setup-python:
	$(UV) sync --frozen --extra dev --extra mavlink --extra dji --python $(PY)

setup-frontend:
	# `--ignore-scripts` is belt-and-suspenders alongside `frontend/.npmrc`:
	# blocks postinstall lifecycle scripts from npm packages so a malicious
	# transitive dep can't execute code at install time (threat model §S3).
	cd frontend && corepack pnpm install --frozen-lockfile --ignore-scripts

# Phase 7.D — opt-in CV runtime. Adds ultralytics + torch + opencv-headless
# + Pillow + numpy on top of the default dev env. NOT pulled by `make setup`
# because the wheels are ~2 GB and 99% of contributors never opt into CV.
# Pairs with `make test-cv` and `make audit-cv-integrity`.
setup-cv:
	$(UV) sync --frozen --extra dev --extra mavlink --extra dji --extra cv --python $(PY)

# ── lint & test ─────────────────────────────────────────────────────────────
lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy core adapters orchestrator sim backend swarm_os
	cd frontend && corepack pnpm typecheck

test: test-python test-frontend

test-python:
	# Phase 6.J — backend in coverage scope at the 80% gate. Load + chaos
	# samples are deselected because coverage instrumentation distorts
	# the latency p95 they assert on; the dedicated `load-smoke` /
	# `chaos-*` targets run them without coverage.
	# Phase 7.D — `cv_baseline` / `cv_baseline_realistic` deselected by
	# default; they require the opt-in `[cv]` extra and run via
	# `make test-cv`.
	$(VENV)/bin/pytest -q -m "not load_smoke and not chaos and not cv_baseline and not cv_baseline_realistic" \
		--cov=core --cov=adapters --cov=orchestrator --cov=swarm_os --cov=backend \
		--cov-report=term-missing --cov-fail-under=80

test-frontend:
	cd frontend && corepack pnpm typecheck
	cd frontend && corepack pnpm test

# Phase 7.D — CV baseline suite. Requires `make setup-cv` first. Runs
# the tests marked `cv_baseline` (and, when reference samples are cached,
# the `cv_baseline_realistic` subset). The default `make test` deselects
# both markers so a contributor without the `cv` extra never sees a
# spurious failure.
test-cv:
	$(VENV)/bin/pytest sim/swarm_sim/cv/tests -q -m "cv_baseline or cv_baseline_realistic"

# ── run ─────────────────────────────────────────────────────────────────────
infra:
	docker compose up -d postgres redis

backend: infra db-migrate
	$(VENV)/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8765

# ── database migrations (Phase 4) ───────────────────────────────────────────
# db-migrate runs `alembic upgrade head` against the URL in $DATABASE_URL.
# db-revision <message="…"> generates a new migration file from model diffs.
db-migrate:
	$(VENV)/bin/alembic upgrade head

db-revision:
	$(VENV)/bin/alembic revision --autogenerate -m "$(message)"

frontend:
	cd frontend && corepack pnpm dev

sim:
	$(PYTHON) -m sim.swarm_sim.runner

orchestrator:
	$(PYTHON) -m orchestrator.swarm_orchestrator.service

demo:
	@./scripts/demo_wildfire.sh

# Phase 7.E — one-command boot of each MVP scenario. Each target loads its
# YAML via SIM_SCENARIO (sim runner enables autonomy baseline + opt-in CV
# from the YAML itself) and launches scripts/scenario_metrics.py in the
# background to snapshot the audit log into docs/bench/artifacts/.
demo-wildfire-sim:
	@./scripts/demo_scenario.sh sim/scenarios/wildfire_owner_land.yaml --metrics

demo-intrusion-sim:
	@./scripts/demo_scenario.sh sim/scenarios/intrusion_owner_land.yaml --metrics

demo-search-sim:
	@./scripts/demo_scenario.sh sim/scenarios/search_owner_land.yaml --metrics

# ── security audit ──────────────────────────────────────────────────────────
# `make audit` is the one-stop check before pushing. It mirrors what CI runs
# under .github/workflows/sast.yml + secret-scanning.yml + image-scan.yml +
# dependency-review.yml. Locally we skip image-scan (needs Docker daemon).
audit: audit-python audit-frontend audit-bandit audit-pymavlink-integrity audit-cv-integrity

audit-python:
	# PYSEC-2025-183 (pyjwt 2.12.1, "weak encryption"): disputed by supplier,
	# no fix version published. SwarmOS enforces SWARM_JWT_SECRET >= 32 bytes
	# via `make bootstrap-auth-dev` (CLAUDE.md §Auth) so the weakness premise
	# does not apply. Re-evaluate at every dependabot bump.
	$(VENV)/bin/pip-audit --skip-editable --cache-dir .cache/pip-audit \
		--ignore-vuln PYSEC-2025-183

audit-frontend:
	cd frontend && corepack pnpm audit --audit-level=high

audit-bandit:
	$(VENV)/bin/bandit -r core adapters orchestrator sim backend swarm_os \
		--severity-level medium \
		--skip B101,B311

audit-pymavlink-integrity:
	$(PYTHON) scripts/verify_pymavlink_integrity.py

# Phase 7.D — CV asset integrity. Always-on (no [cv] extra required):
# the gate verifies the manifest schema + the sha256 of every committed
# fixture against fixtures/LICENSES.md, fully offline. If the `[cv]`
# extra IS installed it also re-verifies any cached weights / samples.
audit-cv-integrity:
	$(PY) scripts/verify_cv_assets_integrity.py

# Phase 7.D — regenerate the synthetic CC0 placeholder fixtures. Only
# writes files that do NOT already exist, so a real Pexels/Unsplash
# frame dropped in by an operator is never overwritten. After running,
# update the row in fixtures/LICENSES.md if anything was created.
cv-generate-fixtures:
	$(PY) sim/swarm_sim/cv/fixtures/_generate.py

phase5-sitl-gate:
	$(PYTHON) scripts/phase5_sitl_probe.py \
		--connection "$${MAVLINK_CONNECTION:-udp:localhost:14540}" \
		--agent-id "$${MAVLINK_AGENT_ID:-mav-px4-sitl}"

# ── auth bootstrap (Phase 6.C, dev only) ────────────────────────────────────
# One-shot: generate a JWT secret + write infra/config/operators.yaml with
# three local accounts (viewer / operator / commander, password swarm-dev).
# Idempotent — never overwrites an existing operators.yaml or a non-empty
# SWARM_JWT_SECRET. NEVER use in staging / production: drone-day §2.C
# documents the real provisioning flow.
bootstrap-auth-dev:
	@./scripts/bootstrap_auth_dev.sh

# ── deploy / images (Phase 6.E) ─────────────────────────────────────────────
# Local image builds — the same Dockerfiles CI uses. Tags are `:dev` for
# local builds; CI tags are managed by docker/metadata-action on tag push.
docker-build: docker-build-backend docker-build-frontend docker-build-backup

docker-build-backend:
	docker build -t swarmos-backend:dev -f backend/Dockerfile .

docker-build-frontend:
	docker build -t swarmos-frontend:dev -f frontend/Dockerfile .

docker-build-backup:
	docker build -t swarmos-backup:dev -f infra/backup/Dockerfile infra/backup

# Helm template render against the vineyard-01 overlay. `kubectl apply
# --dry-run=client` validates that every rendered manifest is schema-valid
# and would be accepted by the apiserver. Both `helm` and `kubectl` must
# be on PATH (drone-day §2.E lists install commands).
helm-template:
	helm template infra/helm/swarmos \
		-f infra/helm/swarmos/values-vineyard-01.yaml \
		--namespace swarmos \
		| kubectl apply --dry-run=client -f -

helm-lint:
	helm lint infra/helm/swarmos -f infra/helm/swarmos/values-vineyard-01.yaml

# Backup dry-run: spins a throwaway sqlite-equivalent via pg_dump --schema-only
# against a postgres container if available. The full path is exercised in
# the integration test backend/tests/test_backup_script.py — this target is
# the ops-side smoke. Skipped if pg_dump is not on PATH.
backup-dump-dry:
	@if ! command -v pg_dump >/dev/null 2>&1; then \
		echo "[backup-dump-dry] pg_dump not installed — skipping (see drone-day §2.E)"; \
		exit 0; \
	fi
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "[backup-dump-dry] DATABASE_URL not set — skipping"; \
		exit 0; \
	fi
	@echo "[backup-dump-dry] dry-running pg_dump --schema-only against $$DATABASE_URL"
	@pg_dump --schema-only "$$DATABASE_URL" >/dev/null && echo "OK"

# Phase 6.G — monthly backup/restore drill. Boots a sidecar Postgres,
# runs the prod backup script against $DATABASE_URL, restores into the
# sidecar, asserts schema parity via Alembic. Drone-day §2.G expects
# this to run monthly and upload artifacts off-site. Requires docker on
# PATH; gracefully degrades if Alembic is missing.
backup-drill:
	@./scripts/backup_restore_drill.sh

# ── load + chaos (Phase 6.F) ────────────────────────────────────────────────
# `load-smoke` runs the in-process pytest assertions (50-agent x 1 Hz x 5 s
# WS p95 < 200 ms, REST p95 < 100 ms, 200-unit burst rate-limiter drops).
# Cheap enough for every push; CI also runs it under .github/workflows/test.yml.
load-smoke:
	$(VENV)/bin/pytest tests/load -m load_smoke -q

# `load-soak` is the out-of-process driver: 500 msg/s x 5 min against a live
# backend + redis. Used by the weekly load-test workflow. Requires
# `make infra && make backend && make bootstrap-auth-dev` first.
load-soak:
	$(PYTHON) -m tests.load.driver --rate 500 --duration 300

# Chaos drills. Manual; not run by `make test`. Each script asserts the
# Phase 6.F SLO numerically and exits non-zero on breach.
chaos-redis:
	@./scripts/chaos/redis_pause.sh

chaos-backend:
	@./scripts/chaos/backend_kill.sh

# ── cleanup ─────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	cd frontend && rm -rf node_modules .next
