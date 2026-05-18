.PHONY: setup setup-python setup-frontend lint test test-python test-frontend sim backend frontend demo audit audit-python audit-frontend audit-bandit audit-pymavlink-integrity phase5-sitl-gate bootstrap-auth-dev clean db-migrate db-revision docker-build docker-build-backend docker-build-frontend docker-build-backup helm-template helm-lint backup-dump-dry

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

# ── lint & test ─────────────────────────────────────────────────────────────
lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy core adapters orchestrator sim backend swarm_os
	cd frontend && corepack pnpm typecheck

test: test-python test-frontend

test-python:
	$(VENV)/bin/pytest -q --cov=core --cov=adapters --cov=orchestrator --cov=swarm_os

test-frontend:
	cd frontend && corepack pnpm typecheck

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

# ── security audit ──────────────────────────────────────────────────────────
# `make audit` is the one-stop check before pushing. It mirrors what CI runs
# under .github/workflows/sast.yml + secret-scanning.yml + image-scan.yml +
# dependency-review.yml. Locally we skip image-scan (needs Docker daemon).
audit: audit-python audit-frontend audit-bandit audit-pymavlink-integrity

audit-python:
	$(VENV)/bin/pip-audit --skip-editable --cache-dir .cache/pip-audit

audit-frontend:
	cd frontend && corepack pnpm audit --audit-level=high

audit-bandit:
	$(VENV)/bin/bandit -r core adapters orchestrator sim backend swarm_os \
		--severity-level medium \
		--skip B101,B311

audit-pymavlink-integrity:
	$(PYTHON) scripts/verify_pymavlink_integrity.py

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

# ── cleanup ─────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	cd frontend && rm -rf node_modules .next
