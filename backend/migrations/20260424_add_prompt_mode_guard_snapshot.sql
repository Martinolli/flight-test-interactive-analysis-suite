-- P3.1: Persist prompt-to-mode routing quality guard snapshot per analysis job.

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS prompt_mode_guard_json TEXT NOT NULL DEFAULT '{}';
