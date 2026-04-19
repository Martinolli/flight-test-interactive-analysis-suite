# FTIAS — Unified TODO (Execution Plan) — REV 02

**Last updated:** 2026-04-19
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

- [x] P1.0 Introduce dataset versioning / active dataset selection per flight test
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
  - Implemented:
    - Added immutable `dataset_versions` model + migration with active version pointer on `flight_tests`.
    - CSV uploads now create new dataset versions (`vN`) without deleting historical datapoints.
    - Added activation + listing endpoints for dataset versions.
    - Dashboard/Parameters/AI Analysis now support selected `dataset_version_id` (defaulting to active version).
    - Reopened saved analysis jobs now display their own persisted dataset provenance in the AI panel (with mismatch notice if current selection differs).
    - Added regression coverage for version creation, activation behavior, and dataset-scoped AI analysis persistence.

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

- [x] P1.2 Scale parameter exploration for large channel sets
  - Search, grouping, favorites, saved views/sets.
  - Implemented:
    - Added searchable/grouped parameter explorer for large channel inventories.
    - Added favorites toggle and favorites-only filter.
    - Added saved parameter sets (save/apply/delete), persisted in browser local storage.
    - Applied in both `Parameters` page and `Flight Test Detail` parameters panel.
  - Follow-up fix (2026-04-17):
    - `Parameters` page saved sets are now scoped at flight-test level (not dataset-version level) to prevent sets appearing lost after navigation or dataset switching.
    - Applying saved sets now warns when some parameters are unavailable in the currently selected dataset and keeps max-8 truncation behavior.
  - Persistence hardening (2026-04-17):
    - Fixed localStorage hydration race in `ParameterExplorerPanel` that could overwrite persisted sets with empty state on remount.
    - Unified saved-set namespace across both surfaces to shared flight-test scope:
      - `Parameters` page
      - `FlightTestDetail` parameters explorer
    - Saved sets now persist across navigation/refresh and are recoverable from both surfaces for the same flight test.
  - Final persistence correction (2026-04-17):
    - Fixed write-before-hydration lifecycle issue so favorites and saved sets are never overwritten by initial empty state during remount.
    - Added explicit hydration-complete guards for key-scoped read/write flow before localStorage updates are allowed.

- [x] P1.3 Upgrade chart workflow for engineering review
  - Linked crosshair, event markers, threshold bands, compare-runs mode, better export quality.
  - Progress (2026-04-17, step 1):
    - Added synchronized time-cursor/crosshair readout wiring in time-series charts on both `Parameters` and `Flight Test Detail`.
    - Added `TimeSeriesChart` sync hooks (`syncId`, hover snapshot callback) to support upcoming multi-chart linked analysis.
  - Progress (2026-04-17, step 2):
    - Added threshold overlays in `Parameters` timeseries workflow (upper/lower lines + optional shaded band).
    - Added event-marker overlay support (initial demo/manual baseline markers: start/mid/end + WOW transition when available).
    - Upgraded PNG export quality path (`scale=3`) and enabled container capture for timeseries export so engineering overlay context/readout is preserved.
  - Progress (2026-04-17, step 3):
    - Added compare-dataset mode in `Parameters` timeseries workflow with a second dataset-version selector.
    - Compare mode overlays the same selected parameters from the secondary dataset as distinct compare traces.
    - Compare traces are visually differentiated in chart legend/line style and retain linked crosshair behavior.
    - Compare flow reports missing parameters from the secondary dataset without breaking primary analysis flow.
  - Hardening pass (2026-04-17):
    - Fixed event-marker visibility by snapping marker timestamps to nearest available chart sample when exact x-axis key matching is not present.
    - Restored reliable PNG export using SVG-first path for Recharts with fallback, plus user-visible export error handling.
    - Improved hover responsiveness by memoizing heavy chart derivations and suppressing redundant hover-state updates.

- [x] P1.4 Improve PDF/report professional quality
  - Implemented professional engineering report structure with fixed section hierarchy:
    1) cover/title
    2) flight-test metadata
    3) dataset provenance
    4) analysis summary
    5) key figures
    6) parameter statistics summary
    7) AI narrative
    8) sources/provenance footer
  - Added explicit provenance visibility in report body:
    - flight test name/ID
    - aircraft type
    - dataset version label/ID
    - analysis job ID
    - generation timestamp
    - model/version
  - Added persisted-snapshot-derived figures and improved narrative rendering:
    - key stats figures (sample density + min/mean/max profile)
    - markdown table rendering preserved
    - warning/finding/recommendation callout styling
  - Added auditable provenance footer + retrieved-source summary table.
  - Added backend regression coverage for report section/provenance rendering while preserving immutable `analysis_job_id` export flow.

- [x] P1.4a Harden report engineering wording and result classification
  - Focused hardening pass without reopening report layout/template design.
  - Clarified takeoff result labeling in deterministic/report content:
    - Estimated takeoff ground roll to liftoff
    - Deterministic data-derived estimate
    - Certification corrections not applied unless explicitly computed
  - Added explicit assumptions/limitations language for takeoff-style results:
    - wind/runway-slope/non-standard-atmosphere corrections not applied
    - WOW transition/event-definition sensitivity
    - sampling/sensor-quality sensitivity
    - estimate-vs-certification distinction
  - Strengthened engineering separation in PDF narrative rendering:
    - deterministic computed result
    - standards cross-check
    - assumptions/limitations
    - recommendations
    - applicability boundaries
  - Preserved immutable export/provenance behavior (`analysis_job_id` artifact flow).

- [x] P1.5 Define capability catalog before deeper domain branching
  - Added backend capability catalog source of truth in `backend/app/capabilities.py` with typed definitions for:
    - capability identity (key/label/description/status)
    - required inputs (signals/dataset/provenance/correction inputs)
    - authority classification (`deterministic_primary`, `deterministic_with_rag_crosscheck`, `rag_guidance_only`, `not_supported`)
    - blocked/downgrade rules with reason keys and outcome policies
    - applicability boundaries and output-contract intent
  - Catalog populated for initial families:
    - `takeoff`
    - `landing`
    - `performance_general`
    - `handling_qualities`
    - `trajectory_kinematics`
    - `systems_monitoring`
    - `buffet_vibration`
    - `flutter_support`
    - `risk_assessment`
    - `general_standards_query`
  - Added resolver/evaluator helpers:
    - `get_capability_definition(...)`
    - `list_capabilities()`
    - `evaluate_capability_request(...)`
  - Integrated minimally with current implemented flow:
    - takeoff deterministic path now evaluates capability state (signals/coverage/event-detection/certification-request downgrade).
    - deterministic takeoff section now emits catalog-aligned capability outcome, limitations, and applicability boundaries.
    - report takeoff limitations/applicability defaults now read from capability catalog (single truth).
  - Added focused tests for catalog/rules and integration-safe behavior.

---

## P2 — Domainization + Deterministic Expansion

- [x] P2.1 Introduce `analysis_mode` architecture
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
  - Implemented backend mode-routing foundation:
    - Added explicit mode registry/resolver in `backend/app/analysis_modes.py`.
    - Added `/api/documents/analysis-modes` endpoint exposing mode key/label/description, capability key, status, and authority.
    - Extended AI analysis request/response contract with `analysis_mode` and `capability_key`.
    - Mode-tagged persisted prompts (`[analysis_mode:...]`) for saved-analysis provenance; reopen flow decodes and returns clean prompt text.
    - Current deterministic takeoff path is now routed through `analysis_mode=takeoff`.
    - Non-takeoff modes return explicit capability-aware bounded output (blocked/partial/guidance-aware), without claiming unsupported deterministic computation.
  - Added focused regression coverage for:
    - mode registry/capability alignment
    - default mode resolution
    - takeoff routed behavior and persisted mode tag
    - explicit limited outcome for non-implemented mode (`landing`)
    - unknown-mode request rejection
  - Frontend integration hardening (Dashboard / Flight Test Detail AI Analysis):
    - quick mode chips now map to explicit backend `analysis_mode` keys and send mode in request payload
    - AI panel now surfaces backend mode truth (`implemented` / `partial` / `planned` / `blocked`) via `/api/documents/analysis-modes`
    - UI shows bounded-capability notice for non-implemented modes and preserves prompt-vs-mode separation
  - Provenance display alignment hardening:
    - AI response now includes persisted `retrieved_sources_snapshot` so dashboard panel can show full retrieved-source provenance.
    - Flight Test Detail AI panel now distinguishes:
      - narrative citations (sources explicitly cited in visible analysis text)
      - retrieved sources (full persisted analysis-job source set used for provenance/PDF footer).
    - Source counts are now surfaced as separate values to avoid under-reporting retrieved evidence.

- [x] P2.2 Add deterministic calculators beyond takeoff
  - Extracted deterministic logic into dedicated module package:
    - `backend/app/analysis/deterministic.py`
    - `backend/app/analysis/__init__.py`
  - Preserved takeoff as deterministic reference implementation via routed module call.
  - Added bounded deterministic calculators and mode routing integration for:
    - `landing` (WOW + ground-speed touchdown-to-rollout estimate)
    - `performance` (`performance_general` bounded trend metrics)
    - `buffet_vibration` (deterministic screening metrics, not clearance determination)
  - Updated capability-catalog truth to align with implemented deterministic scope:
    - `landing`: `implemented`, `deterministic_with_rag_crosscheck`
    - `performance_general`: `implemented`, `deterministic_primary`
    - `buffet_vibration`: `implemented`, `deterministic_primary`
  - Added focused regression coverage for:
    - modular calculator behavior (`test_deterministic_calculators.py`)
    - mode-routing outputs for landing/performance/buffet
    - catalog status/authority alignment updates
  - Kept non-implemented domain boundaries explicit (`flutter` remains bounded/unsupported).

- [ ] P2.3 Add retrieval metadata model for mode-aware RAG
  - Authority / revision / domain / capability tags with mode pre-filtering.

- [ ] P2.4 Add confidence / coverage / applicability controls
  - Clear blocked-condition signaling in UI and report outputs.

- [ ] P2.5 Add FRAT / mission risk workflow
  - Deterministic scoring, hard-stops, approval/finalization, immutable snapshot export.

---

## Immediate Execution Order

1. P2.3 — Add retrieval metadata model for mode-aware RAG  
2. P2.4 — Add confidence / coverage / applicability controls  

- **Reason for this order**

- P1.3 is completed with linked cursor, thresholds, event markers, compare-dataset overlays, and improved export fidelity.
- P1.4 and P1.4a are completed for report professionalism + wording hardening.
- P2.1 routing and P2.2 deterministic expansion are complete; next impact is retrieval metadata + confidence/coverage control hardening.

---

## Execution Gates

- [ ] G1 Product Truth Gate (after P0.1–P0.4 plus P0.3a) — ready for formal closure review
- [ ] G2 Engineering UX Gate (after P1.0–P1.4)
- [x] G3 Capability Definition Gate (after P1.5)
- [x] G4 Domainization Gate (after P2.1 + first additional deterministic modules)

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
- [x] Flight-test deletion integrity for dataset-version/provenance graph
  - Explicit backend deletion sequence now handles `DataPoint`, `AnalysisJob`, `IngestionSession`, `DatasetVersion`, and `active_dataset_version_id` linkage safely.
  - Added regression coverage for deleting provenance-rich flight tests.
  - FK-order follow-up (2026-04-18):
    - corrected dependency order to delete `DatasetVersion` before `IngestionSession`
      because `dataset_versions.source_session_id` references `ingestion_sessions.id`.

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

- Upload history and dataset versions are now both persisted and explicit: history is audit trail, dataset versions are selectable analysis scope.
- Re-upload now creates new immutable dataset versions and updates active version on successful ingestion; historical versions remain selectable.
- `AI Standards Query` and `Analyze with AI` are aligned on core UX behavior, but shared rendering-component extraction is still a future refactor opportunity.
- `Upload Data` and `Document Library` framing/layout standardization is complete.
- Parameter exploration at scale now includes search, grouping, favorites, and saved parameter sets in both analysis surfaces.
- Backend deletion integrity is hardened for legacy and provenance-rich flight tests after dataset versioning rollout.
