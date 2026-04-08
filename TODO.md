# FTIAS — Unified TODO (Root Plan)

**Last updated:** 2026-04-06  
**Scope:** Backend + Frontend + LLM/RAG + Reporting  
**Source of truth:** aligned with `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md` (Improvement Backlog section)

---

## Current Priority Plan

### P0 — Immediate (Security, Correctness, Build Stability)

- [x] Lock down user-management routes
  - Restrict `/api/users/*` to admin or remove in favor of `/api/admin/users/*`.
- [x] Enforce document tenancy
  - Scope document list/delete/query by `uploaded_by_id == current_user.id`.
- [x] Enforce strict timestamp validation on ingestion
  - Reject invalid/missing timestamps with row-level errors.
- [x] Make frontend production build fully green
  - Resolve TS/type/lint blockers and enforce in CI.
- [x] Add ingestion observability baseline
  - Log and track parse/chunk/embed stage durations per document.

### P1 — Next (UX/Data Model Alignment for Mixed Flight-Test Domains)

- [x] Align upload UX and backend capability
  - Constrained upload UX to CSV-only to match backend `/upload-csv` support.
- [ ] Replace synthetic upload history with persisted ingestion sessions
  - Add backend model/API for filename, row count, status, errors, timestamps.
- [ ] Scale parameter exploration UX
  - Searchable parameter tree, subsystem grouping, favorites, saved views.
- [ ] Upgrade chart analysis workflow
  - Linked crosshair, event markers, threshold bands, compare-runs mode.
- [ ] Improve report visual quality
  - Better formula rendering, chart snapshots, clearer source references.
- [ ] Add Flight Test Risk Assessment module (FRAT)
  - Implement versioned risk templates, deterministic scoring, hard-stop checks, approval routing, and PDF export tied to each flight test.

### P2 — After P1 (LLM/RAG Domainization and Provenance)

- [ ] Add `analysis_mode` pipeline
  - Modes: `takeoff`, `landing`, `electrical`, `vibration`, `general`.
- [ ] Add retrieval metadata model
  - Authority/revision/domain/system tags and retrieval pre-filters.
- [ ] Persist immutable analysis jobs
  - Save prompt/model/sources/output hash; report generation by `analysis_job_id`.
- [ ] Introduce confidence and coverage indicators
  - Structured output quality metadata per answer/report.
- [ ] Add AI-assisted mitigation authoring for FRAT
  - Keep risk scoring deterministic; use LLM only to draft mitigation text and rationale with explicit user review.

---

## Recently Completed (Relevant to Current Roadmap)

- [x] Upload indexing moved to background task (no long blocking HTTP upload call)
- [x] Batched embeddings with env-configurable batch size
- [x] Docling fast-mode and chunk controls added via env
- [x] Hybrid retrieval + citation-density gate for analysis quality
- [x] Deterministic takeoff section with explicit WOW transition logic
- [x] AI response markdown/table rendering improvements in frontend
- [x] AI query response now supports formula rendering and responsive chat layout
- [x] Query response now emits citation-integrity/coverage warnings for frontend display
- [x] Docker frontend healthcheck fix (`127.0.0.1` for container health probe)

---

## Deferred / Later Candidates

- [ ] 3D trajectory view (Lat/Long/Alt)
- [ ] Email notifications (registration, processing complete)
- [ ] Celery/Redis queue migration (if/when single-worker model becomes insufficient)
