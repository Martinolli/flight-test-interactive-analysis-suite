-- FTIAS DB Migration
-- Revision date: 2026-04-12
-- Purpose: introduce immutable dataset versions and active dataset selection per flight test.
-- Target DB: PostgreSQL

BEGIN;

CREATE TABLE IF NOT EXISTS dataset_versions (
    id SERIAL PRIMARY KEY,
    flight_test_id INTEGER NOT NULL REFERENCES flight_tests(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    label VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'processing',
    row_count INTEGER NULL,
    data_points_count INTEGER NULL,
    source_session_id INTEGER NULL REFERENCES ingestion_sessions(id) ON DELETE SET NULL,
    created_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_versions_flight_test_version
    ON dataset_versions(flight_test_id, version_number);

CREATE INDEX IF NOT EXISTS ix_dataset_versions_flight_test_id
    ON dataset_versions(flight_test_id);

CREATE INDEX IF NOT EXISTS ix_dataset_versions_created_by_id
    ON dataset_versions(created_by_id);

ALTER TABLE flight_tests
    ADD COLUMN IF NOT EXISTS active_dataset_version_id INTEGER NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_flight_tests_active_dataset_version_id'
    ) THEN
        ALTER TABLE flight_tests
            ADD CONSTRAINT fk_flight_tests_active_dataset_version_id
            FOREIGN KEY (active_dataset_version_id)
            REFERENCES dataset_versions(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_flight_tests_active_dataset_version_id
    ON flight_tests(active_dataset_version_id);

ALTER TABLE data_points
    ADD COLUMN IF NOT EXISTS dataset_version_id INTEGER NULL
    REFERENCES dataset_versions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_data_points_dataset_version_id
    ON data_points(dataset_version_id);

CREATE INDEX IF NOT EXISTS ix_data_points_flight_test_dataset
    ON data_points(flight_test_id, dataset_version_id);

ALTER TABLE ingestion_sessions
    ADD COLUMN IF NOT EXISTS dataset_version_id INTEGER NULL
    REFERENCES dataset_versions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_ingestion_sessions_dataset_version_id
    ON ingestion_sessions(dataset_version_id);

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS dataset_version_id INTEGER NULL
    REFERENCES dataset_versions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_analysis_jobs_dataset_version_id
    ON analysis_jobs(dataset_version_id);

-- Backfill one baseline immutable version (v1) for existing flight tests with existing datapoints.
INSERT INTO dataset_versions (
    flight_test_id,
    version_number,
    label,
    status,
    row_count,
    data_points_count,
    created_by_id
)
SELECT
    ft.id,
    1,
    'v1',
    'success',
    NULL,
    COUNT(dp.id) AS data_points_count,
    ft.created_by_id
FROM flight_tests ft
JOIN data_points dp ON dp.flight_test_id = ft.id
LEFT JOIN dataset_versions existing
    ON existing.flight_test_id = ft.id
   AND existing.version_number = 1
WHERE existing.id IS NULL
GROUP BY ft.id, ft.created_by_id;

-- Link existing datapoints to baseline version when no version is set.
UPDATE data_points dp
SET dataset_version_id = dv.id
FROM dataset_versions dv
WHERE dp.flight_test_id = dv.flight_test_id
  AND dv.version_number = 1
  AND dp.dataset_version_id IS NULL;

-- Set active dataset version for flight tests with backfilled versions.
UPDATE flight_tests ft
SET active_dataset_version_id = dv.id
FROM dataset_versions dv
WHERE dv.flight_test_id = ft.id
  AND dv.version_number = 1
  AND ft.active_dataset_version_id IS NULL;

-- Associate historical ingestion sessions and analysis jobs to the active baseline version
-- for legacy data that predated explicit dataset versioning.
UPDATE ingestion_sessions s
SET dataset_version_id = ft.active_dataset_version_id
FROM flight_tests ft
WHERE s.flight_test_id = ft.id
  AND s.dataset_version_id IS NULL;

UPDATE analysis_jobs aj
SET dataset_version_id = ft.active_dataset_version_id
FROM flight_tests ft
WHERE aj.flight_test_id = ft.id
  AND aj.dataset_version_id IS NULL;

COMMIT;
