# FTIAS Frontend — TODO (Execution Alignment)

**Last updated:** 2026-04-19  
**Alignment:** mirrors root execution plan (`TODO.md`) and REV02 review.

---

## P0 — Product Truth + Unified AI UX

- [x] P0.1 Upload history from persisted ingestion sessions only
  - Remove remaining synthetic/localStorage operational truth.
  - Render backend status lifecycle + persisted errors.
- [x] P0.2 Support richer query response contract rendering
  - Prepare UI for structured fields (`assumptions`, `limitations`, `coverage`, etc.) with graceful fallback.
  - Added rendering blocks for summary, assumptions, limitations, calculation notes, recommended-next-queries, and coverage metrics.
- [x] P0.3 AI UX parity between `AI Standards Query` and `Analyze with AI`
  - Shared adaptive width/height behavior
  - stable long-answer scroll
  - consistent markdown/formula/warning/source rendering
  - Flight Test Detail `Analyze with AI` now matches the AI query chat behavior for adaptive sizing and answer presentation.
- [x] P0.3a Clarify active-dataset behavior in UI
  - Added explicit user-facing notices in Upload Data, Flight Test Detail, and Parameters.
  - Clarified that Upload History is audit-focused while analysis surfaces use the active dataset only.
- [x] P0.4 Analysis job persistence UX
  - Store/display `analysis_job_id` context in analysis/export flows.
  - Export actions now target persisted backend artifacts via immutable `analysis_job_id`.
  - Added "Re-open Saved Analysis by ID" input flow in `Analyze with AI`.
  - Frontend API contract now includes persisted `parameter_stats_snapshot` and `parameters_analysed` for immutable job reopen metadata.
  - Behavior expectation: reopened analysis metadata and export-driven annex values come from persisted job snapshots, not current mutable flight-test points.

---

## P1 — Engineering Usability and Report Quality

- [x] P1.0 Dataset versioning and active dataset selection UX
  - Added dataset-version selector + active-version controls in:
    - `Upload Data`
    - `Parameters`
    - `Flight Test Detail`
  - Dashboard/Parameters/AI Analysis calls now pass `dataset_version_id` when selected.
  - Flight-test API contract now surfaces `active_dataset_version_id`.
  - Upload response and history contracts now include dataset-version linkage fields.
  - Reopened analysis jobs in `Analyze with AI` now render the saved job dataset label from persisted provenance, with explicit mismatch notice versus current page selection.
- [x] P1.1 Standardize page framing and adaptive layout for Upload/Data Library
  - `Upload Data` and `Document Library` now use the adaptive page shell pattern (`max-w`, full-height flex, internal content scroll).
  - Added bounded internal scroll regions for long tables/history blocks to keep controls visible.
  - No behavior/API contract changes in upload or document workflows.
- [x] P1.2 Parameter exploration at scale
  - Added `ParameterExplorerPanel` with:
    - search filter
    - automatic grouping for large channel lists
    - favorites toggle + favorites-only filter
    - saved parameter sets (save/apply/delete)
  - Saved sets/favorites persist in local storage.
  - Integrated into both:
    - `Parameters` page
    - `Flight Test Detail` parameters panel
  - Follow-up persistence hardening (2026-04-17):
    - On `Parameters` page, saved sets are scoped to `flight-test` level to survive navigation/re-entry and dataset-version switching.
    - Apply flow now warns when set members are missing in current dataset, while preserving max-8 selection truncation.
  - Full persistence fix across explorer surfaces (2026-04-17):
    - Fixed mount-time localStorage overwrite race in `ParameterExplorerPanel`.
    - Unified storage namespace at shared flight-test scope for:
      - `Parameters` page explorer
      - `FlightTestDetail` explorer
    - Added missing/truncation warnings on `FlightTestDetail` apply flow for parity.
  - Final persistence correction (2026-04-17):
    - Fixed write-before-hydration ordering bug so favorites and saved sets are not clobbered by initial empty arrays on remount.
    - Added hydration guards to defer localStorage writes until key hydration is complete.
- [x] P1.3 Chart workflow upgrades
  - Linked cursor/crosshair, markers, thresholds, compare mode.
  - Progress (2026-04-17, step 1):
    - Implemented synchronized hover cursor readout for time-series charts in both explorer surfaces.
    - Added `TimeSeriesChart` sync primitives (`syncId`, hover snapshot callback) for upcoming multi-panel compare mode.
  - Progress (2026-04-17, step 2):
    - Added threshold/limit overlay controls on `Parameters` timeseries chart:
      - lower/upper limit lines
      - optional shaded band between limits
      - selectable threshold axis (left/right when dual-axis is present)
    - Added event marker overlay controls on `Parameters` timeseries chart (initial demo/manual baseline markers).
    - Improved report export quality:
      - configurable export options in chart download hook
      - `scale=3` high-resolution PNG export
      - container-capture export for timeseries to retain overlay/readout context.
  - Progress (2026-04-17, step 3):
    - Added compare-dataset mode on `Parameters` timeseries workflow:
      - optional enable/disable compare toggle
      - secondary dataset-version selector (same flight test)
      - overlay of selected parameters from compare dataset
    - Added compare-trace visual differentiation (legend tag + dashed/lighter lines) while preserving linked hover/cursor behavior.
    - Added compare-missing-parameter warning when selected parameters are absent in the secondary dataset.
  - Hardening pass (2026-04-17):
    - Event markers now render robustly by resolving marker timestamps to nearest chart sample when direct key matching fails.
    - PNG export reliability restored with SVG-first export path, fallback behavior, and user-visible export failure toast.
    - Hover responsiveness improved by reducing redundant hover updates and memoizing chart derivation work.
- [x] P1.4 Report UX quality improvements
  - Backend export template upgraded to professional engineering report structure with explicit metadata/provenance blocks.
  - Report now includes key figures, compact parameter summary table, improved narrative formatting, and auditable source/provenance footer.
  - Frontend immutable export flow remains unchanged (`analysis_job_id`-driven), preserving saved-job reproducibility.
- [x] P1.4a Report engineering wording hardening (backend-driven)
  - No frontend contract changes required.
  - Existing export trigger/UI remains unchanged while report content now clarifies:
    - deterministic estimate vs certification-corrected metric
    - explicit assumptions/limitations
    - applicability boundaries in exported narrative.
- [ ] P1.5 Capability-catalog-aware UI preparation
  - Support capability/mode applicability hints once backend catalog is defined.
  - Backend catalog foundation is now available (`backend/app/capabilities.py`); frontend integration remains pending by design.

---

## P2 — Domainization and Risk Workflow

- [x] P2.1 Analysis mode selector and mode-specific UX cues
  - `FlightTestDetail` AI Analysis quick chips now map to explicit backend mode keys:
    - `takeoff`, `landing`, `performance`, `buffet_vibration`, `general`
  - `Analyze with AI` request now sends `analysis_mode` separately from `user_prompt`.
  - AI panel now consumes `/api/documents/analysis-modes` to surface mode status/authority and warn when selected mode is limited.
  - Re-opened saved analysis jobs now carry and display their persisted `analysis_mode` provenance in the panel state.
  - AI panel provenance/source rendering now distinguishes:
    - `Narrative citations (N)` from analysis text references.
    - `Retrieved sources (M)` from persisted analysis-job retrieved-source snapshot.
  - Source counts are displayed separately to keep dashboard view aligned with saved-job/PDF provenance totals.
- [ ] P2.2 Analysis job history + provenance panel
- [ ] P2.3 Confidence/coverage/applicability badges
- [ ] P2.4 FRAT workspace in Flight Test Detail (deterministic workflow + approval UX)
- [ ] P2.5 AI mitigation drafting assistant (advisory only, not authoritative scoring)

---

## Completed Frontend Baseline (Protected)

- [x] Production build reliability restored
- [x] AI markdown/table rendering improvements
- [x] Source IDs visible in source cards
- [x] AI query math rendering (`remark-math` + `rehype-katex`)
- [x] Citation warning panel surfaced in AI query
- [x] AI query responsive layout with stable scrolling
- [x] Frontend Docker healthcheck/runtime fixes
- [x] Upload history polling runs only when ingestion is active (`pending`/`processing`)

---

## Backlog (After P2)

- [ ] Dashboard pagination for very large datasets
- [ ] React Query/SWR cache strategy
- [ ] Global error boundary + route-level skeleton states
- [ ] Accessibility audit (keyboard navigation, ARIA semantics)
- [ ] E2E coverage for critical flows (upload -> analyze -> report)
