# FTIAS Internal Alpha Notes

## What FTIAS Is

Flight Test Interactive Analysis Suite (FTIAS) is a web-based engineering support system for structured, traceable, and reproducible flight-test data analysis.

It supports CSV ingestion, dataset versioning, parameter charts, deterministic engineering modes, AI/RAG-assisted interpretation, saved analysis reports, and FRAT mission-risk review.

## What To Try

- Create or select a flight test.
- Upload a CSV dataset and inspect ingestion history.
- Switch dataset versions and confirm the dashboard duration window changes.
- Explore parameters and charts.
- Toggle demo event markers in the Parameters workflow.
- Run AI Analysis in at least two modes:
  - Takeoff or Landing Performance
  - Performance / Climb / Air Data
- Reopen a saved analysis by ID.
- Export an analysis PDF report.
- Create, score, review, and export a FRAT assessment.
- Open Manual / Help and confirm the manual PDF opens.

## What Not To Trust Yet

- Do not treat FTIAS output as certification approval.
- Do not treat FTIAS output as operational authorization, airworthiness determination, safety clearance, or flutter clearance.
- Treat AI/RAG answers as advisory/contextual and review sources.
- Treat deterministic outputs as bounded by available data, assumptions, data quality, and implemented models.
- Treat event markers as demo/manual baseline overlays, not backend-derived event records.
- Treat flutter, vibration, and loads outputs as screening/pre-screening support only.

## Feedback Requested

Please focus feedback on:

- Workflow clarity: where did you hesitate?
- Data provenance: could you tell which dataset version and analysis job were used?
- Report usefulness: did exported reports explain warnings, controls, and limitations clearly?
- FRAT usability: were scoring fields, hard-stops, notes, and next actions understandable?
- Performance / Climb / Air Data guidance: were CAS/TAS/Mach/ISA/density-altitude boundaries clear?
- Error recovery: were failed uploads and blocked exports understandable?
- Manual / Help: did the in-app help point you to the right guidance?

## How To Report Issues

Use the GitHub issue templates for peer-review feedback, bug reports, and feature requests.

If GitHub is blocked in the work environment, reviewers may access an internally hosted FTIAS instance if deployed by the FTI team. Feedback can still be collected manually using the same fields below and later entered into GitHub Issues when access is available.

For environments where Docker/GitHub deployment is unavailable, reviewers may use a Windows-native setup if approved by IT. Disabled AI/API capabilities should be documented before review.

For each issue, include:

- Short title
- Page/workflow
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshot if useful
- Dataset version ID or label, if relevant
- Analysis job ID, if relevant
- FRAT assessment ID, if relevant
- Browser and environment notes

Clearly mark safety or responsible-use concerns, especially if an output seems to imply certification approval, operational authorization, flutter clearance, loads substantiation, structural approval, or safety clearance. Include traceability IDs whenever available.

## Recommended Test Scenarios

1. Basic upload and chart review
   - Upload a valid CSV.
   - Confirm dataset version creation.
   - Open Parameters and chart at least two channels.

2. Failed upload recovery
   - Use an intentionally invalid upload if safe in your environment.
   - Confirm failed cleanup is available only for failed artifacts.

3. AI analysis provenance
   - Run one analysis.
   - Reopen it by analysis job ID.
   - Export a report and confirm provenance is understandable.

4. Prompt-to-mode guard
   - Select Takeoff but ask a handling/control prompt.
   - Confirm the warning explains the mismatch.

5. Performance / Climb / Air Data
   - Use a prompt involving altitude, vertical speed, CAS/TAS/Mach, ISA, or density altitude.
   - Confirm guidance does not imply certification-corrected performance.

6. FRAT Go / No-Go review
   - Score a normal case.
   - Score or inspect a hard-stop / rejected / No-Go case.
   - Export the FRAT report and confirm the explanation is useful.

## Release Framing

This is an Internal Alpha / Technical Preview. It is intended to find workflow, provenance, reporting, and usability issues before broader hardening.
