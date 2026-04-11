-- FTIAS DB Migration
-- Revision date: 2026-04-11
-- Purpose: add persisted ingestion session tracking table for CSV uploads.
-- Target DB: PostgreSQL

BEGIN;

CREATE TABLE IF NOT EXISTS ingestion_sessions (
    id SERIAL PRIMARY KEY,
    flight_test_id INTEGER NOT NULL REFERENCES flight_tests(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    file_type VARCHAR(32) NOT NULL DEFAULT 'csv',
    source_format VARCHAR(32) NOT NULL DEFAULT 'csv',
    row_count INTEGER NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    error_message TEXT NULL,
    error_log TEXT NULL,
    uploaded_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_ingestion_sessions_flight_test_id
    ON ingestion_sessions (flight_test_id);

CREATE INDEX IF NOT EXISTS ix_ingestion_sessions_uploaded_by_id
    ON ingestion_sessions (uploaded_by_id);

CREATE INDEX IF NOT EXISTS ix_ingestion_sessions_created_at
    ON ingestion_sessions (created_at DESC);

COMMIT;
