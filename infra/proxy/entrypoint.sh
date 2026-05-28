#!/bin/sh
# Phase 6.E — nginx entrypoint for SwarmOS compose-prod.
#
# Two modes:
#   - TLS_MODE=letsencrypt (default): wait for the certbot sidecar to
#     drop /etc/letsencrypt/live/${TLS_SERVER_NAME}/fullchain.pem and
#     privkey.pem, then symlink them into /etc/nginx/ssl and start.
#   - TLS_MODE=self-signed: generate a 4096-bit RSA self-signed cert on
#     first boot. Lets a developer run `docker compose -f
#     docker-compose.prod.yml up` without ACME / a real domain. Production
#     deploys must use TLS_MODE=letsencrypt with a real DNS A record
#     pointing at this host.
#
# Certbot renewal requests arrive through a sentinel file on the shared
# /var/run/nginx volume. The reload itself stays inside this container's
# namespace.
set -eu

TLS_MODE="${TLS_MODE:-letsencrypt}"
TLS_SERVER_NAME="${TLS_SERVER_NAME:-}"
LE_LIVE_DIR="/etc/letsencrypt/live/${TLS_SERVER_NAME}"
NGINX_SSL_DIR="/etc/nginx/ssl"
RELOAD_SENTINEL="/var/run/nginx/reload.request"

mkdir -p "${NGINX_SSL_DIR}" /var/run/nginx

link_cert() {
    rm -f "${NGINX_SSL_DIR}/fullchain.pem" "${NGINX_SSL_DIR}/privkey.pem"
    ln -s "${LE_LIVE_DIR}/fullchain.pem" "${NGINX_SSL_DIR}/fullchain.pem"
    ln -s "${LE_LIVE_DIR}/privkey.pem"   "${NGINX_SSL_DIR}/privkey.pem"
}

case "${TLS_MODE}" in
    self-signed)
        echo "[entrypoint] TLS_MODE=self-signed — generating dev cert"
        if [ ! -s "${NGINX_SSL_DIR}/fullchain.pem" ]; then
            openssl req -x509 -nodes -newkey rsa:4096 \
                -days 30 \
                -keyout "${NGINX_SSL_DIR}/privkey.pem" \
                -out    "${NGINX_SSL_DIR}/fullchain.pem" \
                -subj "/CN=${TLS_SERVER_NAME:-localhost}/O=SwarmOS/O=dev"
            chmod 600 "${NGINX_SSL_DIR}/privkey.pem"
        fi
        ;;
    letsencrypt)
        if [ -z "${TLS_SERVER_NAME}" ]; then
            echo "[entrypoint] FATAL: TLS_SERVER_NAME must be set when TLS_MODE=letsencrypt" >&2
            exit 1
        fi
        echo "[entrypoint] TLS_MODE=letsencrypt — waiting for cert at ${LE_LIVE_DIR}"
        # The certbot sidecar runs `certbot certonly --webroot` on first
        # boot. We poll instead of blocking so a fresh deploy can
        # eventually become healthy.
        for i in $(seq 1 60); do
            if [ -s "${LE_LIVE_DIR}/fullchain.pem" ] && [ -s "${LE_LIVE_DIR}/privkey.pem" ]; then
                link_cert
                break
            fi
            sleep 5
        done
        if [ ! -e "${NGINX_SSL_DIR}/fullchain.pem" ]; then
            echo "[entrypoint] FATAL: cert never appeared in 5 min — check certbot logs" >&2
            exit 1
        fi
        ;;
    *)
        echo "[entrypoint] FATAL: unknown TLS_MODE=${TLS_MODE} (expected self-signed|letsencrypt)" >&2
        exit 1
        ;;
esac

watch_reload_requests() {
    last_seen=""
    while :; do
        sleep 5
        if [ ! -s "${RELOAD_SENTINEL}" ]; then
            continue
        fi
        current="$(cat "${RELOAD_SENTINEL}" 2>/dev/null || true)"
        if [ -z "${current}" ] || [ "${current}" = "${last_seen}" ]; then
            continue
        fi
        last_seen="${current}"
        echo "[entrypoint] cert reload requested"
        link_cert 2>/dev/null || true
        nginx -s reload || echo "[entrypoint] nginx reload failed" >&2
    done
}

# Syntax check first so a config typo fails fast.
nginx -t

watch_reload_requests &

echo "[entrypoint] starting nginx"
exec nginx -g "daemon off;"
