-- P2.3: retrieval metadata model for mode-aware RAG
-- Adds persisted metadata fields to documents for authority/revision/domain/capability aware ranking.

BEGIN;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS authority_type VARCHAR(64) NOT NULL DEFAULT 'handbook',
    ADD COLUMN IF NOT EXISTS document_revision VARCHAR(128),
    ADD COLUMN IF NOT EXISTS domain_tags_json TEXT NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS capability_tags_json TEXT NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS aircraft_scope VARCHAR(128),
    ADD COLUMN IF NOT EXISTS system_scope VARCHAR(128),
    ADD COLUMN IF NOT EXISTS source_priority INTEGER NOT NULL DEFAULT 60;

-- Best-effort normalization for legacy rows.
UPDATE documents
SET authority_type = CASE
    WHEN lower(coalesce(doc_type, '')) IN ('regulation', 'reg', 'standard', 'mil_std') THEN 'regulation'
    WHEN lower(coalesce(doc_type, '')) IN ('advisory', 'ac') THEN 'advisory'
    WHEN lower(coalesce(doc_type, '')) IN ('internal', 'internal_reference') THEN 'internal_reference'
    WHEN lower(coalesce(doc_type, '')) IN ('derived', 'derived_note') THEN 'derived_note'
    ELSE 'handbook'
END
WHERE authority_type IS NULL OR authority_type = '';

UPDATE documents
SET source_priority = CASE
    WHEN authority_type = 'regulation' THEN 100
    WHEN authority_type = 'advisory' THEN 85
    WHEN authority_type = 'handbook' THEN 75
    WHEN authority_type = 'internal_reference' THEN 60
    WHEN authority_type = 'derived_note' THEN 40
    ELSE 60
END
WHERE source_priority IS NULL;

UPDATE documents
SET domain_tags_json = '[]'
WHERE domain_tags_json IS NULL OR trim(domain_tags_json) = '';

UPDATE documents
SET capability_tags_json = '[]'
WHERE capability_tags_json IS NULL OR trim(capability_tags_json) = '';

COMMIT;

