#!/bin/sh
# Phase 6.E — Let's Encrypt renewal loop for SwarmOS compose-prod.
#
# Runs inside the certbot sidecar (certbot/certbot:v3.1.0). Cycle:
#   1. On first boot, request a cert via HTTP-01 webroot challenge if one
#      is not already present.
#   2. Every 12 h, run `certbot renew` (no-op when nothing is near expiry).
#   3. After a successful renew, signal nginx (the sibling container) to
#      pick up the new fullchain via SIGHUP. The sidecar shares the
#      docker network with nginx; we use docker's own DNS by sending
#      SIGHUP via the shared /var/run/nginx.pid sentinel file rather
#      than the docker socket (which we deliberately do not mount —
#      threat model §S2).
#
# Required env:
#   - TLS_SERVER_NAME: e.g. swarmos.example.com (cert subject + ACME order)
#   - TLS_EMAIL:       email registered with Let's Encrypt
#   - TLS_STAGING=1    (optional) use staging ACME endpoint for testing
set -eu

if [ -z "${TLS_SERVER_NAME:-}" ] || [ -z "${TLS_EMAIL:-}" ]; then
    echo "[certbot] FATAL: TLS_SERVER_NAME and TLS_EMAIL must be set" >&2
    exit 1
fi

STAGING_FLAG=""
if [ "${TLS_STAGING:-0}" = "1" ]; then
    STAGING_FLAG="--staging"
    echo "[certbot] using Let's Encrypt STAGING (test certs only)"
fi

WEBROOT="/var/www/certbot"
mkdir -p "${WEBROOT}"

issue_or_skip() {
    if [ -s "/etc/letsencrypt/live/${TLS_SERVER_NAME}/fullchain.pem" ]; then
        echo "[certbot] cert already present for ${TLS_SERVER_NAME} — skip initial issue"
        return 0
    fi
    echo "[certbot] requesting initial cert for ${TLS_SERVER_NAME}"
    certbot certonly \
        --webroot \
        --webroot-path "${WEBROOT}" \
        --non-interactive \
        --agree-tos \
        --email "${TLS_EMAIL}" \
        --domains "${TLS_SERVER_NAME}" \
        --rsa-key-size 4096 \
        ${STAGING_FLAG}
}

reload_nginx() {
    # The nginx container runs an entrypoint that traps SIGHUP and re-links
    # the cert + reloads itself. We send SIGHUP via the nginx-pid shared
    # volume (no docker socket exposed to the certbot container).
    if [ -s "/var/run/nginx/nginx.pid" ]; then
        nginx_pid=$(cat /var/run/nginx/nginx.pid)
        # `kill` exists in the alpine-based certbot image; busybox provides it.
        kill -HUP "${nginx_pid}" 2>/dev/null || \
            echo "[certbot] could not signal nginx pid ${nginx_pid} — manual reload required"
    else
        echo "[certbot] /var/run/nginx/nginx.pid missing — skip reload (will pick up on next nginx start)"
    fi
}

# Initial issue (idempotent).
issue_or_skip

# Renewal loop. certbot's own scheduler is meant for systemd; in a
# container we do a simple sleep loop.
while :; do
    sleep 43200  # 12 h
    echo "[certbot] running renew"
    if certbot renew --quiet --webroot --webroot-path "${WEBROOT}"; then
        reload_nginx
    else
        echo "[certbot] renew failed; will retry next cycle" >&2
    fi
done
