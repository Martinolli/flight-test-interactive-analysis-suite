# FTIAS — Unified TODO (Execution Plan) — REV 02

**Last updated:** 2026-04-11
**Scope:** Backend + Frontend + LLM/RAG + Reporting
**Plan basis:** aligned to `TODO_REV_01.md`, `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`, current `TODO.md`, and post-P0.3 audit findings

---

## Instructions for Codex

1. Treat this file as the current execution plan and source of priority order.
2. Do not reopen completed baseline items unless there is clear defect evidence.
3. For every task:
   - preserve existing working behavior unless the task explicitly changes it
   - keep backend/frontend contracts aligned
   - add or update tests for critical paths
   - update this file when the task is completed
4. Before changing product behavior, ensure the UI does not imply unsupported capability.
5. When a task introduces a new persisted entity or workflow, prefer backend truth over client-side inference.
6. Deterministic engineering logic is authoritative for safety/performance outputs; LLM/RAG is interpretation and standards cross-check, not the primary computation engine.

---

## Execution Principles

1. Deterministic engineering logic is authoritative for safety/performance outputs.
2. LLM/RAG is a context and standards-cross-check layer, not a computation engine.
3. Operational truth must be persisted in backend records, never browser-local state.
4. Analysis outputs must be traceable and reproducible.
5. Applicability limits must be explicit whenever data/evidence is insufficient.
6. UI must not imply capabilities that the backend/data model does not actually provide.

---

## P0 — Immediate (Product Truth + Response Contract + Provenance)

- [x] P0.1 Persist ingestion sessions and remove synthetic upload history
  - Backend model/API for filename, row count, status lifecycle, and persisted error details.
  - Frontend upload history must use backend session data only.

- [x] P0.2 Standardize `/api/documents/query` response contract for engineering workflows
  - Evolve beyond `answer/sources/warnings` with structured fields (`assumptions`, `limitations`, `coverage`, etc.).
  - Keep backward-safe rendering during transition.
  - Added structured backend contract fields and frontend rendering fallback for legacy-safe behavior.
  - Added focused test coverage for structured response on both populated and empty-retrieval query paths.

- [x] P0.3 Standardize AI UX across `AI Standards Query` and `Analyze with AI`
  - Shared adaptive layout, scroll behavior, markdown/formula rendering, warnings, and sources.
  - `Analyze with AI` now uses responsive width, bounded internal answer scroll, markdown+math rendering, and explicit quality/source sections aligned with `AI Standards Query`.

- [x] P0.3a Clarify active-dataset behavior in UI
  - **Reason:** current product behavior preserves ingestion history but replaces active flight-test data on re-upload.
  - Upload History currently implies multiple usable datasets may exist, while Dashboard / Parameters / AI Analysis operate only on the latest active dataset.
  - Add explicit user-facing notice in:
    - `Upload Data`
    - `Flight Test Detail`
    - `Parameters` page or panel, if needed
  - Required wording intent:
    - upload history is audit/history
    - the latest successful upload is the active dataset
    - Dashboard, Parameters, and AI Analysis use the active dataset only
  - Keep current backend behavior unchanged for this task.
  - Added explicit notices in Upload Data, Flight Test Detail, and Parameters pages.
  - Added acceptance checklist in `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`.

- [x] P0.4 Persist analysis jobs and export PDF from immutable artifacts
  - Introduce `analysis_job_id` flow and provenance records.
  - Persist:
    - prompt text
    - model name/version string
    - retrieved source snapshot / IDs
    - `parameters_analysed`
    - parameter statistics snapshot (for immutable annex/report metadata)
    - output hash
    - timestamps
    - flight test linkage
  - Eliminate ad hoc report generation from mutable in-memory text.
  - PDF export must use immutable persisted analysis artifact, not freeform current-page text.
  - Re-open endpoint and PDF annex/statistics must be served from persisted `analysis_jobs` snapshot fields, not live `DataPoint` recomputation.
  - Required acceptance:
    - analysis can be re-opened by ID
    - PDF export uses saved analysis job
    - provenance is inspectable
    - existing UI flow remains usable
    - reopened job metadata remains reproducible after later dataset changes
    - PDF annex/statistics remain reproducible after later dataset changes
  - Implemented with persisted `analysis_jobs` model + migrations, `GET` by analysis job ID, immutable snapshot-backed metadata, and immutable PDF export keyed by `analysis_job_id`.

---

## P1 — Engineering Usability + Report Professionalism

- [ ] P1.0 Introduce dataset versioning / active dataset selection per flight test
  - **Reason:** current history is persisted, but only the last uploaded dataset is active and analyzable.
  - Evolve Upload History from audit-only history to dataset-version awareness.
  - Define and implement one of these models explicitly:
    - immutable dataset versions under a single flight test
    - or linked run datasets under a shared campaign/test container
  - Minimum required capability:
    - user can see which dataset is active
    - user can select prior dataset versions
    - Dashboard / Parameters / AI Analysis operate on the selected version
    - no hidden overwrite behavior
  - This is a larger product/data-model task and should not be merged as a UI-only patch.

- [x] P1.1 Standardize page framing and adaptive layout across main work pages
  - Align `Upload Data` and `Document Library` with the adaptive framing used in:
    - `AI Standards Query`
    - `Flight Test Detail`
    - `Parameters`
  - Standardize:
    - max-width container
    - vertical layout behavior
    - internal scroll regions
    - empty/loading/error states
    - spacing rhythm and card framing
  - Keep behavior changes minimal; this task is primarily visual and UX consistency work.
  - Implemented:
    - `Upload Data` and `Document Library` now use a shared adaptive page shell pattern (`max-w`, full-height flex, internal content scroll).
    - Large tabular/history areas use bounded internal scroll regions to keep page framing stable on smaller screens.
    - Existing upload/library behavior and API interactions are unchanged.

- [ ] P1.2 Scale parameter exploration for large channel sets
  - Search, grouping, favorites, saved views/sets.

- [ ] P1.3 Upgrade chart workflow for engineering review
  - Linked crosshair, event markers, threshold bands, compare-runs mode, better export quality.

- [ ] P1.4 Improve PDF/report professional quality
  - Structured template, figure quality, cleaner references, provenance footer.

- [ ] P1.5 Define capability catalog before deeper domain branching
  - Capability families
  - required inputs
  - deterministic vs RAG-assisted classification
  - blocked-condition rules
  - applicability boundaries

---

## P2 — Domainization + Deterministic Expansion

- [ ] P2.1 Introduce `analysis_mode` architecture
  - Domain routing for:
    - `takeoff`
    - `landing`
    - `performance`
    - `handling_qualities`
    - `buffet_vibration`
    - `flutter`
    - `propulsion_systems`
    - `electrical_systems`
    - `general`

- [ ] P2.2 Add deterministic calculators beyond takeoff
  - Extract current logic to dedicated analysis modules.
  - Add landing / climb / vibration / flutter-support metrics in a modular structure.

- [ ] P2.3 Add retrieval metadata model for mode-aware RAG
  - Authority / revision / domain / capability tags with mode pre-filtering.

- [ ] P2.4 Add confidence / coverage / applicability controls
  - Clear blocked-condition signaling in UI and report outputs.

- [ ] P2.5 Add FRAT / mission risk workflow
  - Deterministic scoring, hard-stops, approval/finalization, immutable snapshot export.

---

## Immediate Execution Order

1. P1.0 — Dataset versioning / active dataset selection  
2. P1.2 — Scale parameter exploration for large channel sets  

- **Reason for this order**

- P0.3a is completed and user-facing dataset-scope behavior is now explicit.
- P0.4 is completed: analysis artifacts are now persisted and exported by immutable job ID.
- P1.1 is now completed.
- P1.0 remains the highest-impact product/data-model change and should be implemented deliberately.

---

## Execution Gates

- [ ] G1 Product Truth Gate (after P0.1–P0.4 plus P0.3a) — ready for formal closure review
- [ ] G2 Engineering UX Gate (after P1.0–P1.4)
- [ ] G3 Capability Definition Gate (after P1.5)
- [ ] G4 Domainization Gate (after P2.1 + first additional deterministic modules)

---

## Completed Baseline (Protected)

- [x] User-route lockdown
- [x] Document tenancy isolation
- [x] Strict timestamp validation
- [x] Frontend production build stability
- [x] Ingestion observability baseline
- [x] CSV-only upload alignment
- [x] DB migration artifact for `ingestion_sessions` table (`backend/migrations/20260411_add_ingestion_sessions.sql`)
- [x] Upload-page polling narrowed to active ingestion states only (`pending`/`processing`)
- [x] Hybrid retrieval + citation hardening
- [x] Deterministic takeoff section
- [x] Responsive AI Standards Query page
- [x] Query warning surfacing
- [x] Retrieval diversity controls

These baseline controls should be protected by regression tests.

---

## Deferred / Later Candidates

- [ ] Document visibility / sharing model
  - private vs shared vs admin-visible standards library
- [ ] 3D trajectory view (Lat/Long/Alt)
- [ ] Email notifications (registration, processing complete)
- [ ] Celery/Redis queue migration (if/when single-worker model becomes insufficient)

---

## Notes from Latest Audit

- Upload History is now truthful and persisted, but it currently tracks ingestion sessions rather than selectable dataset versions.
- Current re-upload behavior replaces the active dataset for the flight test while keeping prior ingestion sessions visible in history.
- `AI Standards Query` and `Analyze with AI` are now much closer in UX behavior, but shared rendering components are still a future refactor opportunity.
- `Upload Data` and `Document Library` still need page-framing/layout standardization to match the stronger work surfaces.
