-- FTIAS DB Migration
-- Revision date: 2026-04-11
-- Purpose: harden analysis job immutability with persisted parameter stats snapshot.
-- Target DB: PostgreSQL

BEGIN;

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS parameters_analysed INTEGER NOT NULL DEFAULT 0;

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS parameter_stats_snapshot_json TEXT NOT NULL DEFAULT '[]';

COMMIT;
