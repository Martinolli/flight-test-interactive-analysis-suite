# FTIAS Release Readiness

## Release Type

Internal Alpha / Technical Preview.

## Intended Audience

Technical peers, engineering reviewers, and selected internal users who understand flight-test data workflows and can provide disciplined feedback.

## Responsible Use Statement

FTIAS is engineering support only. It is not certification approval, operational authorization, airworthiness determination, flutter clearance, or safety clearance. Deterministic outputs, AI/RAG summaries, reports, and FRAT assessments must be reviewed by qualified personnel before use in any formal decision.

## Current Readiness Status

Status: documentation and workflow readiness pass complete for internal alpha preparation.

This repository is suitable for controlled technical preview only after the checks below pass in the target environment. Wider release still requires deployment, security, data-handling, and organizational/legal suitability review.

## Current Validation Baseline

Run these checks before sharing:

```powershell
black --check --diff backend/app backend/tests
pytest backend/tests -q
pnpm -C frontend run build
docker compose up -d --build backend frontend
```

Useful service checks:

```powershell
docker compose ps
docker compose logs -f backend
```

Expected local URLs:

- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`

## Required Pre-Share Checks

- [ ] Working tree is clean or intentional changes are committed.
- [ ] CI checks are green on the branch being shared.
- [ ] Docker rebuild succeeds for backend and frontend.
- [ ] `.env` and local secrets are not committed.
- [ ] Manual opens from the in-app Help page.
- [ ] README reflects current capabilities and limitations.
- [ ] Known limitations are visible to reviewers.
- [ ] Sample/demo data policy is clear to reviewers.
- [ ] Reviewers receive `INTERNAL_ALPHA_NOTES.md`.

## CI / Build Checks

- [ ] Backend formatting check passes.
- [ ] Backend test suite passes.
- [ ] Frontend production build passes.
- [ ] Docker Compose build validates the local runtime.
- [ ] Any expected warnings are recorded in this file.

## Manual Smoke-Test Checklist

- [ ] Login/authentication works.
- [ ] Flight test creation works.
- [ ] CSV upload succeeds with a valid file.
- [ ] Failed upload cleanup is visible for failed ingestion sessions and removes only failed artifacts.
- [ ] Dataset version switching updates the selected version.
- [ ] Dashboard duration window updates from the selected dataset.
- [ ] Parameter charting renders selected telemetry.
- [ ] Demo event markers are clearly labeled and visibly toggle on charts.
- [ ] AI Analysis mode selection works.
- [ ] Prompt-to-mode warning appears for an obvious mismatch.
- [ ] Performance / Climb / Air Data guidance appears and is understandable.
- [ ] Saved analysis report export works from an analysis job.
- [ ] FRAT draft creation and scoring work.
- [ ] FRAT hard-stop warning is prominent when selected.
- [ ] FRAT No-Go/rejected export remains available once scored.
- [ ] Manual / Help page opens.
- [ ] Manual PDF opens from `/manual/FTIAS-MANUAL-V00.pdf`.

## Documentation Checks

- [ ] `README.md` is current.
- [ ] `RELEASE_READINESS.md` is current.
- [ ] `INTERNAL_ALPHA_NOTES.md` is current.
- [ ] `TODO.md` and `frontend/TODO.md` show the next planned step.
- [ ] `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md` records the readiness pass.
- [ ] `LICENSE` exists and is referenced.
- [ ] MIT License terms are suitable for the intended distribution group.

## Responsible-Use Checks

- [ ] README includes responsible-use limitations.
- [ ] Help page includes responsible-use reminder.
- [ ] Reports and AI analysis surfaces avoid implying certification approval.
- [ ] FRAT output is framed as mission-risk support, not organizational approval.
- [ ] Flutter support is labeled as pre-screening only.
- [ ] Vibration/load results are labeled as screening support only.

## Known Warnings

- Vite may warn that Node.js `20.18.1` is installed while Vite expects `20.19+` or `22.12+`. Builds have completed successfully with the warning, but Node should be upgraded when practical.
- Vite may warn that some frontend chunks are larger than 500 kB after minification. This is acceptable for internal alpha but should be revisited before wider release.
- The repository currently uses MIT License terms.
- Confirm organizational/legal suitability before external redistribution.

## Known Limitations

- FTIAS is not certification-ready.
- FTIAS is not operational approval or safety clearance.
- Flutter support is pre-screening only, not flutter clearance.
- Vibration and loads support is screening only, not formal substantiation.
- Event markers are demo/manual baseline overlays only, not backend-derived event records.
- AI/RAG output is advisory and contextual; citations and retrieval coverage must be reviewed.
- Deterministic modes are bounded by available telemetry, data quality, assumptions, and implemented models.
- Performance / Climb / Air Data support does not provide certification-corrected performance reduction unless explicit correction models are implemented and documented.
- Successful dataset deletion is not part of failed-upload cleanup.
- Deployment, security hardening, access control review, backup/restore, and data-retention policy work are still required before wider release.

## Peer Review Instructions

1. Start the app with Docker Compose.
2. Upload or select a sample dataset.
3. Run a basic parameter check and verify charts render.
4. Run AI analysis in at least two modes, including Performance / Climb / Air Data.
5. Export a saved analysis report.
6. Create and score a FRAT assessment.
7. Trigger or inspect a FRAT hard-stop / No-Go case and export the FRAT report.
8. Open Manual / Help and confirm the manual PDF opens.
9. Record issues with screenshots, dataset version, analysis job ID, FRAT assessment ID, and steps to reproduce.

## Share / No-Share Gate

Share only if all applicable items are true:

- [ ] CI is green.
- [ ] Docker rebuild is successful.
- [ ] Manual opens from the app.
- [ ] README is current.
- [ ] `LICENSE` is present and MIT License terms are understood.
- [ ] No secrets are present in the repository.
- [ ] Sample/demo data policy is clear.
- [ ] Known limitations are visible to reviewers.
- [ ] Internal reviewers understand that this is a technical preview.

No-share conditions:

- [ ] Any required build/test check fails without a documented reason.
- [ ] Secrets or private credentials are present.
- [ ] Manual / Help cannot be opened.
- [ ] Known limitations are hidden from intended reviewers.
- [ ] Review audience expects certification, airworthiness, or operational authorization output.
