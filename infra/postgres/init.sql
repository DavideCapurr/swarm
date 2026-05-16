-- SWARM OS — Postgres extensions only.
--
-- Phase 4 moved schema ownership to Alembic (`backend/app/db/migrations/`).
-- This file now only enables the extensions Alembic depends on. On first
-- backend boot, `alembic upgrade head` creates every table — including the
-- Timescale hypertables for `telemetry` and `events`, plus the 30-day
-- retention policy on `telemetry`.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
