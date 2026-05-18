# syntax=docker/dockerfile:1.7
# SwarmOS backend image (Phase 6.E).
#
# Multi-stage build:
#   1. `builder` — python:3.11-slim with uv. Resolves dependencies from
#      pyproject.toml + uv.lock with --frozen so a lockfile mismatch fails
#      the build (no silent drift between dev and image). The runtime
#      virtualenv is created at /opt/venv and copied into the runtime stage.
#   2. `runtime` — python:3.11-slim with a non-root user (uid 10001) and a
#      read-only-rootfs-compatible layout. EXPOSE 8765 (uvicorn).
#
# Hardening:
#   - Both stages pinned by sha256 digest (tag in comment for traceability).
#   - Runtime drops all root activity; entrypoint runs as `swarm` (uid 10001).
#   - Filesystem is read-only at runtime (compose/k8s mount tmpfs to /tmp).
#   - No build-essential / gcc / git in the runtime layer — only the venv.
#   - HEALTHCHECK uses /health (liveness); /ready is for orchestrator-level
#     readiness probes (k8s readinessProbe / compose depends_on).
#
# Build context: repo root. The .dockerignore at the root excludes tests,
# docs, frontend, node_modules, .venv, secrets, IaC dirs, etc.

# python:3.11-slim
FROM python@sha256:9a7765b36773a37061455b332f18e265e7f58f6fea9c419a550d2a8b0e9db834 AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_NO_CACHE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Build toolchain for native Python extensions in the builder stage only.
# `pymavlink` (Phase 5) ships a sdist that runs setup.py at install time
# and pulls `lxml` (libxml2 + libxslt headers needed). These packages
# never reach the runtime stage — the resolved venv is copied out via
# `COPY --from=builder /opt/venv` so the runtime image stays slim.
#
# uv itself is installed via pip from PyPI (pinned to 0.5.18 — matches
# the `astral-sh/setup-uv` version used by .github/workflows/test.yml's
# v8.1.0 default). Pip + a fixed version is simpler and more reliable
# than juggling a GHCR digest for the upstream `astral-sh/uv` image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "uv==0.5.18"

WORKDIR /build

# Resolve dependencies first so a code-only change doesn't bust the
# dependency layer. We need pyproject.toml + uv.lock; the readme is
# referenced by pyproject.toml so we copy it too to keep `uv sync` happy.
COPY pyproject.toml uv.lock README.md ./

# `--frozen` forbids lock regeneration; `--no-dev` skips test/lint tools;
# `--no-install-project` keeps the layer reusable until the source changes;
# `--extra mavlink` pulls pymavlink which the Phase 5 adapter needs.
# `UV_NO_CACHE=1` (set above) bypasses uv's local cache so we don't need
# a BuildKit cache-mount here — layer caching from docker/build-push-action
# (cache-from/cache-to type=gha) handles inter-build reuse.
RUN uv sync --frozen --no-dev --no-install-project --extra mavlink

# Now copy the source and install the project itself (editable=false).
COPY core/ ./core/
COPY swarm_os/ ./swarm_os/
COPY orchestrator/ ./orchestrator/
COPY adapters/ ./adapters/
COPY sim/ ./sim/
COPY backend/ ./backend/
COPY alembic.ini ./

RUN uv sync --frozen --no-dev --no-editable --extra mavlink

# ── runtime ─────────────────────────────────────────────────────────────────
# python:3.11-slim
FROM python@sha256:9a7765b36773a37061455b332f18e265e7f58f6fea9c419a550d2a8b0e9db834 AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    SWARM_ENV=prod

# Non-root user. uid 10001 is the convention we'll use across backend +
# frontend so volume mounts can be chowned consistently. /tmp must remain
# writable; readonly-rootfs deployments mount a tmpfs over it.
RUN groupadd --system --gid 10001 swarm \
 && useradd --system --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin swarm \
 && install -d -o swarm -g swarm /app /tmp \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Resolved virtualenv from the builder stage.
COPY --from=builder --chown=swarm:swarm /opt/venv /opt/venv

# Application source. We could `uv pip install .` but the editable layout
# under /app makes shell debugging easier and adds no measurable size.
COPY --from=builder --chown=swarm:swarm /build/core /app/core
COPY --from=builder --chown=swarm:swarm /build/swarm_os /app/swarm_os
COPY --from=builder --chown=swarm:swarm /build/orchestrator /app/orchestrator
COPY --from=builder --chown=swarm:swarm /build/adapters /app/adapters
COPY --from=builder --chown=swarm:swarm /build/sim /app/sim
COPY --from=builder --chown=swarm:swarm /build/backend /app/backend
COPY --from=builder --chown=swarm:swarm /build/alembic.ini /app/alembic.ini

WORKDIR /app
USER swarm

EXPOSE 8765

# /health is the liveness probe; /ready is the readiness probe (Phase 6.D).
# We use /health here because liveness must not fail just because Redis is
# briefly unavailable — orchestrators handle readiness separately.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8765/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8765"]
