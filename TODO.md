# FTIAS — Unified TODO (Execution Plan)

**Last updated:** 2026-04-09  
**Scope:** Backend + Frontend + LLM/RAG + Reporting  
**Plan basis:** aligned to `TODO_REV_01.md` review and `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

---

## Execution Principles

1. Deterministic engineering logic is authoritative for safety/performance outputs.
2. LLM/RAG is a context and standards-cross-check layer, not a computation engine.
3. Operational truth must be persisted in backend records, never browser-local state.
4. Analysis outputs must be traceable and reproducible.
5. Applicability limits must be explicit whenever data/evidence is insufficient.

---

## P0 — Immediate (Product Truth + Response Contract + Provenance)

- [ ] P0.1 Persist ingestion sessions and remove synthetic upload history
  - Backend model/API for filename, row count, status lifecycle, and persisted error details.
  - Frontend upload history must use backend session data only.
- [ ] P0.2 Standardize `/api/documents/query` response contract for engineering workflows
  - Evolve beyond `answer/sources/warnings` with structured fields (`assumptions`, `limitations`, `coverage`, etc.).
  - Keep backward-safe rendering during transition.
- [ ] P0.3 Standardize AI UX across `AI Standards Query` and `Analyze with AI`
  - Shared adaptive layout, scroll behavior, markdown/formula rendering, warnings, and sources.
- [ ] P0.4 Persist analysis jobs and export PDF from immutable artifacts
  - Introduce `analysis_job_id` flow and provenance records (prompt/model/source snapshot/hash).
  - Eliminate ad hoc report generation from mutable in-memory text.

---

## P1 — Engineering Usability + Report Professionalism

- [ ] P1.1 Scale parameter exploration for large channel sets
  - Search, grouping, favorites, saved views/sets.
- [ ] P1.2 Upgrade chart workflow for engineering review
  - Linked crosshair, event markers, threshold bands, compare-runs mode, better export quality.
- [ ] P1.3 Improve PDF/report professional quality
  - Structured template, figure quality, cleaner references, provenance footer.
- [ ] P1.4 Define capability catalog before deeper domain branching
  - Capability families, required inputs, deterministic vs RAG-assisted classification.

---

## P2 — Domainization + Deterministic Expansion

- [ ] P2.1 Introduce `analysis_mode` architecture
  - Domain routing for `takeoff`, `landing`, `performance`, `handling_qualities`, `buffet_vibration`, `flutter`, `propulsion_systems`, `electrical_systems`, `general`.
- [ ] P2.2 Add deterministic calculators beyond takeoff
  - Extract current logic to dedicated analysis modules and add landing/climb/vibration/flutter-support metrics.
- [ ] P2.3 Add retrieval metadata model for mode-aware RAG
  - Authority/revision/domain/capability tags with mode pre-filtering.
- [ ] P2.4 Add confidence/coverage/applicability controls
  - Clear blocked-condition signaling in UI/report outputs.
- [ ] P2.5 Add FRAT / mission risk workflow
  - Deterministic scoring, hard-stops, approval/finalization, immutable snapshot export.

---

## Execution Gates

- [ ] G1 Product Truth Gate (after P0.1–P0.4)
- [ ] G2 Engineering UX Gate (after P1.1–P1.3)
- [ ] G3 Capability Definition Gate (after P1.4)
- [ ] G4 Domainization Gate (after P2.1 + first additional deterministic modules)

---

## Completed Baseline (Protected)

- [x] User-route lockdown
- [x] Document tenancy isolation
- [x] Strict timestamp validation
- [x] Frontend production build stability
- [x] Ingestion observability baseline
- [x] CSV-only upload alignment
- [x] Hybrid retrieval + citation hardening
- [x] Deterministic takeoff section
- [x] Responsive AI Standards Query page
- [x] Query warning surfacing
- [x] Retrieval diversity controls

These baseline controls should be protected by regression tests.

---

## Deferred / Later Candidates

- [ ] 3D trajectory view (Lat/Long/Alt)
- [ ] Email notifications (registration, processing complete)
- [ ] Celery/Redis queue migration (if/when single-worker model becomes insufficient)
