# FTIAS Frontend TODO — REV 03

**Last updated:** 2026-04-24
**Scope:** Frontend UX, workflow alignment, routing clarity, engineering usability, FRAT workspace

---

## Frontend Execution Principles

1. UI must reflect backend truth, not imply unsupported capability.
2. Deterministic engineering outputs must be visually distinguished from advisory/RAG guidance.
3. Persisted backend artifacts must be preferred over browser-local state.
4. Dataset, analysis, report, and FRAT provenance must remain visible where relevant.
5. Warnings, applicability limits, and confidence/coverage controls must be understandable to users.
6. Workflow clarity is part of safety: do not hide state, mode, or limitation boundaries.

---

## Completed / Protected

* [x] Responsive framing across main pages

  * Upload Data
  * Document Library
  * Flight Test Detail
  * Parameters
  * AI Standards Query

* [x] Upload history now uses backend truth

* [x] Dataset version selection / activation UI

* [x] Dataset provenance display in AI analysis

* [x] Upload History dataset label fidelity

* [x] Parameter explorer with:

  * search
  * favorites
  * saved parameter sets
  * persistence hardening

* [x] Chart review workflow:

  * linked crosshair
  * event markers
  * threshold/limit overlays
  * compare-dataset mode
  * export hardening

* [x] AI Analysis panel mode wiring to backend `analysis_mode`

* [x] Mode-truth UI:

  * implemented
  * partial
  * planned
  * limited-state notices

* [x] Saved analysis reopen by ID

* [x] Retrieved-sources vs narrative-citations separation in AI panel

* [x] PDF/report export flow aligned to immutable analysis jobs

* [x] Analysis control fields exposed in frontend contracts

* [x] FRAT workspace page added with:

  * create/edit draft
  * score
  * approve/reject
  * finalize
  * export

These should be protected from regression.

---

## Current Frontend Priority

* [x] P3.1 Support prompt-to-mode routing quality guard in UI

  * Surface prompt/mode mismatch warnings clearly before analysis is run.
  * Examples:

    * user selects `takeoff`, but prompt is about `aileron`, `stick`, `roll response`, `handling`
    * user selects `general`, but prompt explicitly asks for landing rollout or vibration screening
  * Required UI behavior:

    * show a clear mismatch warning
    * suggest a better mode when available
    * surface backend-authoritative mismatch result (selected mode, executed mode, inferred intent)
    * allow the user to keep current mode intentionally, but do not hide the mismatch
  * Keep backend routing truth authoritative; frontend should guide, not invent routing logic.

---

## P3 — Frontend Roadmap

### P3.1 Prompt-to-mode routing clarity

* Add a visible pre-run validation layer in AI Analysis.
* Show:

  * selected mode
  * prompt intent mismatch warning when detected
  * suggested mode(s)
* Prevent UI from giving false confidence when prompt and selected mode do not align.
* Do not auto-switch mode silently.

### P3.2 Handling-qualities / control-response frontend workflow ✅

* Added frontend entry point for handling-qualities mode.
* UI pattern now supports:

  * control input channels
  * response channels
  * selected signal mapping
  * bounded interpretation notes
* Implemented surfaces:

  * Flight Test Detail AI panel
  * Parameters page integration
  * possible dedicated handling-analysis section later

### P3.3 Atmosphere / air-data support UX

* Prepare future frontend support for atmosphere/air-data outputs:

  * corrected values
  * derived air-data summaries
  * explicit assumptions/limitations
* Keep derived/engineering-calculated values visibly separated from raw telemetry.

### P3.4 Buffet / vibration workflow hardening

* Improve frontend support for vibration screening results:

  * grouped channel summaries
  * event-window summaries
  * anomaly emphasis
  * clearer “screening only” messaging
* Do not visually imply flutter clearance or formal substantiation.

### P3.5 FRAT usability hardening

* Improve FRAT input clarity and operator guidance.
* Add a clear user checklist / guided sequence for FRAT workflow:

  1. create draft
  2. enter mission/test inputs
  3. link supporting analysis if available
  4. score
  5. review hard-stops/warnings
  6. approve or reject
  7. finalize
  8. export
* Clarify parameter meanings in the FRAT UI:

  * labels
  * helper text
  * section grouping
  * risk meaning of each field
* This is a UX hardening task, not a workflow redesign.

### P3.6 Report/readability polish in frontend-visible surfaces

* Improve readability of control summaries:

  * use human-readable labels instead of enum-like names
  * e.g. `High`, `Bounded`, `Advisory only`
* Deduplicate repeated limitation/applicability text where surfaced in UI previews.
* Improve empty/zero-retrieval wording:

  * avoid abrupt or confusing phrasing
  * make limitations explicit but readable

### P3.7 Manual / help integration

* Support future user guidance surfaces:

  * mode selection help
  * report interpretation help
  * FRAT usage help
  * capability limitations quick reference

---

## Immediate Frontend Execution Order

1. **P3.5 — FRAT usability hardening**
2. **P3.6 — Report/control readability polish**
3. **P3.4 — Buffet / vibration workflow hardening**
4. **P3.3 — Atmosphere / air-data support UX**
5. **P3.7 — Manual / help integration**

---

## Frontend Notes from Latest Review

* FRAT workflow is operational, but the user needs a clearer checklist and field guidance.
* Prompt/mode mismatch is now surfaced pre-run and with backend-authoritative guard state after run.
* Handling/control-response mode is now exposed in AI Analysis quick options with bounded deterministic backend support.
* Current reports expose useful control information, but frontend/report wording still needs polish:

  * enum-style labels should become user-friendly
  * repeated limitations should be reduced
  * weak/no-source cases should be communicated more clearly
* Current frontend mode set is still a simplified surface over a broader backend capability architecture.

---

## Deferred / Later Frontend Candidates

* [ ] Shared document visibility controls
* [ ] 3D trajectory viewer
* [ ] richer report preview before PDF export
* [ ] multi-analysis comparison workspace
* [ ] advanced engineering annotation workflow
