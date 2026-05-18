# SwarmOS Console image (Phase 6.E).
#
# Multi-stage build:
#   1. `deps` — node:24-alpine, installs pnpm via corepack with the
#      lockfile frozen and `--ignore-scripts` (no postinstall arbitrary
#      execution; matches `frontend/.npmrc`).
#   2. `builder` — runs `pnpm build` (Next.js standalone output).
#   3. `runtime` — node:24-alpine running the prebuilt standalone server
#      as non-root (uid 1001:1001). Read-only rootfs compatible; /tmp is
#      a writable tmpfs mount in compose / k8s.
#
# Hardening:
#   - All stages digest-pinned (tag in comment).
#   - corepack uses the version pinned in package.json (pnpm@11.1.2).
#   - --frozen-lockfile + --ignore-scripts at every pnpm step.
#   - Final image carries only `.next/standalone`, `.next/static`, and
#     `public/` — no node_modules tree, no source maps for `next dev`,
#     no devDependencies.
#
# Build context: repo root. The frontend tree under `frontend/` is the
# only thing this image cares about; the .dockerignore excludes the rest.

# node:24-alpine
FROM node@sha256:d1b3b4da11eefd5941e7f0b9cf17783fc99d9c6fc34884a665f40a06dbdfc94f AS deps

# corepack is shipped with node:24 but disabled by default. Enable it and
# pin pnpm via package.json `packageManager`.
RUN corepack enable

WORKDIR /build/frontend

# Lockfile-only first for layer reuse on source-only changes. The pnpm
# workspace file is read by pnpm during install.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.npmrc frontend/.pnpmfile.cjs ./

RUN corepack pnpm install --frozen-lockfile --ignore-scripts

# ── builder ─────────────────────────────────────────────────────────────────
# node:24-alpine
FROM node@sha256:d1b3b4da11eefd5941e7f0b9cf17783fc99d9c6fc34884a665f40a06dbdfc94f AS builder

RUN corepack enable

WORKDIR /build/frontend

COPY --from=deps /build/frontend/node_modules ./node_modules
COPY frontend/ ./

# next.config.mjs sets `output: "standalone"` (see config). Build emits
# `.next/standalone/server.js` + `.next/static/`. `public/` is optional in
# Next.js; ensure it exists so the runtime COPY layer is unconditional.
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN mkdir -p ./public && corepack pnpm build

# ── runtime ─────────────────────────────────────────────────────────────────
# node:24-alpine
FROM node@sha256:d1b3b4da11eefd5941e7f0b9cf17783fc99d9c6fc34884a665f40a06dbdfc94f AS runtime

# node:24-alpine already ships a `node` user (uid 1000); we add a dedicated
# `swarm` uid 1001 to match the backend uid convention pattern (10001 there;
# the Console image stays under 65535 so musl is happy).
RUN addgroup --system --gid 1001 swarm \
 && adduser --system --uid 1001 --ingroup swarm --shell /sbin/nologin swarm \
 && mkdir -p /app /tmp \
 && chown -R swarm:swarm /app /tmp

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Standalone Next bundle. .next/standalone contains its own minimal
# node_modules subset; .next/static and public/ must be copied separately.
COPY --from=builder --chown=swarm:swarm /build/frontend/.next/standalone ./
COPY --from=builder --chown=swarm:swarm /build/frontend/.next/static ./.next/static
COPY --from=builder --chown=swarm:swarm /build/frontend/public ./public

USER swarm

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
