-- P2.5: FRAT / mission-risk persisted workflow model.

CREATE TABLE IF NOT EXISTS frat_assessments (
    id SERIAL PRIMARY KEY,
    flight_test_id INTEGER NOT NULL REFERENCES flight_tests(id),
    dataset_version_id INTEGER NULL REFERENCES dataset_versions(id),
    created_by_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    assessment_name VARCHAR(255) NULL,
    analysis_reference_ids_json TEXT NOT NULL DEFAULT '[]',
    input_snapshot_json TEXT NOT NULL DEFAULT '{}',
    score_snapshot_json TEXT NOT NULL DEFAULT '{}',
    hard_stop_snapshot_json TEXT NOT NULL DEFAULT '[]',
    approval_notes TEXT NULL,
    approved_by_id INTEGER NULL REFERENCES users(id),
    approved_at TIMESTAMPTZ NULL,
    rejected_by_id INTEGER NULL REFERENCES users(id),
    rejected_at TIMESTAMPTZ NULL,
    finalized_by_id INTEGER NULL REFERENCES users(id),
    finalized_at TIMESTAMPTZ NULL,
    finalized_snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_frat_assessments_flight_test_id ON frat_assessments(flight_test_id);
CREATE INDEX IF NOT EXISTS ix_frat_assessments_dataset_version_id ON frat_assessments(dataset_version_id);
CREATE INDEX IF NOT EXISTS ix_frat_assessments_created_by_id ON frat_assessments(created_by_id);
CREATE INDEX IF NOT EXISTS ix_frat_assessments_status ON frat_assessments(status);
