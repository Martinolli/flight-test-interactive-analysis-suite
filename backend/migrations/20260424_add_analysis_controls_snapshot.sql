-- P2.4: Persist structured confidence/coverage/applicability controls per analysis job.
-- Safe for existing rows via default empty JSON object.

ALTER TABLE analysis_jobs
ADD COLUMN IF NOT EXISTS analysis_controls_json TEXT NOT NULL DEFAULT '{}';
