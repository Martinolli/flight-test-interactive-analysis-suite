# FTIAS Frontend — TODO (Aligned to Root P0/P1/P2 Plan)

**Last updated:** 2026-04-06  
**Alignment:** mirrors priorities in root `TODO.md` and summary backlog

---

## P0 — Immediate Frontend Work

- [x] Restore production build reliability
  - Resolve all TypeScript and lint blockers in app build path.
  - Keep Tailwind utility normalization warnings cleaned up where touched.
- [ ] Improve AI answer rendering for technical content
  - Ensure formulas/equations render consistently on screen and in exported report text.
  - Keep markdown tables/lists/headers robust for long responses.
- [ ] Tighten source-reference UX in AI responses
  - Keep citation ids stable (`[S1]`, `[S2]`) and clearly map to source cards.
  - Surface "insufficient citation coverage" warning in UI when backend flags low density.
- [ ] Add ingestion progress observability in UI
  - Show parsing/chunking/indexing stage and elapsed time when available from backend.

## P1 — Next Frontend Work (UX/Data Alignment)

- [ ] Upload UX/backend parity decision
  - Either keep UI CSV-only or enable XLS/XLSX only after backend support is live.
- [ ] Replace synthetic upload history with backend ingestion sessions
  - Render real status/error/timestamps from API (no localStorage-derived records).
- [ ] Parameter explorer for large channel sets
  - Add search, subsystem grouping, favorites, saved parameter sets.
- [ ] Chart workflow upgrades for engineering analysis
  - Linked cursor/crosshair across charts.
  - Event markers and threshold bands.
  - Compare mode between multiple flight tests.
- [ ] Report UX upgrades
  - Better chart-to-report selection and preview before generating PDF.
- [ ] Add `Risk Assessment (FRAT)` workspace in Flight Test Detail
  - Category checklist UI, live score/disposition badge, hard-stop alert banner, and approval/signature section.

## P2 — Frontend Support for LLM/RAG Domainization

- [ ] Add analysis mode selector in AI panel
  - `takeoff`, `landing`, `electrical`, `vibration`, `general`.
- [ ] Introduce analysis jobs UI
  - Job history list, job detail view, immutable source/provenance panel.
- [ ] Add confidence and coverage indicators in responses/reports
  - Visual badges and warning states for low confidence/coverage.
- [ ] Add AI-assisted mitigation drafting in FRAT UI
  - Suggest mitigation text from selected risk factors, but require explicit human acceptance before saving.

---

## Recently Completed (Frontend-Relevant)

- [x] AI Analysis panel reset/new-query flow
- [x] Markdown table rendering improvements in AI response panel
- [x] Source cards now display stable source ids for citation mapping
- [x] Frontend Docker healthcheck fix (`127.0.0.1`) to avoid false unhealthy state
- [x] Time-series chart PNG export flow repaired

---

## Backlog (After P2)

- [ ] Dashboard pagination for very large datasets
- [ ] React Query/SWR cache strategy
- [ ] Global error boundary + route-level skeleton states
- [ ] Accessibility audit (keyboard navigation, ARIA semantics)
- [ ] E2E coverage for critical flows (upload -> analyze -> report)
