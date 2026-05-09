# FTIAS Peer Review Guide

## Purpose

Use this guide to review the FTIAS Internal Alpha / Technical Preview. Feedback should focus on usability, traceability, reports, FRAT, data ingestion, analysis interpretation, and responsible-use clarity.

## Before Reviewing

- Read `INTERNAL_ALPHA_NOTES.md`.
- Open Manual / Help in the app.
- Use non-sensitive sample or test data only.
- Do not treat outputs as certification approval, operational authorization, airworthiness determination, flutter clearance, or safety clearance.

## Recommended Review Flow

1. Start app.
2. Create/select flight test.
3. Upload CSV.
4. Switch dataset versions.
5. Review dashboard duration.
6. Chart parameters.
7. Toggle demo event markers.
8. Run AI Analysis in two modes.
9. Export report.
10. Create and score FRAT.
11. Test hard-stop/no-go scenario.
12. Export FRAT.
13. Open Manual / Help.

## What Feedback Is Most Useful

- unclear wording
- confusing workflow
- missing provenance
- misleading or overconfident output
- report readability
- FRAT score interpretation
- responsible-use boundary clarity
- reproducible defects

## How To Submit Feedback

Use GitHub Issues and choose the template that best fits the feedback:

- Peer review feedback
- Bug report
- Feature request

## After Submitting Feedback

Maintainers may label issues during triage and may ask for dataset version, analysis job ID, FRAT assessment ID, screenshots, logs, or exact reproduction steps.

Future ideas may be parked as concepts instead of immediately implemented. This keeps the internal alpha focused while preserving useful engineering suggestions.

## Evidence To Include

- screenshots
- dataset version ID
- analysis job ID
- FRAT assessment ID
- exact steps
- browser/environment
