CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_ts DOUBLE PRECISION NOT NULL,
    received_ts DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL DEFAULT 'api',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_user_event_ts_desc
    ON events (user_id, event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_received_ts_desc
    ON events (received_ts DESC);

CREATE TABLE IF NOT EXISTS user_vector_snapshots (
    user_id TEXT PRIMARY KEY,
    short_term_vector JSONB NOT NULL,
    long_term_vector JSONB NOT NULL,
    last_event_ts DOUBLE PRECISION,
    snapshot_ts DOUBLE PRECISION NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
