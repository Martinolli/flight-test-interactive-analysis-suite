-- FTIAS DB Migration
-- Revision date: 2026-04-11
-- Purpose: add immutable persisted AI analysis jobs with provenance metadata.
-- Target DB: PostgreSQL

BEGIN;

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id SERIAL PRIMARY KEY,
    flight_test_id INTEGER NOT NULL REFERENCES flight_tests(id) ON DELETE CASCADE,
    created_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status VARCHAR(32) NOT NULL DEFAULT 'completed',
    model_name VARCHAR(128) NOT NULL,
    model_version VARCHAR(128) NULL,
    prompt_text TEXT NOT NULL,
    retrieved_source_ids_json TEXT NOT NULL DEFAULT '[]',
    retrieved_sources_snapshot_json TEXT NOT NULL DEFAULT '[]',
    output_sha256 VARCHAR(64) NOT NULL,
    analysis_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_analysis_jobs_flight_test_id
    ON analysis_jobs (flight_test_id);

CREATE INDEX IF NOT EXISTS ix_analysis_jobs_created_by_id
    ON analysis_jobs (created_by_id);

CREATE INDEX IF NOT EXISTS ix_analysis_jobs_created_at
    ON analysis_jobs (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_analysis_jobs_output_sha256
    ON analysis_jobs (output_sha256);

COMMIT;
