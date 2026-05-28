#!/usr/bin/env bash
# Generate local-only infrastructure secrets in .env.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  cp .env.example "$ENV_FILE"
  echo "[bootstrap-dev-env] created .env from .env.example"
fi

random_hex() {
  python3 -c 'import secrets; print(secrets.token_hex(24))'
}

url_quote() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

get_env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true
}

set_env_value() {
  local key="$1"
  local value="$2"
  local escaped
  escaped="$(printf '%s' "$value" | sed 's/[&|\\]/\\&/g')"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i.bak "s|^${key}=.*$|${key}=${escaped}|" "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

ensure_value() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(get_env_value "$key")"
  if [ -z "$value" ]; then
    set_env_value "$key" "$fallback"
  fi
}

postgres_password="$(get_env_value POSTGRES_PASSWORD)"
if [ -z "$postgres_password" ] || [ "$postgres_password" = "swarm" ]; then
  postgres_password="$(random_hex)"
  set_env_value POSTGRES_PASSWORD "$postgres_password"
  echo "[bootstrap-dev-env] generated local POSTGRES_PASSWORD"
fi

redis_password="$(get_env_value REDIS_PASSWORD)"
if [ -z "$redis_password" ] || [ "$redis_password" = "swarm" ]; then
  redis_password="$(random_hex)"
  set_env_value REDIS_PASSWORD "$redis_password"
  echo "[bootstrap-dev-env] generated local REDIS_PASSWORD"
fi

ensure_value POSTGRES_USER swarm
ensure_value POSTGRES_DB swarm
ensure_value POSTGRES_HOST localhost
ensure_value POSTGRES_PORT 5432
ensure_value REDIS_HOST localhost
ensure_value REDIS_PORT 6379
ensure_value REDIS_DB 0
ensure_value SWARM_ALLOWED_ORIGINS http://localhost:3000

postgres_user="$(get_env_value POSTGRES_USER)"
postgres_db="$(get_env_value POSTGRES_DB)"
postgres_host="$(get_env_value POSTGRES_HOST)"
postgres_port="$(get_env_value POSTGRES_PORT)"
redis_host="$(get_env_value REDIS_HOST)"
redis_port="$(get_env_value REDIS_PORT)"
redis_db="$(get_env_value REDIS_DB)"
postgres_password_url="$(url_quote "$postgres_password")"
redis_password_url="$(url_quote "$redis_password")"

set_env_value DATABASE_URL "postgresql+asyncpg://${postgres_user}:${postgres_password_url}@${postgres_host}:${postgres_port}/${postgres_db}"
set_env_value REDIS_URL "redis://:${redis_password_url}@${redis_host}:${redis_port}/${redis_db}"

echo "[bootstrap-dev-env] .env is ready for local docker compose"
