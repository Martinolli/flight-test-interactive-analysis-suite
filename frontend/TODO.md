# FTIAS Frontend — TODO (Execution Alignment)

**Last updated:** 2026-04-11  
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

- [ ] P1.1 Parameter exploration at scale
  - Search/filter, grouping, favorites, saved plot sets.
- [ ] P1.2 Chart workflow upgrades
  - Linked cursor/crosshair, markers, thresholds, compare mode.
- [ ] P1.3 Report UX quality improvements
  - Better figure selection/preview and clearer professional formatting expectations.
- [ ] P1.4 Capability-catalog-aware UI preparation
  - Support capability/mode applicability hints once backend catalog is defined.

---

## P2 — Domainization and Risk Workflow

- [ ] P2.1 Analysis mode selector and mode-specific UX cues
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
