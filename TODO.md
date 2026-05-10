# FTIAS — Unified TODO (Execution Plan) — REV 03

**Last updated:** 2026-05-04
**Scope:** Backend + Frontend + LLM/RAG + Reporting + Operational Workflow
**Plan basis:** aligned to REV 02, `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`, completed P0/P1/P2 work, and post-P2.4 review findings

---

## Instructions for Codex

1. Treat this file as the current execution plan and source of priority order.
2. Do not reopen completed baseline items unless there is clear defect evidence.
3. For every task:

   * preserve existing working behavior unless the task explicitly changes it
   * keep backend/frontend contracts aligned
   * add or update tests for critical paths
   * update this file when the task is completed
4. Before changing product behavior, ensure the UI does not imply unsupported capability.
5. When a task introduces a new persisted entity or workflow, prefer backend truth over client-side inference.
6. Deterministic engineering logic is authoritative for safety/performance outputs; LLM/RAG is interpretation and standards cross-check, not the primary computation engine.
7. Mission/risk workflows must remain auditable, stateful, and exportable from immutable backend artifacts.
8. Routing must not silently misclassify obviously mismatched prompt/mode combinations.

---

## Execution Principles

1. Deterministic engineering logic is authoritative for safety/performance outputs.
2. LLM/RAG is a context and standards-cross-check layer, not a computation engine.
3. Operational truth must be persisted in backend records, never browser-local state.
4. Analysis outputs must be traceable and reproducible.
5. Applicability limits must be explicit whenever data/evidence is insufficient.
6. UI must not imply capabilities that the backend/data model does not actually provide.
7. Advisory-only outputs must never be presented as mission-approval evidence without clear limitations.
8. Domain growth should follow validated engineering kernels before broader narrative expansion.

---

## P0 — Immediate (Product Truth + Response Contract + Provenance)

* [x] P0.1 Persist ingestion sessions and remove synthetic upload history
* [x] P0.2 Standardize `/api/documents/query` response contract for engineering workflows
* [x] P0.3 Standardize AI UX across `AI Standards Query` and `Analyze with AI`
* [x] P0.3a Clarify active-dataset behavior in UI
* [x] P0.4 Persist analysis jobs and export PDF from immutable artifacts

---

## P1 — Engineering Usability + Report Professionalism

* [x] P1.0 Introduce dataset versioning / active dataset selection per flight test
* [x] P1.1 Standardize page framing and adaptive layout across main work pages
* [x] P1.2 Scale parameter exploration for large channel sets
* [x] P1.3 Upgrade chart workflow for engineering review
* [x] P1.4 Improve PDF/report professional quality
* [x] P1.4a Harden report engineering wording and result classification
* [x] P1.5 Define capability catalog before deeper domain branching

---

## P2 — Domainization + Deterministic Expansion

* [x] P2.1 Introduce `analysis_mode` architecture

* [x] P2.2 Add deterministic calculators beyond takeoff

* [x] P2.3 Add retrieval metadata model for mode-aware RAG

* [x] P2.4 Add confidence / coverage / applicability controls

* [x] P2.5 Add FRAT / mission risk workflow

  * Deterministic scoring
  * Hard-stops
  * Approval / rejection / finalization lifecycle
  * Immutable snapshot export
  * Backend truth over browser-local state
  * Linkage to flight test / dataset version / supporting analysis jobs
  * Clear go / review / no-go outcome model
  * FRAT results must respect analysis applicability, confidence, and warning controls from P2.4

---

## P3 — Routing Quality + Domain Deepening

* [x] P3.1 Add prompt-to-mode routing quality guard

  * **Reason:** current routing is mode-first and can produce semantically wrong classification when the prompt intent does not match the selected mode.
  * Add prompt/mode mismatch detection before final routing.
  * Examples:

    * prompt mentions `aileron`, `stick`, `roll response`, `handling`, `control input`, but selected mode is `takeoff`
    * prompt requests vibration/load/frequency behavior, but selected mode is `general` or `takeoff`
  * Required behavior:

    * detect probable mismatch
    * warn user clearly
    * suggest better mode(s)
    * downgrade strong mismatches from strict deterministic modes to safer general execution with explicit traceability
  * Do not silently run an obviously wrong deterministic mode when the prompt intent is incompatible.
  * Preserve explicit user control; do not over-automate.
  * Add tests for:

    * mode mismatch detection
    * safe fallback / suggestion behavior
    * non-regression for correct mode selections

* [x] P3.2 Add handling qualities / control-response workflow

  * **Reason:** current datasets already contain useful control and response parameters:

    * aileron deflection
    * stick position
    * rudder/elevator
    * roll/pitch/yaw rates
    * attitude response
  * Implemented a bounded handling-qualities mode:

    * control-input range summaries
    * response trend/correlation summaries
    * lag/trend observations
    * anomaly flagging
  * Keep output explicitly bounded:

    * not formal Cooper-Harper determination
    * not full certification handling-qualities substantiation
  * Capability catalog aligned with explicit applicability boundaries.
  * Deterministic summaries first, with RAG as supporting interpretation.

* [x] P3.3 Add atmosphere / air-data engineering support

  * **Reason:** this is a strong engineering kernel and supports better normalization in performance workflows.
  * Implemented bounded deterministic atmosphere/air-data support in performance mode:

    * ISA snapshot derivation from pressure altitude
    * density-altitude estimate from pressure altitude + OAT
    * TAS estimate from CAS + sigma (bounded low-compressibility approximation)
    * Mach estimate from TAS + temperature source (SAT/OAT/TAT priority)
    * consistency summaries for TAS/Mach estimate-vs-measured and pressure-altitude-vs-altitude
  * Output now explicitly lists:

    * channels used
    * skipped calculations when required inputs are missing
    * applicability boundaries and non-calibration limitations
  * Capability catalog and prompt-intent routing keywords were aligned for air-data/performance terminology.

### P3.4 Harden buffet / vibration workflow ✅

* **Completed:** buffet/vibration deterministic workflow is now structured and engineering-readable as bounded screening support.
* Delivered hardening includes:

  * grouped channel summaries and dominant-channel ranking
  * regime-aware segmentation using bounded WOW/speed cues
  * significant anomaly/event-window summaries
  * bounded optional frequency-domain screening with cadence-quality guards and explicit skips
* Preserved strict boundary:

  * screening/support only
  * not loads substantiation
  * not flutter clearance
* Narrative/report wording updated for screening-only positioning and clearer traceability.

### P3.5 Add bounded flutter-support pre-screening ✅

* **Completed:** `flutter` mode now runs a real bounded deterministic flutter-support pre-screening workflow.
* Delivered scope:

  * channel/regime/frequency-based pre-screening indicators
  * dominant window summaries with contextual flight-condition cues
  * concern-indicator model and follow-up recommendation output
  * explicit non-clearance, non-certification wording in analysis/report sections
* Safety boundary preserved:

  * not flutter clearance
  * not modal-identification certification
  * not aeroelastic substantiation authority
* Controls alignment:

  * flutter concern indicators now influence warning severity and bounded-result interpretation.

### P3.6 Expand manual / documentation package

* Build structured project manual in chapters:

  1. Introduction
  2. System overview
  3. Architecture and connections
  4. Installation and Docker environment
  5. Upload / dataset workflow
  6. Parameters and chart workflow
  7. AI analysis modes
  8. Reporting / provenance / immutability
  9. FRAT workflow
  10. Troubleshooting
  11. Maintenance and future growth
* Include capability-by-capability usage guidance.
* Include limitations and expected engineering review practices.

---

## Immediate Execution Order

1. **P3.6 — Expand manual / documentation package**

---

## Reason for This Order

* P2.1 through P2.4 are complete and provide:

  * mode architecture
  * deterministic calculators
  * retrieval metadata
  * confidence/coverage/applicability controls
* P2.5 FRAT workflow is now complete and establishes mission-risk state, scoring, hard-stops, approval/finalization, and immutable export.
* Prompt-to-mode guard is now enforced with explicit mismatch severity and guarded execution.
* Handling/control-response mode is now a bounded deterministic workflow with explicit non-certification boundaries.
* Atmosphere / air-data support is now available as a bounded deterministic kernel inside performance mode.
* Buffet/vibration hardening and flutter-support pre-screening are complete.
* Next highest-value step is documentation/manual expansion for operational adoption and review consistency.
* Manual/documentation expansion should continue in parallel when practical, but it becomes much more valuable after FRAT and P3.1/P3.2 stabilization.

---

## Execution Gates

* [ ] G1 Product Truth Gate (after P0.1–P0.4 plus P0.3a) — ready for formal closure review
* [ ] G2 Engineering UX Gate (after P1.0–P1.4)
* [x] G3 Capability Definition Gate (after P1.5)
* [x] G4 Domainization Gate (after P2.1 + first additional deterministic modules)
* [ ] G5 Mission Decision Gate (after P2.5)
* [x] G6 Routing Integrity Gate (after P3.1)
* [x] G7 Control/Handling Analysis Gate (after P3.2–P3.3)

---

## Completed Baseline (Protected)

* [x] User-route lockdown
* [x] Document tenancy isolation
* [x] Strict timestamp validation
* [x] Frontend production build stability
* [x] Ingestion observability baseline
* [x] CSV-only upload alignment
* [x] DB migration artifact for `ingestion_sessions`
* [x] Upload-page polling narrowed to active ingestion states only
* [x] Upload History dataset label fidelity on Upload page
* [x] Hybrid retrieval + citation hardening
* [x] Deterministic takeoff section
* [x] Responsive AI Standards Query page
* [x] Query warning surfacing
* [x] Retrieval diversity controls
* [x] Flight-test deletion integrity for dataset-version/provenance graph
* [x] Dataset-version-aware analysis routing and saved-job dataset provenance
* [x] Persisted analysis control snapshot (`analysis_controls_json`)
* [x] PDF/report control summary integration

These baseline controls should be protected by regression tests.

---

## P4 — Trust, Reporting, and Export Completeness

* [x] P4.1 FRAT No-Go / not-approved report availability and explanation layer

  * Added structured FRAT decision explanations to scored/reopened assessment payloads.
  * FRAT PDF export is now available for scored Go, review, rejected, no-go, unacceptable, hard-stop, approved, and finalized states.
  * Unscored draft export remains blocked with an explicit message.
  * Reports now include decision summary, score composition, category breakdown, hard-stops, linked-analysis/no-linked-analysis evidence, dominant risk drivers, reviewer/transition notes, and provenance.
  * No-linked-analysis cases explicitly state that technical analysis evidence was not included and warn when score is moderate or higher.
  * Backend and frontend contracts were updated with regression coverage.

* [x] P4.2 Report chart label readability fix

  * Added deterministic chart label shortening/coding for ReportLab PDF figures.
  * Preserved full parameter names in chart caption mappings and the parameter statistics table.
  * Report generation now succeeds with long telemetry/channel names without placing raw long labels on chart axes.
  * Backend regression coverage verifies helper behavior, axis label compaction, full-name preservation, and PDF generation.

* [x] P4.3 Upload failed/incorrect ingestion cleanup

  * Added owner-scoped failed-ingestion cleanup endpoint for failed/cancelled/error upload sessions.
  * Cleanup removes failed ingestion sessions, failed dataset versions, and associated partial data points while preserving successful and active datasets.
  * Cleanup is blocked for successful datasets, active datasets, saved-analysis references, FRAT references, and another user's records.
  * Upload Data now exposes a confirmed cleanup action only on failed/cancelled/error upload rows and refreshes history/dataset versions after cleanup.
  * Backend regression coverage verifies cleanup success, blocked states, reference safety, tenant isolation, and response summaries.

* [x] P4.4 Dashboard duration window derivation

  * Added dataset-scoped duration derivation from persisted timestamp min/max aggregation.
  * Dataset version responses now include structured duration status, start/end timestamps, seconds, and display label.
  * Flight Test Detail now shows the selected dataset duration window instead of static flight-test duration metadata.
  * Backend regression coverage verifies multi-point, single-point, no-data, dataset-scoped, tenant-isolated, and invalid timestamp cases.

* [x] P4.5 Event marker UX clarification/fix

  * Confirmed Parameters chart markers are a demo/manual baseline only, derived from selected chart data.
  * Renamed the control to `Show demo event markers` and added explicit marker availability/visibility copy.
  * Chart markers now render in front of traces with stronger labels, and the UI states that no backend event marker source exists yet.

* [x] P3.6 / P4.6 Report/control readability polish in frontend-visible surfaces

  * Added frontend-readable analysis routing, result-control, provenance, limitation, and report-readiness cards.
  * Prompt-to-mode warnings now answer whether the selected mode likely matches the prompt intent.
  * Saved analysis reopen wording now states the artifact is immutable and tied to the captured dataset/controls.

* [x] P3.7 Manual / help integration

  * Added a protected `/help` page with Manual V-00 access and workflow cards.
  * Served `FTIAS-MANUAL-V00.pdf` through the frontend static manual path.
  * Added contextual help links for Upload, Dataset Versioning, Parameters, AI Analysis, Reports, and FRAT.

* [x] P3.5a FRAT usability hardening

  * Added field-level guidance for assessment scope, authority, manual adjustment, linked analysis, categories, hard-stops, and notes.
  * Added compact 0-20 category scoring guide and local category-base preview while keeping backend score authoritative.
  * Added workflow status, hard-stop prominence, notes/rationale reminders, and clearer score composition.

* [x] P3.3 Atmosphere / air-data support UX

  * Updated Performance / Climb / Air Data quick prompt copy and local prompt-intent keywords.
  * Added frontend guidance for CAS/TAS/Mach, ISA, pressure-altitude, density-altitude, and air-data consistency interpretation.
  * Added Help page air-data guidance and contextual links while keeping backend calculations authoritative.

* [x] Release readiness / internal alpha preparation

  * Added `RELEASE_READINESS.md` with internal alpha validation gates, known warnings, limitations, and share/no-share checklist.
  * Added `INTERNAL_ALPHA_NOTES.md` for peer-facing technical preview guidance.
  * Updated README and GitHub workflow README references for current alpha documentation.

* [x] License metadata cleanup

  * Standardized the MIT `LICENSE` file with the selected copyright line.
  * Removed placeholder contact/author metadata.

* [x] v0.1.0-alpha release tagging

  * Internal alpha tag and GitHub pre-release are published.

* [x] P5.0 Peer review issue templates and feedback workflow

  * Added structured GitHub issue templates for peer review feedback, bug reports, and feature requests.
  * Added issue-template contact links to internal alpha notes and release readiness.
  * Added `PEER_REVIEW_GUIDE.md` with reviewer flow, feedback focus areas, and evidence expectations.

* [x] P5.1 Repository / CI hygiene cleanup

  * Removed generated coverage artifacts from version control while keeping them ignored locally.
  * Updated `.gitignore` for backend coverage/cache output, frontend build/cache output, environment files, and logs.
  * Updated GitHub Actions documentation to clarify workflow triggers, path filters, local frontend build validation, and current warnings.
  * Added repository hygiene checks to release readiness.

* [x] P5.2 Vibration & Frequency Analysis concept formalization

  * Created `Project_Documents/P5_2_Vibration_Frequency_Analysis_Concept.md`.
  * Formalized the future vibration/frequency workspace as concept-only, not implemented in v0.1.0-alpha.
  * Captured responsible-use boundaries, V1 scope, later scope, defaults, sampling warnings, and future task breakdown.

* [x] P5.3 Internal alpha issue triage labels and guide

  * Added `ISSUE_TRIAGE_GUIDE.md` with internal alpha triage principles, label taxonomy, severity guidance, release-impact decisions, and examples.
  * Updated peer-review and internal alpha notes to explain post-submission triage and traceability expectations.
  * Renamed future vibration/frequency placeholders to `P5.VF.*` to avoid conflict with active internal-alpha task numbering.

* [x] P5.4 Internal alpha feedback intake / sample issue dry run

  * Created Issue #1 as a peer-review dry run: `[Peer Review]: Internal alpha workflow dry run`.
  * Confirmed template structure, `internal-alpha` / `peer-review` labels, provenance fields, severity/priority section, and responsible-use section.

* [x] P5.5 Repository document cleanup

  * Removed obsolete `TODO_V0.md` and `frontend/TODO_V1.md`.
  * Added `Project_Documents/README.md` to classify historical planning notes, reference documents, archive candidates, and current future concepts.
  * Clarified that current roadmap truth lives in `TODO.md` and `frontend/TODO.md`.

* [ ] P5.6 Linux internal deployment guide for FTI server

  * Next planned step.
  * Document a bounded internal Linux deployment workflow for an FTI server environment.

---

## Deferred / Later Candidates

### Future Vibration & Frequency Analysis Roadmap

These are planning placeholders only. They are not active implementation tasks.

* [ ] P5.VF.1 Vibration/Frequency data model and API design
* [ ] P5.VF.2 Time-domain + PSD MVP
* [ ] P5.VF.3 Data-quality checks and sampling warnings
* [ ] P5.VF.4 Frequency bands and summary metrics
* [ ] P5.VF.5 Spectrogram and comparison mode
* [ ] P5.VF.6 Export/report integration

* [ ] Document visibility / sharing model

  * private vs shared vs admin-visible standards library
* [ ] 3D trajectory view (Lat/Long/Alt)
* [ ] Email notifications (registration, processing complete)
* [ ] Celery/Redis queue migration (if/when single-worker model becomes insufficient)
* [ ] Selective PDAS routine adaptation backlog

  * atmosphere kernels
  * numerical interpolation/root-finding helpers
  * bounded performance support routines
  * later vibration/flutter-support kernels after validation

---

## Notes from Latest Audit

* Takeoff remains the strongest deterministic mode and is the current engineering reference implementation.
* Landing is now a usable bounded deterministic mode.
* Performance mode is useful as bounded engineering trend support, not full certification performance analysis.
* General mode works as advisory-only standards/context guidance.
* Buffet/vibration remains screening-level and should be expanded only with explicit applicability controls.
* P2.4 controls are valuable, but report rendering still has polish opportunities:

  * replace enum-style labels with human-readable wording
  * deduplicate repeated limitations/applicability text
  * improve wording for zero-retrieval cases
* Prompt-to-mode guard is now enforced with mismatch severity, suggested modes, and strong-mismatch guarded execution metadata.
