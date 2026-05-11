# Flight Test Interactive Analysis Suite (FTIAS)

## Overview

Flight Test Interactive Analysis Suite (FTIAS) is a web-based engineering support system for structured, traceable, and reproducible flight-test data analysis.

FTIAS supports flight-test data ingestion, immutable dataset versioning, parameter exploration, deterministic engineering calculations, AI/RAG-assisted interpretation, PDF report generation, and FRAT mission-risk workflows.

FTIAS is an engineering review and decision-support tool. It is not a certification system, an automatic operational approval system, or a substitute for qualified engineering judgment.

## Current Capabilities

The app also includes a protected `Manual / Help` page that links to the current manual and lightweight workflow guidance for Upload Data, Dataset Versioning, Parameters, AI Analysis, Reports, FRAT, and troubleshooting.

### Flight-Test Data Management

- Flight-test record creation and management
- CSV upload for time-series flight-test data
- Persisted ingestion sessions with status, errors, and upload history
- Immutable dataset versions for successful uploads
- Active dataset selection for dashboards, parameters, and analysis
- Cleanup support for failed ingestion artifacts while preserving valid dataset history

### Parameter Exploration

- Parameter search and selection
- Interactive charts for selected telemetry channels
- Favorites and saved parameter sets
- Dataset-aware parameter viewing
- Dataset comparison support
- Chart export for review and reporting workflows

### AI Standards Query

- Document-centered RAG query workflow
- Uploaded technical documents, standards, handbooks, and references
- Source-backed answers with retrieval metadata
- Backend-controlled retrieval and answer generation

### AI Analysis

- Mode-driven flight-test analysis from selected or active dataset versions
- Saved immutable analysis jobs with provenance snapshots
- Prompt-to-mode guard for mismatch detection and safer execution
- Analysis controls for:
  - deterministic confidence
  - retrieval coverage
  - applicability status
  - warning level
  - result strength
- Reopen/export support from saved analysis artifacts

### Deterministic / Bounded Engineering Modes

Current bounded engineering modes include:

- Takeoff Performance
- Landing Performance
- Performance / Climb / Air Data
- Handling / Control Response
- Vibration & Loads
- Flutter Support Pre-screen
- General Summary

These modes are bounded by available telemetry, implemented deterministic models, data quality, and explicit applicability limits. Missing signals or weak applicability are surfaced through warnings and controls rather than hidden.

### Reports

- PDF/report export from saved analysis artifacts
- Dataset, analysis-job, source, and control provenance
- Analysis controls and warning summaries
- Engineering narrative rendering with assumptions, limitations, and applicability boundaries
- Report charts generated from persisted parameter statistics
- Chart label readability improvements for long telemetry/channel names

### FRAT / Mission Risk

- FRAT assessment draft, score, review, approve, reject, finalize, and export workflow
- Score composition across mission/test profile, weather/environment, runway/operational, aircraft system status, and crew readiness categories
- Manual adjustments, analysis indicators, total score, risk band, and recommendation tracking
- Hard-stop flag support
- Linked-analysis support for analysis evidence and controls
- No-linked-analysis explanation and warning behavior where applicable
- No-Go, unacceptable, rejected, needs-review, and hard-stop report/explanation support

## Architecture

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL with pgvector support
- Runtime: Docker Compose
- External AI/RAG services are accessed through backend-controlled workflows

```text
User Browser -> Frontend -> Backend -> PostgreSQL
                                  -> External AI/RAG
                                  -> Reports/Exports
```

## Repository Structure

```text
backend/                                  FastAPI application, routers, models, tests
backend/migrations/                       SQL migration files
frontend/                                 React + TypeScript + Vite frontend
database/                                 Database initialization assets
docker/                                   Docker build files
docs/                                     Supporting documentation
Project_Documents/                        Project document assets
sample_data/                              Sample data fixtures and reference files
scripts/                                  Utility scripts
TODO.md                                  Backend/product roadmap and execution plan
frontend/TODO.md                         Frontend roadmap and UX planning
DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md Development history and implementation notes
FTIAS-MANUAL-V00.pdf                     Current FTIAS manual
RELEASE_READINESS.md                     Internal alpha readiness checklist
INTERNAL_ALPHA_NOTES.md                  Peer-facing internal alpha notes
```

## Getting Started

Build and start the backend and frontend services:

```powershell
docker compose up -d --build backend frontend
```

Check service status:

```powershell
docker compose ps
```

Follow backend logs:

```powershell
docker compose logs -f backend
```

The frontend is typically available at:

```text
http://localhost:5173
```

The backend API docs are typically available at:

```text
http://localhost:8000/docs
```

Environment values are read from `.env` and `.env.example`. AI/RAG features require the relevant backend environment variables, including an OpenAI API key when using OpenAI-backed workflows.

## Database Migrations

When new SQL migration files are added under `backend/migrations/`, apply them to the running PostgreSQL container before relying on the related feature.

PowerShell example:

```powershell
Get-Content backend/migrations/<migration_file>.sql -Raw | docker compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Validation

Common validation commands:

```powershell
black --check --diff backend/app backend/tests
pytest backend/tests -q
pnpm -C frontend run build
```

The frontend build may warn if Node.js is `20.18.1` while Vite expects `20.19+` or `22.12+`. The build can still complete successfully, but the runtime should be upgraded when practical.

## Documentation

- `FTIAS-MANUAL-V00.pdf` - current FTIAS manual
- `RELEASE_READINESS.md` - internal alpha readiness checklist, validation gate, and known limitations
- `INTERNAL_ALPHA_NOTES.md` - peer-facing technical preview notes and review workflow
- `LINUX_INTERNAL_DEPLOYMENT_GUIDE.md` - FTI-managed Linux internal alpha deployment guidance
- `WINDOWS_NATIVE_SETUP_GUIDE.md` - Windows native setup guidance when Docker is not approved
- `PEER_REVIEW_GUIDE.md` - structured guidance for internal alpha reviewers
- `TODO.md` - active backend/product roadmap and execution plan
- `frontend/TODO.md` - frontend roadmap and UX planning
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md` - implementation history and technical notes
- `Project_Documents/` - historical planning notes and future concepts, not primary user guidance
- `CONTRIBUTING.md` - contribution guidance
- `Docker_Troubleshooting_Guide.md` - Docker troubleshooting notes
- `LICENSE` - MIT License terms

GitHub Issues include templates for peer review feedback, bug reports, and feature requests.

## Roadmap

The active roadmap and deferred items are tracked in `TODO.md` and `frontend/TODO.md` rather than duplicated here.

Current readiness focus:

```text
Internal Alpha / Technical Preview readiness
```

Next planned step:

```text
Work IT dependency approval / Windows setup feasibility review
```

## Responsible Use / Limitations

- FTIAS supports engineering review, traceability, and repeatable analysis workflows.
- Deterministic outputs are bounded by available telemetry, assumptions, implemented models, and data quality.
- AI/RAG outputs are advisory and contextual; source citations and retrieval metadata must be reviewed.
- Flutter Support Pre-screen is pre-screening only and is not flutter clearance.
- Vibration and loads outputs are screening support only and are not formal loads substantiation.
- FRAT output supports mission-risk review but does not replace organizational authority, safety review, or formal approval processes.
- Certification, operational approval, and final safety decisions remain with qualified personnel and the governing organization.
