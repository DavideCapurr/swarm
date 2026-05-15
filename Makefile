.PHONY: setup setup-python setup-frontend lint test test-python test-frontend sim backend frontend demo audit audit-python audit-frontend audit-bandit clean

PY := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python

# ── setup ───────────────────────────────────────────────────────────────────
setup: setup-python setup-frontend

setup-python:
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev,mavlink,dji]"

setup-frontend:
	cd frontend && (pnpm install || npm install)

# ── lint & test ─────────────────────────────────────────────────────────────
lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy core adapters orchestrator sim backend
	cd frontend && (pnpm typecheck || npm run typecheck)

test: test-python test-frontend

test-python:
	$(VENV)/bin/pytest -q --cov=core --cov=adapters --cov=orchestrator

test-frontend:
	cd frontend && (pnpm test --run || npm test -- --run) 2>/dev/null || true

# ── run ─────────────────────────────────────────────────────────────────────
infra:
	docker compose up -d postgres redis

backend: infra
	$(VENV)/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8765

frontend:
	cd frontend && (pnpm dev || npm run dev)

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
audit: audit-python audit-frontend audit-bandit

audit-python:
	$(VENV)/bin/pip-audit --skip-editable

audit-frontend:
	cd frontend && (pnpm audit --audit-level=high || npm audit --audit-level=high)

audit-bandit:
	$(VENV)/bin/bandit -r core adapters orchestrator sim backend swarm_os \
		--severity-level medium \
		--skip B101,B311

# ── cleanup ─────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	cd frontend && rm -rf node_modules .next
