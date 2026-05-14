-- SWARM OS — initial Postgres + TimescaleDB schema.
-- Loaded by the postgres container's entrypoint on first boot.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Fleet ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    vendor      TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Anomalies ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS anomalies (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    alt_m         DOUBLE PRECISION DEFAULT 0,
    confidence    REAL NOT NULL,
    source_agent  TEXT,
    verified      BOOLEAN NOT NULL DEFAULT false,
    ts            TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS anomalies_ts_idx ON anomalies (ts DESC);

-- ── Missions ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS missions (
    id              TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    params          JSONB NOT NULL,
    priority        INTEGER NOT NULL,
    assigned_agent  TEXT,
    deadline        TIMESTAMPTZ,
    ts              TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS missions_ts_idx ON missions (ts DESC);

-- ── Telemetry (TimescaleDB hypertable) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry (
    agent_id      TEXT NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    alt_m         DOUBLE PRECISION DEFAULT 0,
    yaw_deg       REAL DEFAULT 0,
    velocity_mps  REAL DEFAULT 0,
    battery_pct   REAL NOT NULL,
    link_quality  REAL DEFAULT 1.0
);

-- Hypertable partitioned by ts (chunk = 1 day).
SELECT create_hypertable('telemetry', 'ts', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

CREATE INDEX IF NOT EXISTS telemetry_agent_ts_idx ON telemetry (agent_id, ts DESC);
