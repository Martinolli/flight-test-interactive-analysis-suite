# FTIAS — Unified TODO (Execution Plan) — REV 03

**Last updated:** 2026-04-24
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

### P3.3 Add atmosphere / air-data engineering support

* **Reason:** this is a strong next engineering kernel and supports better normalization in later performance work.
* Add deterministic support for:

  * ISA / atmosphere conversions
  * pressure / temperature / density derivations
  * TAS / CAS / Mach support where data allows
  * basic air-data cross-check calculations
* This task is a strong candidate for selective PDAS/Fortran-to-Python adaptation of validated routines.
* Keep methods bounded and traceable.
* Do not imply full air-data calibration package unless actually implemented.

### P3.4 Harden buffet / vibration workflow

* **Reason:** current buffet/vibration mode is useful as screening, but still preliminary.
* Expand toward:

  * regime-aware screening
  * channel grouping
  * event-window analysis
  * better anomaly segmentation
  * optional first frequency-domain summaries if data quality supports it
* Preserve strict boundary:

  * screening/support only unless stronger validated methods are added
  * not loads substantiation
  * not flutter clearance
* Improve report wording and evidence traceability for this mode.

### P3.5 Add bounded flutter-support pre-screening

* **Reason:** after vibration hardening and atmosphere support, introduce a limited flutter-support layer.
* Scope:

  * pre-screening
  * safety-support indicators
  * trend review
  * explicit no-clearance boundary
* Do not present this as formal flutter clearance or certification evidence.
* Require strong applicability warning model.

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

1. **P3.3 — Add atmosphere / air-data engineering support**
2. **P3.4 — Harden buffet / vibration workflow**
3. **P3.5 — Add bounded flutter-support pre-screening**
4. **P3.6 — Expand manual / documentation package**

---

## Reason for This Order

* P2.1 through P2.4 are complete and provide:

  * mode architecture
  * deterministic calculators
  * retrieval metadata
  * confidence/coverage/applicability controls
* P2.5 FRAT workflow is now complete and establishes mission-risk state, scoring, hard-stops, approval/finalization, and immutable export.
* The biggest current product gap is now routing quality:

  * prompt intent can still mismatch selected mode
* Handling/control-response mode is now a bounded deterministic workflow with explicit non-certification boundaries.
* Atmosphere / air-data support should come before deeper vibration/flutter expansion because it strengthens engineering kernels broadly.
* Buffet/vibration should be hardened before any flutter-support pre-screening.
* Manual/documentation expansion should continue in parallel when practical, but it becomes much more valuable after FRAT and P3.1/P3.2 stabilization.

---

## Execution Gates

* [ ] G1 Product Truth Gate (after P0.1–P0.4 plus P0.3a) — ready for formal closure review
* [ ] G2 Engineering UX Gate (after P1.0–P1.4)
* [x] G3 Capability Definition Gate (after P1.5)
* [x] G4 Domainization Gate (after P2.1 + first additional deterministic modules)
* [ ] G5 Mission Decision Gate (after P2.5)
* [x] G6 Routing Integrity Gate (after P3.1)
* [ ] G7 Control/Handling Analysis Gate (after P3.2–P3.3)

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

## Deferred / Later Candidates

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
