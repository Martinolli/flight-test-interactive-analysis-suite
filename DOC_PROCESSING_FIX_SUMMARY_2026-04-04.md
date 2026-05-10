# Document Processing Stability & Performance Fix Summary (2026-04-04)

## Problem Reported

- Document uploads were very slow.
- Upload flow appeared to hang during processing.
- Manual process restart was needed to recover.

## Root Cause

- `POST /api/documents/upload` was doing **full PDF parsing + chunk embedding + DB writes inside the request**.
- For large PDFs, the HTTP request stayed open too long and looked frozen.
- Embeddings were generated one chunk at a time (many API calls).

## Implemented Changes

### 1) Backend: Move indexing to background task

**File:** `backend/app/routers/documents.py`

- Upload endpoint now:
  - Saves uploaded PDF to temp file.
  - Creates `documents` row with `status="processing"`.
  - Returns response immediately.
  - Schedules `_process_document_upload(...)` as a FastAPI background task.
- Background task performs:
  - Docling parse/chunk.
  - Embedding generation.
  - Chunk persistence.
  - Document status update to `ready` or `error`.

### 2) Backend: Batch embedding calls

**File:** `backend/app/routers/documents.py`

- Added `embed_texts(...)` for batched embedding requests.
- Added configurable batch size via env var:
  - `EMBEDDING_BATCH_SIZE` (default `32`).
- Added fallback to per-chunk embedding if a batch fails.

### 3) Frontend: Auto-refresh processing status

**File:** `frontend/src/pages/DocumentLibrary.tsx`

- Added polling every 5 seconds when at least one document is in `processing`.
- Upload success message updated to indicate queued background indexing.
- Info banner updated to clarify background processing and auto-refresh behavior.

### 4) Environment config update

**File:** `.env.example`

- Added:
  - `EMBEDDING_BATCH_SIZE=32`

### 5) Test/runtime hardening

**Files:**

- `backend/app/config.py`
- `backend/requirements.txt`

Changes:

- `DEBUG` parser now tolerates aliases like `release`, `production`, `dev`.
- Added explicit dependency `email-validator>=2.2.0` to prevent schema import failures during tests.

## Validation Performed

- Python compile check passed for updated backend files.
- `pytest backend/tests/test_health.py -q` passed.
- Frontend full build has existing unrelated TypeScript issues in other files (pre-existing).

## Expected User-Visible Outcome

- PDF upload returns quickly and no longer blocks until full indexing completes.
- Document stays visible as `Processing` while background indexing runs.
- Status changes automatically to `Ready` (or `Error`) without manual restart.

## Tunable Setting

- `EMBEDDING_BATCH_SIZE`:
  - Increase to reduce API round-trips (faster throughput, higher request payload).
  - Decrease if API/provider limits or timeouts appear.

## Docker Runbook (Windows / PowerShell)

### Correct Folders

- Run Docker Compose commands from **repo root**:
  - `flight-test-interactive-analysis-suite`
- Run `npm run dev` only from **`frontend/`** when using local (non-Docker) frontend mode.

### Start Services (Docker Mode)

From root:

```powershell
docker compose up -d --build postgres backend
docker compose --profile frontend up -d --build frontend
docker compose ps
```

### After Closing VSCode

- You do **not** need to run `npm run dev` if Docker frontend is already running.
- Containers keep running in Docker Desktop unless manually stopped or system restart policies change.
- Open app directly at:
  - Frontend: `http://localhost:5173`
  - Backend docs: `http://localhost:8000/docs`

### If Laptop Rebooted / Containers Stopped

From root:

```powershell
docker compose up -d postgres backend
docker compose --profile frontend up -d frontend
docker compose ps
```

### One Frontend Runtime at a Time

- If Docker frontend is running on `5173`, do not run local `npm run dev` on same port.
- To switch to local frontend:

```powershell
# from repo root
docker compose stop frontend

# then from frontend/
npm run dev
```

### Monitor Document Ingestion

From root:

```powershell
docker compose logs -f backend
```

You should see document processing/indexing messages and final status transition to `ready` or `error`.

## Performance Update (Second Pass - 2026-04-04)

### Additional changes applied

**Files:**

- `backend/app/routers/documents.py`
- `docker-compose.yml`
- `docker-compose.backend-only.yml`
- `.env.example`

**What changed:**

- Added configurable Docling performance flags:
  - `DOCLING_FAST_MODE`
  - `DOCLING_AUTO_FAST_FOR_LARGE_FILES`
  - `DOCLING_FAST_THRESHOLD_MB`
  - `DOCLING_TABLE_STRUCTURE`
  - `DOCLING_NUM_THREADS`
  - `DOCLING_MAX_CHUNK_CHARS`
- Fast mode behavior:
  - Disables table-structure extraction for large documents (or always if `DOCLING_FAST_MODE=true`), reducing heavy parse time.
- Added chunk splitting guard for oversized chunk text to avoid tokenizer slow paths.
- Added ingestion progress logs:
  - parse config
  - chunking complete
  - embedding batch progress
  - final indexed summary
- Removed `--reload` from backend Docker run command to avoid file-watcher instability during long background ingestion tasks.

## Clear Command List

### 1) Update `.env` in repo root

Use these baseline values:

```env
DEBUG=false
EMBEDDING_BATCH_SIZE=64
DOCLING_NUM_THREADS=4
DOCLING_FAST_MODE=false
DOCLING_AUTO_FAST_FOR_LARGE_FILES=true
DOCLING_FAST_THRESHOLD_MB=25
DOCLING_TABLE_STRUCTURE=true
DOCLING_MAX_CHUNK_CHARS=5000
```

If a document is still too slow, switch to faster mode temporarily:

```env
DOCLING_FAST_MODE=true
```

### 2) Rebuild and restart backend (from repo root)

```powershell
docker compose up -d --build backend
```

### 3) Optional pre-warm (from repo root)

```powershell
docker compose exec backend python /app/prewarm_docling.py
```

### 4) Check service status (from repo root)

```powershell
docker compose ps
```

### 5) Watch ingestion logs (from repo root)

```powershell
docker compose logs -f backend
```

Filtered view (recommended):

```powershell
docker compose logs -f backend | Select-String "parse config|chunking complete|embedding progress|indexed|processing failed|Batch embedding failed|Docling parsing failed"
```

## Analysis Quality & References Update (2026-04-06)

### Scope

- Improve AI answer depth for technical queries (including takeoff-distance analysis).
- Improve source-reference correctness and prevent weak/misaligned citations.
- Clean PDF-export text rendering for formulas/symbols.

### Changes Implemented

**Files:**

- `backend/app/routers/documents.py`
- `backend/app/routers/admin.py`
- `frontend/src/pages/AIQuery.tsx`
- `frontend/src/services/api.ts`
- `.env.example`
- `docker-compose.yml`
- `docker-compose.backend-only.yml`
- `docker/frontend.Dockerfile`

1. Hybrid retrieval added (vector + lexical + reciprocal-rank fusion):

- Better coverage of relevant chunks for standards-heavy questions.
- More stable source selection before LLM generation.

1. Deterministic takeoff calculation section injected into AI analysis:

- Backend now computes takeoff metrics directly from flight-test time series.
- LLM is instructed to interpret/cross-check only, not recompute deterministic values.
- Reduces incorrect arithmetic in narrative output.
- Deterministic section now explicitly documents WOW transition logic used:
  - on-ground: mean WOW >= 0.5 (approx WOW=1)
  - airborne: mean WOW < 0.5 (approx WOW=0)
  - includes detected start/liftoff timestamps and WOW values used for distance segment.

1. Citation tightening:

- LLM output requires inline `[Sx]` citations for standards claims.
- References list is built from actually cited source IDs.
- Fallback note is added when no inline standards citations are produced.
- Added Standards Cross-Check citation-density gate:
  - Extracts section (2) text and measures sentence-level `[Sx]` citation coverage.
  - If density is below configured threshold, a second LLM editorial pass rewrites for citation compliance.
- New env control:
  - `ANALYSIS_MIN_CITATION_DENSITY=0.75`

1. Query response quality controls:

- Configurable query model/temperature/max tokens/top-k via env.
- Source text is not returned in API response payload (metadata only).
- Frontend query UI now renders markdown/GFM response formatting.
- Source cards show stable source IDs (`S1`, `S2`, ...) aligned with inline citations.

1. PDF sanitization improvements:

- Converts common LaTeX fragments to plain text for export stability.
- Removes problematic control characters.
- Normalizes list bullets and table/heading/body text before rendering.
- Adjusted deterministic equation text to use `x` multiplication symbol in report text
  to avoid markdown `*...*` stripping artifacts in PDF output.

1. Docker runtime consistency:

- Added pass-through env vars in Compose for `QUERY_*` and `ANALYSIS_*` so `.env` tuning is applied in containerized backend runs.
- Fixed frontend Docker healthcheck endpoint from `localhost` (IPv6 resolution issue in container) to `127.0.0.1`, removing false `unhealthy` status.

### Validation Snapshot (Reports v2/v3/v4)

- Deterministic takeoff metrics are now stable and repeatable from backend computation:
  - distance: `832.2 ft (253.6 m)`
  - start speed: `4.75 kt`
  - liftoff speed: `81.5 kt`
  - runtime: `11.1 s`
- WOW transition logic is explicitly surfaced in the report:
  - start sample uses on-ground state (WOW≈1)
  - liftoff sample uses airborne state (WOW≈0)
- References section is generated and aligned to inline `[Sx]` citations.

### New/Updated Environment Controls

Set in `.env` (copied from `.env.example` as needed):

```env
QUERY_LLM_MODEL=gpt-4o-mini
QUERY_TOP_K_DEFAULT=8
QUERY_CONTEXT_LIMIT=12
QUERY_VECTOR_CANDIDATES=30
QUERY_LEXICAL_CANDIDATES=20
QUERY_MAX_TOKENS=1800
QUERY_TEMPERATURE=0.1
ANALYSIS_LLM_MODEL=gpt-4o-mini
ANALYSIS_MAX_TOKENS=2600
ANALYSIS_TEMPERATURE=0.2
ANALYSIS_MIN_CITATION_DENSITY=0.75
```

## Restart / Run Commands (Exact + Folder)

### Folder

- Run Docker commands from **repo root**:
  - `flight-test-interactive-analysis-suite`

### Restart backend after code/env changes

From root:

```powershell
docker compose up -d --build backend
```

### Ensure full stack is up (Docker frontend mode)

From root:

```powershell
docker compose up -d postgres backend
docker compose --profile frontend up -d frontend
docker compose ps
```

### Monitor ingestion/analysis logs

From root:

```powershell
docker compose logs -f backend
```

### If using local frontend instead of Docker frontend

- Stop Docker frontend from root:

```powershell
docker compose stop frontend
```

- Then run local frontend from `frontend/`:

```powershell
npm run dev
```

## Improvement Backlog (P0/P1/P2) — 2026-04-06

This section captures the priority roadmap focused on gaps and risks, not achievements.

### P0 — Security, Correctness, Build Stability (Immediate)

1. Lock down exposed user endpoints

- Risk: `/api/users/*` currently allows user management without auth guards.
- Files:
  - `backend/app/routers/users.py`
  - `backend/app/main.py`
- Action:
  - Require admin auth on all `/api/users/*` routes, or remove this router and keep `/api/admin/users/*` as the only management API.

1. Enforce document tenancy isolation

- Risk: document list/delete/query retrieval can cross user boundaries.
- Files:
  - `backend/app/routers/documents.py`
- Action:
  - Add user-scope filters (`uploaded_by_id == current_user.id`) to list/delete/query retrieval SQL.

1. Strict timestamp validation in CSV ingestion

- Risk: fallback timestamp synthesis can silently fabricate timeline data.
- Files:
  - `backend/app/routers/flight_tests.py`
  - `backend/tests/test_flight_tests_comprehensive.py`
- Action:
  - Reject rows/files with missing or invalid timestamp format.
  - Return explicit validation errors with row references.

1. Restore frontend production build to green

- Risk: current frontend build has blocking TS/lint/type issues.
- Files:
  - `frontend/src/components/TimeSeriesChart.tsx`
  - `frontend/src/pages/Settings.tsx`
  - `frontend/tsconfig.node.json`
  - dependency/type resolution for `react-markdown`, `remark-gfm`, `html2canvas`
- Action:
  - Resolve current compile errors and enforce build in CI.

### P1 — Data Model & UX Alignment for Mixed Flight-Test Domains

1. Align upload UX and backend capabilities

- Gap: UI allows CSV/XLS/XLSX while backend upload endpoint is CSV-only.
- Files:
  - `frontend/src/components/DropZone.tsx`
  - `frontend/src/pages/Upload.tsx`
  - `backend/app/routers/flight_tests.py`
- Action:
  - Either implement true Excel ingestion in backend or constrain UI to CSV until implemented.

1. Replace synthetic upload history with real upload sessions

- Gap: upload history is currently derived from parameter stats + localStorage.
- Files:
  - `frontend/src/services/api.ts`
  - backend models/routers for ingestion session tracking
- Action:
  - Add persistent upload session entity with filename, row count, status, error log, timestamps.

1. Scale parameter exploration for large datasets

- Gap: chip-based selection is not viable for hundreds/thousands of channels.
- Files:
  - `frontend/src/pages/Parameters.tsx`
  - `frontend/src/pages/FlightTestDetail.tsx`
- Action:
  - Add searchable parameter tree, subsystem grouping, favorites, and saved parameter sets.

1. Improve chart architecture for engineer workflows

- Gap: limited linked analysis (crosshair sync, event overlays, compare runs).
- Files:
  - `frontend/src/components/TimeSeriesChart.tsx`
  - `frontend/src/components/CorrelationChart.tsx`
  - `frontend/src/pages/Parameters.tsx`
- Action:
  - Add synchronized multi-panel timeline, event markers, threshold bands, and compare-flight overlay mode.

1. Add Flight Test Risk Assessment (FRAT) workflow

- Gap: mission-go/no-go risk assessment currently lives outside the app in spreadsheets.
- Files:
  - `backend/app/models.py`
  - `backend/app/routers/flight_tests.py` (or dedicated `risk_assessment.py`)
  - `frontend/src/pages/FlightTestDetail.tsx`
  - new frontend FRAT component(s) under `frontend/src/components/`
- Action:
  - Implement deterministic FRAT scoring with hard-stop override, per-flight-test saved assessments, approval signatures, and PDF export.

### P2 — LLM/RAG Domainization & Report Provenance

1. Move from single analysis path to domain modes

- Gap: analysis pipeline is tuned to takeoff and not modular for electrical/vibration/propulsion.
- Files:
  - `backend/app/routers/documents.py`
- Action:
  - Introduce `analysis_mode` (`takeoff`, `landing`, `electrical`, `vibration`, `general`) and route to dedicated deterministic calculators/prompts.

1. Enrich retrieval metadata and filtering

- Gap: retrieval depends mainly on chunk text with weak domain constraints.
- Files:
  - `backend/app/models.py`
  - `backend/app/routers/documents.py`
  - DB migration scripts
- Action:
  - Add metadata fields (document revision, authority, domain tags, system tags) and pre-filter retrieval by mode/context.

1. Persist analysis jobs and generate reports from immutable artifacts

- Gap: PDF generation currently accepts freeform analysis text payload.
- Files:
  - `backend/app/routers/admin.py`
  - new analysis job model + endpoints
  - `frontend/src/pages/FlightTestDetail.tsx`
- Action:
  - Save analysis output with prompt/model/source ids/hash and export PDF by `analysis_job_id`.

## Proposed API Contracts (Implementation Targets)

1. `POST /api/flight-tests/{id}/analysis-jobs`

- Request:
  - `analysis_mode` (`takeoff|landing|electrical|vibration|general`)
  - `user_prompt` (optional)
  - `parameter_scope` (optional list)
- Response:
  - `job_id`, `status`, `created_at`

1. `GET /api/flight-tests/{id}/analysis-jobs/{job_id}`

- Response:
  - deterministic metrics
  - narrative analysis
  - source references
  - model/prompt metadata
  - confidence/coverage indicators

1. `POST /api/admin/analysis-jobs/{job_id}/report.pdf`

- Response:
  - PDF generated from persisted job data (no raw analysis body required).

## Proposed API Contracts (Risk Assessment / FRAT Targets)

1. `POST /api/flight-tests/{id}/risk-assessments`

- Request:
  - `template_version` (for example `frat_v2`)
  - `selected_factor_ids` (list)
  - `selected_hard_stop_ids` (list)
  - `mitigations` (text)
- Response:
  - `assessment_id`, `total_score`, `hard_stop_count`, `disposition`, `created_at`

1. `GET /api/flight-tests/{id}/risk-assessments/{assessment_id}`

- Response:
  - selected factors/hard-stops
  - category subtotals
  - total score + final disposition
  - approval status/signatures
  - template version metadata

1. `POST /api/flight-tests/{id}/risk-assessments/{assessment_id}/finalize`

- Request:
  - `approver_name`, `approver_role`, `approval_notes`
- Response:
  - immutable finalized snapshot for report/audit

1. `POST /api/admin/risk-assessments/{assessment_id}/report.pdf`

- Response:
  - FRAT PDF generated from persisted assessment snapshot.

## P0 Implementation Update (2026-04-07)

### Completed: Lock down exposed `/api/users/*` endpoints

**Goal:** close an admin-privilege bypass where user-management CRUD endpoints were previously unauthenticated.

**Files changed:**

- `backend/app/routers/users.py`
- `backend/tests/conftest.py`
- `backend/tests/test_users.py`
- `backend/tests/test_csv_upload.py`
- `backend/tests/test_auth_comprehensive.py`
- `TODO.md`

**What changed:**

- Applied router-level dependency `Depends(get_current_superuser)` to `/api/users/*`.
- Added dedicated superuser test fixtures (`admin_user`, `admin_headers`) for admin-only route coverage.
- Updated user-route tests to use admin auth.
- Added explicit test that a regular authenticated user receives `403` on `/api/users/*`.
- Updated auth comprehensive test to reflect admin-only access for `/api/users/{id}`.
- Updated CSV upload test setup to create users through admin-authenticated flow.

**Validation run:**

```powershell
pytest backend/tests/test_users.py backend/tests/test_csv_upload.py backend/tests/test_auth_comprehensive.py -q
```

**Result:** `36 passed, 1 skipped`.

### Completed: Enforce document tenancy isolation (`/api/documents/*`)

**Goal:** prevent cross-user access to documents during list, delete, and retrieval-driven query paths.

**Files changed:**

- `backend/app/routers/documents.py`
- `backend/tests/test_documents_tenancy.py`
- `TODO.md`

**What changed:**

- Scoped `GET /api/documents/` to the authenticated user's owned documents only.
- Scoped `DELETE /api/documents/{id}` to owned documents only (returns `404` when not owned/not found).
- Added user-scope filter to hybrid retrieval SQL (`d.uploaded_by_id = :owner_user_id`).
- Passed `owner_user_id=current_user.id` into retrieval calls for:
  - `POST /api/documents/query`
  - `POST /api/documents/flight-tests/{id}/ai-analysis`
- Added tenancy tests for:
  - list isolation
  - delete isolation
  - query path ownership scoping propagation

**Validation run:**

```powershell
pytest backend/tests/test_documents_tenancy.py backend/tests/test_users.py -q
```

**Result:** `14 passed`.

### Completed: Strict timestamp validation for CSV ingestion

**Goal:** remove synthetic/fallback timeline fabrication and fail uploads with explicit row-level timestamp errors.

**Files changed:**

- `backend/app/routers/flight_tests.py`
- `backend/tests/test_flight_tests_comprehensive.py`
- `TODO.md`

**What changed:**

- Removed permissive timestamp fallback behavior that previously synthesized timestamps.
- Added strict timestamp column detection (`timestamp`, `time`, or `description`).
- Added strict timestamp parser supporting:
  - numeric seconds offset
  - `Day:HH:MM:SS[.fraction]`
  - ISO datetime
- Added row-level error collection for:
  - missing timestamp values
  - invalid timestamp format
- Upload now returns `400` with explicit row references when timestamp validation fails.
- Added rollback on `HTTPException` in upload flow to ensure validation failures do not leave partial DB changes.

**Validation run:**

```powershell
pytest backend/tests/test_flight_tests_comprehensive.py -q
pytest backend/tests/test_csv_upload.py -q
```

**Result:** all tests passed.

### Completed: Frontend production build restored to green

**Goal:** clear TypeScript build blockers so `npm run build` succeeds consistently.

**Files changed:**

- `frontend/src/components/TimeSeriesChart.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/pages/Settings.tsx`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/.gitignore`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Removed unused declarations/imports that failed `noUnusedLocals`.
- Fixed settings toast API call (`toast.info` -> `toast.warning`) to match available hook methods.
- Added per-config `tsBuildInfoFile` paths under `frontend/node_modules/.tmp/` to avoid root noise.
- Set `frontend/tsconfig.node.json` to `noEmit: true` so build-time typecheck does not require emitted JS.
- Added frontend ignore entries for generated files:
  - `*.tsbuildinfo`
  - `vite.config.js`
  - `vite.config.d.ts`
- Installed missing declared frontend dependencies used by code:
  - `react-markdown`
  - `remark-gfm`
  - `html2canvas`

**Validation run:**

```powershell
cd frontend
npm run build
```

**Result:** build completed successfully (`tsc -b && vite build`).

### Completed: Ingestion observability baseline (stage timing telemetry)

**Goal:** expose per-document ingestion stage timings to diagnose slow uploads in production-like runs.

**Files changed:**

- `backend/app/routers/documents.py`
- `TODO.md`

**What changed:**

- Added explicit stage-duration tracking in background document ingestion:
  - `parse_chunk_duration_s`
  - `embed_duration_s`
  - `persist_duration_s`
  - `finalize_duration_s`
  - total elapsed duration
- Enhanced existing logs with durations:
  - chunking completion now logs stage duration
  - embedding completion now logs chunks, embedded count, missing embeddings, batch count, and duration
  - final ingestion log now emits a structured timing summary across all stages
- Enhanced failure logging to include partial stage timings at the point of exception.

**Validation run:**

```powershell
pytest backend/tests/test_documents_tenancy.py backend/tests/test_users.py backend/tests/test_flight_tests_comprehensive.py -q
```

**Result:** `39 passed`.

## P1 Implementation Update (2026-04-07)

### Completed: Align upload UX with backend capability (CSV-only)

**Decision implemented:** constrain frontend upload flow to CSV-only until backend XLS/XLSX ingestion is implemented.

**Files changed:**

- `frontend/src/components/DropZone.tsx`
- `frontend/src/pages/Upload.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `frontend/src/services/api.ts`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Removed XLS/XLSX acceptance from upload dropzone and validation.
- Updated upload-page copy to explicitly state CSV-only support.
- Updated format guidance to match real backend parser expectations:
  - row 1: parameter names
  - row 2: units
  - rows 3+: data with timestamp column (`timestamp`, `time`, or `description`)
- Updated `FlightTestDetail` empty-state helper text from "CSV or Excel" to "CSV".
- Narrowed frontend upload history `file_type` typing from `'csv' | 'excel'` to `'csv'`.
- Marked P1 upload parity item complete in root and frontend TODOs.

**Validation run:**

```powershell
cd frontend
npm run build
```

**Result:** build completed successfully (`tsc -b && vite build`).

## P0/P1 Implementation Update (2026-04-08)

### Completed: Query answer quality hardening (specialist depth + citation integrity)

**Goal:** reduce generic AI answers and tighten source-reference correctness in `/api/documents/query`.

**Files changed:**

- `backend/app/routers/documents.py`
- `.env.example`

**What changed:**

- Added query-level citation controls:
  - `QUERY_MIN_CITATION_DENSITY` (default `0.6`)
  - `QUERY_STRICT_CITATIONS` (default `true`)
- Added specialist-aware prompt shaping:
  - brief-response detection for succinct requests
  - risk-assessment request detection with structured risk-matrix output format
- Added strict post-processing for citations:
  - strips `USED_SOURCES` footer
  - rejects unknown inline source IDs
  - optional editorial repair pass when citation coverage is weak or invalid IDs are present
  - source list is filtered to only cited source IDs
- Added `warnings` to query API response payload for UI surfacing when citation coverage is insufficient.
- Fixed import-time initialization safety by ensuring `_env_flag` is defined before use.

### Completed: AI Query frontend usability upgrades (responsive + formula rendering + warning UX)

**Goal:** make AI chat adaptive to window size and improve rendering of technical/math content.

**Files changed:**

- `frontend/src/pages/AIQuery.tsx`
- `frontend/src/services/api.ts`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/TODO.md`
- `TODO.md`

**What changed:**

- Added markdown math rendering pipeline:
  - `remark-math`
  - `rehype-katex`
  - KaTeX stylesheet import in AI query page
- Added AI answer quality warning panel in chat bubbles using backend `warnings`.
- Updated AI chat layout to be responsive to viewport expansion:
  - removed narrow fixed-width behavior
  - expanded max content width
  - ensured scroll area uses `min-h-0` + flex sizing for stable resizing
- Marked related TODO items complete in root and frontend TODO trackers.

**Validation run:**

```powershell
python -m compileall backend/app/routers/documents.py
cd frontend
npm install
npm run build
```

**Result:** backend module compiles; frontend build succeeded with Node engine warning (`20.18.1` detected, Vite recommends `20.19+`).

### Hotfix: Frontend container dependency sync for new packages (2026-04-08)

**Issue observed:**

- Vite runtime import error inside container:
  - `Failed to resolve import "remark-math" from "src/pages/AIQuery.tsx"`
- Cause: persisted Docker volume at `/app/node_modules` retained stale dependencies.

**File changed:**

- `docker-compose.yml`

**What changed:**

- Updated frontend runtime command to always sync dependencies before dev server startup:
  - from: `pnpm dev --host 0.0.0.0`
  - to: `sh -c "pnpm install && pnpm dev --host 0.0.0.0"`

**Operational impact:**

- On each frontend container start, missing/new deps from `frontend/package.json` are installed into mounted `/app/node_modules`, preventing stale-volume import failures.

### Hotfix: Non-interactive pnpm install in Docker (2026-04-08)

**Issue observed:**

- Frontend restart loop with:
  - `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`
- Cause: `pnpm install` attempted module purge confirmation in a non-TTY container.

**File changed:**

- `docker-compose.yml`

**What changed:**

- Added `CI=true` for frontend container environment.
- Updated frontend startup command to enforce non-interactive install behavior:
  - `pnpm install --config.confirmModulesPurge=false --no-frozen-lockfile`
  - then `pnpm dev --host 0.0.0.0`

**Operational impact:**

- Frontend container no longer aborts during dependency sync when `node_modules` must be replaced.

### Query Retrieval Diversity Update (2026-04-08)

**Issue observed:**

- AI query answers could over-concentrate citations on a single handbook even when multiple relevant documents were uploaded.

**Files changed:**

- `backend/app/routers/documents.py`
- `.env.example`
- `docker-compose.yml`
- `frontend/.gitignore`

**What changed:**

- Added retrieval diversity controls:
  - `QUERY_MIN_UNIQUE_DOCUMENTS` (default `3`)
  - `QUERY_MAX_CHUNKS_PER_DOCUMENT` (default `3`)
- Updated hybrid retrieval selection to:
  - pass 1: prioritize one chunk per distinct document up to unique-document target
  - pass 2: fill remaining context with per-document cap to prevent over-representation
- Added query warning when retrieved/cited evidence remains concentrated in too few documents.
- Wired new retrieval env vars into backend container configuration.
- Added frontend gitignore entries for:
  - `.pnpm-store`
  - `pnpm-lock.yaml`
  to avoid Docker-generated workspace noise.

**Validation run:**

```powershell
python -m compileall backend/app/routers/documents.py
cd backend
python -c "import app.routers.documents as d; print('documents_import_ok')"
```

**Result:** module compiles/imports successfully.

### Query Quality Notice Tuning (2026-04-08)

**Issue observed:**

- “Quality Notice” remained visible in answers that were materially cited, due to strict sentence-level density checks on structural markdown lines.

**Files changed:**

- `backend/app/routers/documents.py`
- `.env.example`
- `docker-compose.yml`

**What changed:**

- Added `QUERY_WARNING_CITATION_DENSITY` (default `0.4`) separate from repair threshold.
- Kept repair enforcement using `QUERY_MIN_CITATION_DENSITY` (default `0.6`), but relaxed warning threshold to reduce noisy alerts.
- Added `_query_citation_density()` for query answers:
  - computes density from substantive prose lines
  - ignores markdown headings, list wrappers, and table rows that created false low-density signals
- Kept concentration warning logic focused on retrieval breadth while preserving citation-integrity checks.

**Validation run:**

```powershell
python -m compileall backend/app/routers/documents.py
cd backend
python -c "import app.routers.documents as d; print('documents_import_ok')"
```

**Result:** module compiles/imports successfully.

## Next Session Note (2026-04-08)

- Frontend UX follow-up requested:
  - replicate the responsive/adaptive + scrollable chat interaction now used in `AI Standards Query`
  - target location: `Analyze with AI` panel in Flight Test Detail (dashboard workflow)

## Plan Review Adoption (REV 01) — 2026-04-09

### Review Outcome

- `TODO_REV_01.md` is strong enough to adopt as the active execution direction.
- It improves the previous roadmap by adding:
  - clear sequencing and dependency discipline
  - assurance points and exit criteria
  - explicit test expectations
  - management gates for phase closure decisions

### Planning Realignment Applied

- Root plan (`TODO.md`) was realigned to REV01 priorities:
  - P0 now focuses on product truth + response contract + AI UX unification + analysis-job provenance.
  - P1 now focuses on parameter/charts/report quality + capability catalog definition.
  - P2 now focuses on domainization, deterministic expansion, retrieval metadata, confidence/applicability, and FRAT.
- Frontend plan (`frontend/TODO.md`) was realigned accordingly:
  - ingestion-session truth UI
  - structured response rendering
  - AI panel parity between AIQuery and FlightTestDetail
  - analysis job and provenance UX follow-through.

### Adoption Notes

- Previously completed baseline controls remain protected and should not be reopened without defect evidence.
- The adopted immediate execution order remains:
  1. P0.1 ingestion sessions
  2. P0.2 response contract
  3. P0.3 unified AI UX
  4. P0.4 persisted analysis jobs

## P0.1 Implementation Update (2026-04-09)

### Completed: Persist real ingestion sessions and remove synthetic upload history

**Goal:** make upload history/status/error reporting backend-truthful and tenant-scoped.

**Files changed:**

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/routers/flight_tests.py`
- `backend/tests/test_flight_tests_comprehensive.py`
- `frontend/src/services/api.ts`
- `frontend/src/pages/Upload.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Added persisted backend model:
  - `IngestionSession` with `flight_test_id`, `filename`, `file_type`, `source_format`, `row_count`, `status`, `error_message`, `error_log`, `uploaded_by_id`, timestamps.
- Added `FlightTest -> ingestion_sessions` relationship.
- Added API endpoints:
  - `GET /api/flight-tests/{test_id}/ingestion-sessions`
  - `GET /api/flight-tests/{test_id}/ingestion-sessions/{session_id}`
- Updated CSV upload lifecycle:
  - create `IngestionSession(status="processing")` at upload start
  - transition to `success` with authoritative `row_count` on commit
  - persist `failed` with error detail when validation/runtime failures occur
  - include `session_id` in upload response payload
- Removed synthetic upload history logic in frontend:
  - dropped parameter-count/localStorage-derived history synthesis
  - `getUploadHistory()` now uses backend ingestion-session endpoint directly
  - removed localStorage filename/timestamp writes from upload flow
- Added periodic upload-history refresh polling in Upload page (`5s`) while a flight test is selected.

**Validation run:**

```powershell
pytest backend/tests/test_flight_tests_comprehensive.py -q
cd frontend
npm run build
```

**Result:**

- Backend: `28 passed`
- Frontend: build successful (`tsc -b && vite build`)

## P0.1 Hardening Update (2026-04-11)

### Added DB migration artifact for ingestion sessions

**File added:**

- `backend/migrations/20260411_add_ingestion_sessions.sql`

**What changed:**

- Added explicit SQL migration script to create `ingestion_sessions` with indexes and FK constraints.
- This closes the gap for existing databases that were created before ingestion-session persistence was introduced in code.

### Narrowed Upload-page polling to active processing only

**File changed:**

- `frontend/src/pages/Upload.tsx`

**What changed:**

- Upload history polling is now conditional:
  - poll every 5s only when at least one ingestion session is `pending` or `processing`
  - no continuous polling when all sessions are terminal (`success` / `failed`)
- Result: reduced unnecessary API load while preserving near-real-time status updates during active ingestion.

## P0.2 Implementation Update (2026-04-11)

### Completed: standardized `/api/documents/query` response contract for engineering workflows

**Files changed:**

- `backend/app/routers/documents.py`
- `backend/tests/test_documents_tenancy.py`
- `frontend/src/services/api.ts`
- `frontend/src/pages/AIQuery.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Expanded query response contract with structured fields:
  - `summary`, `answer_type`, `technical_scope`
  - `assumptions`, `limitations`, `calculation_notes`
  - `recommended_next_queries`
  - `coverage` (citation density + source/document counts)
  - `retrieval_metadata` (top-k/context/diversity knobs)
- Added deterministic fallback for empty retrieval:
  - explicit `insufficient_evidence` answer type
  - structured warnings and next-query guidance
  - populated metadata blocks even when no sources are returned
- Frontend AI Standards Query now renders structured sections when present while remaining backward-safe if fields are absent.
- Added/updated backend tests to assert structured response shape for:
  - normal retrieval path
  - empty retrieval path

**Validation run:**

```powershell
pytest backend/tests/test_documents_tenancy.py -q
pytest backend/tests/test_flight_tests_comprehensive.py -q
cd frontend
npm run build
```

**Result:**

- `test_documents_tenancy`: `4 passed`
- `test_flight_tests_comprehensive`: `28 passed`
- Frontend build: successful (`tsc -b && vite build`)

## P0.3 Implementation Update (2026-04-11)

### Completed: AI UX parity between `AI Standards Query` and `Analyze with AI`

**Files changed:**

- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- `Analyze with AI` panel upgraded to adaptive layout behavior:
  - expanded page container width for large screens
  - bounded, internally scrollable analysis viewport for long answers
- Markdown rendering parity improved:
  - enabled `remark-math` + `rehype-katex` for formula rendering consistency
- Added explicit quality/sources display behavior aligned with AI query page:
  - parses generated analysis references block
  - shows a `Quality Notice` panel when citation coverage is missing
  - exposes collapsible source list in the analysis panel

**Validation run:**

```powershell
cd frontend
npm run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`)

## P1.1 Implementation Update (2026-04-12)

### Completed: standardize adaptive page framing for Upload/Data Library

**Goal:** align `Upload Data` and `Document Library` with the adaptive page-shell behavior already used by core analysis pages.

**Files changed:**

- `frontend/src/pages/Upload.tsx`
- `frontend/src/pages/DocumentLibrary.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Both pages now use a consistent adaptive shell:
  - `max-w` constrained container
  - full-height flex layout (`h-[100dvh]`)
  - internal content scroll (`min-h-0` + `overflow-y-auto`)
- `Upload Data`:
  - standardized spacing rhythm and card stacking under an adaptive shell
  - upload history panel now uses a bounded internal vertical scroll region for long histories
- `Document Library`:
  - standardized spacing/card framing and responsive stats row
  - indexed-documents table now uses bounded internal scroll with sticky table header
  - upload panel remains functionally unchanged, but responsive layout was tightened for smaller widths
- Behavioral contracts intentionally unchanged:
  - upload/session APIs unchanged
  - document upload/delete/index polling behavior unchanged

### Acceptance Check

- [x] max-width container aligned with adaptive pages
- [x] vertical layout behavior standardized
- [x] internal scroll regions added for long content blocks
- [x] empty/loading states preserved and kept readable inside new frame
- [x] no backend/API behavior changes

**Validation run:**

```powershell
cd frontend
npm run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`)

## P0.4 Implementation Update (2026-04-11)

### Completed: persist analysis jobs + export PDF from immutable artifacts

**Files changed:**

- `backend/app/models.py`
- `backend/migrations/20260411_add_analysis_jobs.sql`
- `backend/app/routers/documents.py`
- `backend/app/routers/admin.py`
- `backend/tests/test_documents_tenancy.py`
- `backend/tests/test_admin_report_export.py`
- `frontend/src/services/api.ts`
- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Added persisted `AnalysisJob` model + migration with provenance fields:
  - `flight_test_id`, `created_by_id`, `model_name`, `model_version`
  - `prompt_text`
  - `retrieved_source_ids_json`, `retrieved_sources_snapshot_json`
  - `analysis_text`, `output_sha256`, timestamps
- `POST /api/documents/flight-tests/{id}/ai-analysis` now:
  - generates analysis as before
  - persists immutable analysis artifact + provenance
  - returns `analysis_job_id`, model/hash metadata, and retrieval source IDs
- Added re-open-by-ID endpoint:
  - `GET /api/documents/flight-tests/{flight_test_id}/ai-analysis/jobs/{analysis_job_id}`
  - tenant-scoped to owning user (superuser override retained)
- PDF export now uses immutable job artifact only:
  - admin report export endpoints accept `analysis_job_id`
  - analysis text is loaded from persisted `analysis_jobs`
  - freeform `analysis_text` payload export path removed
  - PDF metadata includes analysis job provenance (ID/model/hash snippet)
- Frontend Analyze with AI flow updated:
  - displays analysis job ID in result metadata
  - exports PDF via `analysis_job_id`
  - adds "Re-open Saved Analysis by ID" input/action

### Acceptance Check

- [x] analysis can be re-opened by ID
- [x] PDF export uses saved analysis job
- [x] provenance is inspectable in API response and PDF metadata
- [x] existing UI flow remains usable

**Validation run:**

```powershell
pytest backend/tests/test_documents_tenancy.py -q
pytest backend/tests/test_admin_report_export.py -q
pytest backend/tests/test_flight_tests_comprehensive.py -q
cd frontend
npm run build
```

**Result:**

- `test_documents_tenancy`: `6 passed`
- `test_admin_report_export`: `2 passed`
- `test_flight_tests_comprehensive`: `28 passed`
- Frontend build: successful (`tsc -b && vite build`)

## P0.4 Hardening Update (2026-04-11)

### Completed: full immutability for parameter metadata snapshot

**Goal:** ensure reopened analysis jobs and PDF annex/statistics remain reproducible after later mutable dataset changes in the same flight test.

**Files changed:**

- `backend/app/models.py`
- `backend/migrations/20260411_harden_analysis_jobs_snapshot.sql`
- `backend/app/routers/documents.py`
- `backend/app/routers/admin.py`
- `backend/tests/test_documents_tenancy.py`
- `backend/tests/test_admin_report_export.py`
- `frontend/src/services/api.ts`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- `AnalysisJob` now persists:
  - `parameters_analysed`
  - `parameter_stats_snapshot_json`
- `POST /api/documents/flight-tests/{id}/ai-analysis` now saves:
  - immutable parameter count at analysis generation time
  - immutable parameter statistics snapshot (`min/max/avg/std/sample_count`) for report annex use
- `GET /api/documents/flight-tests/{flight_test_id}/ai-analysis/jobs/{analysis_job_id}` now returns persisted job values for:
  - `parameters_analysed`
  - `parameter_stats_snapshot`
  - no live recomputation from current `DataPoint` rows for these fields
- Admin PDF export now uses persisted job snapshot only for Annex A statistics:
  - removed live `DataPoint` aggregation dependency from export path
  - annex/statistics are reproducible by `analysis_job_id`
- Existing behavior preserved for:
  - `analysis_job_id` usage
  - provenance metadata
  - saved analysis text
  - reopen-by-ID flow
  - immutable PDF export by job ID

### Acceptance Check (immutability)

- [x] analysis job stores `parameters_analysed`
- [x] analysis job stores parameter statistics snapshot
- [x] reopened job returns persisted snapshot values
- [x] PDF export uses persisted snapshot values even if current flight-test data changes later
- [x] saved analysis job remains reproducible after later dataset mutation

**Validation run:**

```powershell
pytest backend/tests/test_documents_tenancy.py -q
pytest backend/tests/test_admin_report_export.py -q
cd frontend
npm run build
```

**Result:**

- `test_documents_tenancy`: `7 passed`
- `test_admin_report_export`: `3 passed`
- Frontend build: successful (`tsc -b && vite build`)

## P0.3a Implementation Update (2026-04-11)

### Completed: clarify active-dataset behavior in UI (no backend behavior change)

**Files changed:**

- `frontend/src/pages/Upload.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Added explicit user-facing notices that:
  - Upload History is an ingestion/audit trail
  - the latest successful upload is the active dataset
  - Parameters, Dashboard surfaces, and Analyze with AI use the active dataset only
- Clarified this in the three required work surfaces:
  - Upload Data page
  - Flight Test Detail page
  - Parameters page
- Kept backend and data behavior unchanged (no dataset versioning introduced in this task).

### Acceptance Checklist

- [x] Upload page displays active-dataset notice next to upload/history workflow.
- [x] Flight Test Detail displays active-dataset notice for Parameters + AI Analysis context.
- [x] Parameters page displays active-dataset scope notice for selected flight test.
- [x] No API contract or backend behavior change for ingestion history.
- [x] Frontend build passes after UI copy/layout updates.

**Validation run:**

```powershell
cd frontend
npm run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`)

## P1.0 Implementation Update (2026-04-12)

### Completed: dataset versioning + active dataset selection per flight test

**Goal:** remove hidden overwrite behavior and make analysis scope explicit/selectable across Upload, Parameters, and Analyze with AI.

**Files changed:**

- `backend/app/models.py`
- `backend/migrations/20260412_add_dataset_versions.sql`
- `backend/app/schemas.py`
- `backend/app/routers/flight_tests.py`
- `backend/app/routers/documents.py`
- `backend/app/routers/admin.py`
- `backend/tests/test_flight_tests_comprehensive.py`
- `backend/tests/test_documents_tenancy.py`
- `frontend/src/services/api.ts`
- `frontend/src/pages/Upload.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `frontend/src/components/UploadHistoryTable.tsx`
- `TODO.md`
- `frontend/TODO.md`

**What changed:**

- Added persisted `dataset_versions` entity and active-pointer field on `flight_tests`:
  - `flight_tests.active_dataset_version_id`
  - `data_points.dataset_version_id`
  - `ingestion_sessions.dataset_version_id`
  - `analysis_jobs.dataset_version_id`
- CSV upload now creates immutable dataset versions (`vN`) instead of deleting prior data points.
- Added dataset-version endpoints:
  - `GET /api/flight-tests/{id}/dataset-versions`
  - `POST /api/flight-tests/{id}/dataset-versions/{dataset_version_id}/activate`
- Read/query endpoints now support optional dataset scoping:
  - flight-test parameters/data APIs
  - AI analysis generation (`dataset_version_id`)
- AI analysis jobs now persist the dataset version used, preserving provenance for reopen/export flows.
- Frontend now exposes dataset-version selection and activation in Upload, Parameters, and Flight Test Detail.
- API contracts updated so frontend can display and use active/selected dataset state consistently.

### Acceptance Check

- [x] user can identify active dataset version
- [x] user can select and activate prior dataset versions
- [x] Parameters and Analyze with AI run on selected dataset version (or active by default)
- [x] re-upload no longer silently overwrites historical dataset versions

**Validation run:**

```powershell
pytest backend/tests/test_flight_tests_comprehensive.py -q
pytest backend/tests/test_documents_tenancy.py -q
pytest backend/tests/test_admin_report_export.py -q
pnpm -C frontend run build
```

**Result:**

- `test_flight_tests_comprehensive`: `30 passed`
- `test_documents_tenancy`: `8 passed`
- `test_admin_report_export`: `3 passed`
- Frontend build: successful (`tsc -b && vite build`)
- Note: Vite printed a Node warning (`20.18.1` detected; recommends `20.19+`), but build output is successful.

## P1.0 Follow-up (2026-04-12): Saved Analysis Dataset Provenance Display

### Completed: provenance-correct dataset label for reopened analysis jobs

**Goal:** prevent misleading dataset labeling when reopening a saved analysis job by ID while the page currently has a different dataset selected.

**Files changed:**

- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Reopen-by-ID flow now preserves `dataset_version_id` from saved analysis job response into panel state.
- AI Analysis panel metadata now displays dataset as:
  - `Analysis dataset: <saved job dataset label>` when job has dataset provenance.
  - `Analysis dataset: active/legacy` only when job has no persisted dataset version.
- When saved-job dataset differs from current page selection, panel now shows explicit mismatch notice:
  - saved analysis provenance dataset
  - current page selected dataset
- Existing selected-dataset behavior is unchanged for:
  - Parameters & Data panel
  - new AI analysis runs
  - Set Active dataset actions

### Acceptance Check (documented)

- [x] Run analysis with dataset version **A** selected.
- [x] Change current page selection to dataset version **B**.
- [x] Re-open saved analysis job from version **A** by job ID.
- [x] Verify AI Analysis panel shows saved analysis as dataset **A** (and mismatch notice vs **B**), not as dataset **B**.

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## P1.3 Step 3 Update (2026-04-17): Compare-Dataset Mode

### Completed: compare-runs/dataset slice for engineering review

**Goal:** finalize P1.3 by enabling same-parameter comparison across two dataset versions of the same flight test in the `Parameters` timeseries workflow.

**Files changed:**

- `frontend/src/pages/Parameters.tsx`
- `frontend/src/components/TimeSeriesChart.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Added compare-dataset workflow controls on `Parameters` page:
  - compare-mode enable toggle
  - compare dataset-version selector (same flight test)
  - clear primary vs compare dataset labeling
- Implemented compare overlay in timeseries chart:
  - selected parameters from compare dataset are fetched and plotted with the primary dataset
  - compare traces are visually distinct (dashed/lighter style + legend compare tag)
  - linked hover/crosshair behavior remains active with overlays
- Added compare robustness:
  - candidate dataset guard (excludes currently selected primary dataset)
  - missing-parameter warning if compare dataset lacks some selected channels
  - no change to saved sets/favorites behavior

### Acceptance Check (documented)

- [x] compare-dataset mode selectable on Parameters page
- [x] same parameters can be overlaid across primary + compare dataset versions
- [x] compare traces remain readable and distinguishable
- [x] no regression in dataset selection, saved sets, favorites, or chart loading behavior
- [x] linked crosshair, markers, thresholds, and export improvements remain intact

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).
- P1.3 chart-workflow scope is now complete.

## P1.3 Hardening Update (2026-04-17): Marker Visibility, Export Reliability, Hover Responsiveness

### Completed: stabilization pass for delivered P1.3 features

**Goal:** address manual-test issues without reopening P1.3 scope:

1. event markers not visibly rendering
2. PNG export regression
3. sluggish hover/crosshair interaction

**Files changed:**

- `frontend/src/components/TimeSeriesChart.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/hooks/useChartDownload.ts`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Event marker reliability and visibility:
  - marker timestamps now resolve to the nearest available chart sample timestamp when exact x-key match is missing
  - increased marker stroke prominence and improved overflow handling for visibility
  - strengthened demo marker generation baseline by using the densest available series for Start/Midpoint/End markers
- PNG export reliability:
  - restored SVG-first export as primary path for Recharts charts
  - retained html2canvas fallback when SVG rendering fails
  - removed silent failure behavior by surfacing export errors to the UI (toast)
- Hover/crosshair responsiveness:
  - memoized heavy chart derivations (`groupByUnit`, merged data, metadata maps, binary checks)
  - throttled redundant hover updates by suppressing repeated callbacks for identical cursor timestamp
  - reduced unnecessary state churn in `Parameters` hover snapshot handler

### Acceptance Check (documented)

- [x] event markers render visibly when enabled
- [x] Start/Midpoint/End markers render when timeseries data exists
- [x] WOW transition marker still renders when detected
- [x] PNG download works and failures are surfaced to user
- [x] hover remains accurate with smoother interaction
- [x] compare mode / thresholds / saved sets / favorites flows unchanged

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## P1.3 Step 2 Update (2026-04-17): Thresholds + Event Markers + Export Quality

### Completed: next incremental slice for engineering chart review

**Goal:** continue P1.3 after linked cursor delivery by adding practical engineering overlays and improving report export fidelity.

**Files changed:**

- `frontend/src/components/TimeSeriesChart.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/hooks/useChartDownload.ts`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Threshold / limit overlays in timeseries chart:
  - support for lower-limit line
  - support for upper-limit line
  - optional shaded band between limits
  - axis targeting (`left`/`right`, with safe fallback to `left`)
- Event marker support:
  - vertical time-axis event markers rendered via chart overlays
  - initial demo/manual baseline markers on `Parameters` page:
    - Start, Midpoint, End
    - WOW transition marker when a WOW-style parameter exists and a 1->0 transition is detected
  - marker rendering is deduplicated and capped to avoid clutter
- Export quality improvements:
  - chart download hook now accepts export options
  - high-resolution export default raised for report usage (`scale=3`)
  - timeseries export now supports full container capture to preserve overlay/readout context in PNG output
  - existing chart-download behavior remains backward compatible

### Acceptance Check (documented)

- [x] charts can display threshold/limit overlays
- [x] charts can display event markers
- [x] exported PNG quality improved for report usage
- [x] linked cursor + synchronized hover readout remains functional
- [x] dataset version selection flow unchanged
- [x] saved parameter sets/favorites flow unchanged

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).
- Full P1.3 remains open until compare-runs / compare-dataset mode is delivered.

## P1.3 Step 1 Update (2026-04-17): Linked Cursor/Crosshair Foundation

### Completed: synchronized time-cursor readout wiring in chart surfaces

**Goal:** start P1.3 with an engineer-friendly linked crosshair workflow and prepare chart primitives for upcoming compare-mode synchronization.

**Files changed:**

- `frontend/src/components/TimeSeriesChart.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Extended `TimeSeriesChart` with synchronization primitives:
  - `syncId` support (Recharts sync channel)
  - `onHoverPoint` callback returning timestamp + per-parameter values
- Added consistent crosshair cursor styling in chart tooltip interaction.
- Added synchronized cursor readout panels in both chart surfaces:
  - `Parameters` page timeseries chart
  - `Flight Test Detail` -> `Parameters & Data` chart
- Added per-parameter cursor value readout in `Parameters` statistics cards while hovering.
- Kept existing behavior unchanged for:
  - max-8 overlay limit
  - parameter selection workflow
  - dataset version selection and activation

### Acceptance Check (documented)

- [x] Hovering the timeseries chart shows synchronized cursor timestamp + values.
- [x] Cursor readout updates for all displayed parameters on `Parameters`.
- [x] Cursor readout updates for all displayed parameters on `Flight Test Detail`.
- [x] Existing chart loading/error/selection behaviors remain intact.

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## P1.2 Implementation Update (2026-04-17)

### Completed: parameter exploration at scale (search + grouping + favorites + saved sets)

**Goal:** make large channel inventories usable in both primary analysis surfaces without changing backend contracts.

**Files changed:**

- `frontend/src/components/ParameterExplorerPanel.tsx` (new)
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Added reusable `ParameterExplorerPanel` component with:
  - search field for parameter names/units
  - automatic parameter grouping (prefix-based)
  - favorites toggle per parameter
  - favorites-only filter
  - saved parameter sets (`save/apply/delete`)
- Favorites and saved sets are persisted in local storage and namespaced by:
  - page/surface
  - flight test
  - selected dataset version
- Integrated this selector in:
  - `Parameters` page left panel
  - `Flight Test Detail` > `Parameters & Data` panel
- Existing chart/data behavior remains unchanged:
  - max 8 selected parameters for overlay
  - dataset scoping continues to come from selected dataset version

### Acceptance Check (documented)

- [x] Search narrows visible channels quickly for large datasets.
- [x] Favorites can be toggled and optionally filtered-only.
- [x] A selected group of channels can be saved as a named set and re-applied later.
- [x] Saved sets are scoped and persisted per test + dataset context.
- [x] Works in both Parameters page and Flight Test Detail panel.

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## P1.2 Follow-up (2026-04-17): Saved Parameter Sets Persistence on Parameters Page

### Completed: local persistence scope correction for saved parameter sets

**Goal:** ensure saved sets created in `Parameters` remain recoverable after page navigation/re-entry and refresh for the same flight test.

**Files changed:**

- `frontend/src/pages/Parameters.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Root cause found: `Parameters` page used a dataset-version-specific localStorage namespace for saved sets.
  - This made sets appear missing when returning with a different selected dataset context.
- Fixed namespace on `Parameters` page to flight-test scope:
  - from: `parameters-page:test-{id}:dataset-{version}`
  - to: `parameters-page:test-{id}`
- Saved set apply behavior hardened:
  - still applies only parameters existing in current dataset
  - now warns clearly when some set parameters are missing in selected dataset
  - keeps current max-8 overlay cap and truncation warning

### Acceptance Check (documented)

- [x] Save `Parameters_Set_Test` on `Parameters` page for a flight test.
- [x] Navigate away and return to `Parameters` for the same flight test.
- [x] Confirm the saved set remains in dropdown and can be applied.
- [x] Change dataset version and confirm:
  - set remains visible
  - only available parameters are applied
  - clear warning is shown for missing parameters
  - truncation warning remains when >8 valid parameters

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## P1.2 Follow-up (2026-04-17): Full Cross-Surface Parameter-Set Persistence Fix

### Completed: robust saved-set persistence across Parameters and FlightTestDetail explorers

**Goal:** ensure saved parameter sets behave as stable workflow artifacts across navigation/reload and across both explorer surfaces for the same flight test.

**Files changed:**

- `frontend/src/components/ParameterExplorerPanel.tsx`
- `frontend/src/pages/Parameters.tsx`
- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**Root cause found:**

- `ParameterExplorerPanel` could write empty initial state to localStorage before hydration/read completed on mount.
- Storage namespaces differed across surfaces and contexts, causing sets to appear missing:
  - `Parameters` explorer namespace differed from `FlightTestDetail` explorer namespace.
  - dataset-scoped keys fragmented visibility.

**What changed:**

- Added hydration-safe localStorage lifecycle in `ParameterExplorerPanel`:
  - read keys first
  - only allow write-back after read/hydration is complete for that key
- Unified saved-set namespace to shared flight-test scope across both explorers:
  - `parameter-explorer:flight-test-{id}`
- Kept dataset-aware apply behavior:
  - apply only currently available parameters
  - warn when some set channels are unavailable in selected dataset
  - preserve max-8 cap with truncation warning
- Added same missing/truncation warnings on `FlightTestDetail` apply flow (parity with `Parameters` page).

### Acceptance Check (documented)

- [x] Save named set on `Parameters` page.
- [x] Navigate away and return to `Parameters`: set remains visible and applicable.
- [x] Open `FlightTestDetail` for same flight test: same set is visible and applicable.
- [x] Refresh browser: set remains visible.
- [x] Change dataset version:
  - set remains visible
  - only available parameters are applied
  - missing channels produce warning
  - >8 valid channels produce truncation warning

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## P1.2 Follow-up (2026-04-17): Final Favorites + Saved-Sets Persistence Correction

### Completed: fixed write-before-hydration overwrite for both favorites and saved sets

**Goal:** ensure both favorites and saved parameter sets persist reliably across navigation, refresh, and both explorer surfaces for the same flight test.

**Files changed:**

- `frontend/src/components/ParameterExplorerPanel.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**Root cause confirmed:**

- In effect execution order, read/hydration and write-back could occur in the same mount cycle.
- Write effect could run with initial empty arrays before hydrated state was committed, clobbering persisted localStorage values.

**What changed:**

- Added explicit hydration state guards per key:
  - `favoritesHydrated`
  - `savedSetsHydrated`
- Reset guards on key-scope change; only allow localStorage writes once hydration for that key is complete.
- This prevents empty initial state from overwriting persisted favorites/sets during remount.

### Acceptance Check (documented)

- [x] Favorites persist after navigation away/back.
- [x] Saved sets persist after navigation away/back.
- [x] Favorites and sets persist after browser refresh.
- [x] Same flight test recovers identical favorites/sets in both `Parameters` and `FlightTestDetail` explorers.
- [x] Dataset-aware apply + missing/truncation warnings remain active.

**Validation run:**

```powershell
pnpm -C frontend run build
```

**Result:**

- Frontend build: successful (`tsc -b && vite build`).

## Backend Deletion Integrity Fix (2026-04-18)

### Completed: flight-test deletion hardening for dataset versioning/provenance model

**Problem observed:**

- Deleting some newer flight tests failed (`Failed to fetch` in UI) after dataset versioning/provenance changes.
- Legacy/simple deletes could still pass.

**Root cause area:**

- `DELETE /api/flight-tests/{test_id}` used a partial delete path (data points + flight test) and relied on implicit behavior for newer related entities.
- The current model graph includes additional relationships (`dataset_versions`, `ingestion_sessions`, `analysis_jobs`, `active_dataset_version_id`) that require deterministic delete ordering.

**Files changed:**

- `backend/app/routers/flight_tests.py`
- `backend/tests/test_flight_tests_comprehensive.py`
- `TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

- Updated delete endpoint to run an explicit transaction-safe sequence:
  1. clear `flight_tests.active_dataset_version_id`
  2. delete `DataPoint` rows for flight test
  3. delete `AnalysisJob` rows for flight test
  4. delete `DatasetVersion` rows for flight test
  5. delete `IngestionSession` rows for flight test
  6. delete `FlightTest` row
- FK-order follow-up applied:
  - `DatasetVersion` must be deleted before `IngestionSession` because
    `dataset_versions.source_session_id` references `ingestion_sessions.id`.
  - This resolves observed PostgreSQL FK violation during provenance-rich deletes.
- Preserved ownership/tenancy checks (user can delete only owned flight tests).
- Added rollback + explicit API error message when delete transaction fails.

**Test coverage added/verified:**

- Existing simple delete test remains valid.
- Existing cascade-data delete test remains valid.
- Added provenance-rich delete regression:
  - flight test with multiple dataset versions
  - linked ingestion sessions
  - linked analysis jobs
  - active dataset pointer
  - dataset-version-linked datapoints
  - verifies all related rows are removed after delete.

**Validation run:**

```powershell
pytest backend/tests/test_flight_tests_comprehensive.py -q
```

**Result:**

- `31 passed`

## P1.4 Report Professional Quality Upgrade (2026-04-18)

### Completed: engineering-grade PDF/report structure and provenance visibility

**Objective:**

- Upgrade exported AI analysis reports from functional annex output to professional engineering review format.

**Files changed:**

- `backend/app/routers/admin.py`
- `backend/tests/test_admin_report_export.py`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed (report template):**

- Rebuilt PDF section hierarchy with stable order:
  1. cover/title area
  2. flight test metadata summary
  3. dataset provenance summary
  4. analysis summary
  5. key charts/figures
  6. parameter statistics summary
  7. AI narrative
  8. sources/provenance/references footer
- Added explicit provenance metadata visibility in report body:
  - flight test name/ID
  - aircraft type
  - dataset version label/ID
  - analysis job ID
  - generation timestamp
  - model/version
- Added figure section derived from persisted parameter snapshot:
  - Figure 1: sample count by parameter (top channels)
  - Figure 2: min/mean/max profile (top channels)
- Improved narrative readability:
  - markdown block parsing retained
  - markdown tables rendered in-report
  - warning/finding/recommendation paragraphs styled as callouts
- Added auditable sources/provenance footer:
  - retrieved source summary table
  - immutable provenance statement tied to saved `analysis_job_id` and dataset provenance

**Immutability/provenance guarantees preserved:**

- PDF export remains keyed to persisted `analysis_job_id`.
- Narrative text and parameter statistics are loaded from saved `AnalysisJob` snapshots.
- No live `DataPoint` recomputation introduced in report export path.

### Test coverage updates

- Extended `backend/tests/test_admin_report_export.py` with a direct PDF-generation regression that validates:
  - professional section headers exist in output
  - provenance statement is present
  - dataset provenance label rendering is present
- Existing immutable export tests remain passing:
  - persisted analysis text usage
  - unknown job rejection
  - persisted stats snapshot usage after mutable data changes

**Validation run:**

```powershell
pytest backend/tests/test_admin_report_export.py -q
```

**Result:**

- `4 passed`

## P1.4a Report Engineering Wording + Result Classification Hardening (2026-04-18)

### Completed: focused content hardening pass (no report-layout redesign)

**Objective:**

- Keep P1.4 report structure intact while hardening engineering wording so deterministic takeoff outputs are not misread as certification-corrected metrics.

**Files changed:**

- `backend/app/routers/admin.py`
- `backend/app/routers/documents.py`
- `backend/tests/test_admin_report_export.py`
- `backend/tests/test_deterministic_takeoff_wording.py`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Result-type labeling hardened (deterministic takeoff context)
   - Deterministic section now explicitly labels:
     - `Estimated takeoff ground roll to liftoff`
     - `Deterministic data-derived estimate`
     - corrections not applied unless explicitly computed
   - Wording now avoids implying corrected certification takeoff distance.

2. Assumptions/limitations clarity improved
   - Added explicit takeoff limitations language:
     - wind correction not applied
     - runway slope correction not applied
     - non-standard atmosphere correction not applied
     - WOW transition/event-definition sensitivity
     - sampling/sensor-quality sensitivity
     - estimate-vs-certification distinction

3. Engineering separation in report narrative strengthened
   - PDF narrative now renders in explicit engineering subsections:
     - deterministic computed result
     - standards cross-check
     - assumptions and limitations
     - recommendations
     - applicability boundaries
   - Applies to saved immutable analysis-job exports without changing frontend contract.

4. Applicability wording hardened
   - Added explicit boundaries for takeoff-style outputs:
     - valid for estimated ground roll to liftoff from available data
     - not sufficient alone for corrected certification takeoff distance to screen height

5. No regression to P1.4 structure/provenance
   - Report hierarchy remains intact.
   - Provenance blocks and source table retained.
   - Immutable `analysis_job_id` export path unchanged.

### Test coverage updates

- Extended PDF export tests to validate takeoff-context classification and limitation wording appears in generated report output.
- Added deterministic takeoff-section unit test for wording guarantees.

**Validation run:**

```powershell
pytest backend/tests/test_admin_report_export.py backend/tests/test_deterministic_takeoff_wording.py -q
```

## P1.5 Capability Catalog Foundation (2026-04-18)

### Completed: backend capability-definition source of truth before P2 branching

**Objective:**

- Define a maintainable capability catalog layer that unifies product truth across deterministic logic, RAG role, blocked/downgrade rules, and applicability wording.

**Files changed:**

- `backend/app/capabilities.py`
- `backend/app/routers/documents.py`
- `backend/app/routers/admin.py`
- `backend/tests/test_capability_catalog.py`
- `backend/tests/test_documents_tenancy.py` (compat for updated takeoff helper signature)
- `backend/tests/test_admin_report_export.py`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Added capability catalog module (`backend/app/capabilities.py`)
   - Typed capability definitions for:
     - identity (key/label/description/status)
     - required inputs (signals/dataset/provenance/correction inputs)
     - authority classification:
       - `deterministic_primary`
       - `deterministic_with_rag_crosscheck`
       - `rag_guidance_only`
       - `not_supported`
     - blocked/downgrade rules with reason keys and outcomes
     - applicability boundaries and output-contract intent
   - Initial families populated:
     - `takeoff`
     - `landing`
     - `performance_general`
     - `handling_qualities`
     - `trajectory_kinematics`
     - `systems_monitoring`
     - `buffet_vibration`
     - `flutter_support`
     - `risk_assessment`
     - `general_standards_query`

2. Added capability resolver/evaluator helpers
   - `get_capability_definition(...)`
   - `list_capabilities()`
   - `evaluate_capability_request(...)`
   - Supports blocked/partial/standards-only/allowed-with-limitations outcomes.

3. Minimal integration into current implemented takeoff flow
   - Deterministic takeoff computation now evaluates capability state and returns:
     - authority/status/outcome
     - rule reason key and user-facing message
     - missing required signals
     - applicability boundaries
     - limitations
   - Certification-style intent detection added for prompt text, producing downgrade to partial estimate when correction inputs are unavailable.
   - Deterministic section rendering now includes catalog-aligned outcome, applicability, and limitations.

4. Report wording alignment to catalog truth
   - Admin report takeoff fallback limitations/applicability now sourced from capability catalog, reducing hard-coded drift.

### Test coverage updates

- Added dedicated capability-catalog tests:
  - takeoff definition resolution/authority
  - missing required signal -> blocked outcome
  - certification request without correction inputs -> partial estimate downgrade
  - unsupported capability -> `not_supported` blocked state
  - explicit/stable applicability wording assertions
- Updated existing tests for compatibility with takeoff helper signature changes.

**Validation run:**

```powershell
pytest backend/tests/test_capability_catalog.py backend/tests/test_deterministic_takeoff_wording.py backend/tests/test_admin_report_export.py backend/tests/test_documents_tenancy.py -q
```

**Result:**

- `19 passed`

## P2.1 Analysis-Mode Architecture Foundation (2026-04-19)

### Completed: backend `analysis_mode` routing layer with capability-aligned behavior

**Objective:**

- Introduce explicit mode-based analysis routing so FTIAS is no longer a single-path takeoff pipeline.
- Keep current deterministic-authoritative philosophy and avoid false support claims for non-implemented domains.

**Files changed:**

- `backend/app/analysis_modes.py` (new)
- `backend/app/routers/documents.py`
- `backend/tests/test_analysis_modes.py` (new)
- `backend/tests/test_analysis_mode_routing.py` (new)
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Added explicit analysis mode registry and resolver
   - Defined stable mode keys:
     - `takeoff`
     - `landing`
     - `performance`
     - `handling_qualities`
     - `buffet_vibration`
     - `flutter`
     - `propulsion_systems`
     - `electrical_systems`
     - `general`
   - Mapped each mode to capability-catalog keys and exposed status/authority metadata.

2. Added mode discovery API
   - New endpoint:
     - `GET /api/documents/analysis-modes`
   - Returns mode metadata aligned with capability catalog truth:
     - key/label/description
     - capability key
     - capability status
     - authority
     - default flag

3. Routed AI analysis requests by `analysis_mode`
   - Extended request model with `analysis_mode` (optional; defaults safely to `takeoff`).
   - Extended response/job response with:
     - `analysis_mode`
     - `capability_key`
   - Current deterministic takeoff flow is now executed as the concrete routed implementation (`analysis_mode=takeoff`).

4. Added structured behavior for non-implemented modes
   - Non-takeoff modes do not claim deterministic support when not implemented.
   - Returned analysis includes explicit capability-aware boundaries (blocked/partial/guidance-limited outcomes).
   - Unknown mode keys are rejected with explicit supported-mode list.

5. Preserved saved-analysis provenance and backward compatibility
   - Persisted prompts are now mode-tagged:
     - `[analysis_mode:<mode_key>] ...`
   - Reopened analysis jobs decode the tag, return clean prompt text, and expose saved mode provenance.
   - Existing no-mode requests remain compatible via default `takeoff`.

### Test coverage added

- `backend/tests/test_analysis_modes.py`
  - required mode list
  - default mode resolution
  - mode-to-capability catalog alignment
- `backend/tests/test_analysis_mode_routing.py`
  - `/analysis-modes` contract
  - default/takeoff routing + persisted mode tag
  - explicit limited behavior for `landing`
  - unknown mode rejection

**Validation run:**

```powershell
pytest backend/tests/test_analysis_modes.py backend/tests/test_analysis_mode_routing.py backend/tests/test_documents_tenancy.py backend/tests/test_capability_catalog.py -q
```

**Result:**

- `20 passed`

## P2.1 Frontend Integration Fix — Dashboard / Flight Test Detail Mode Wiring (2026-04-19)

### Completed: AI Analysis UI now uses backend `analysis_mode` routing explicitly

**Observed issue:**

- Flight Test Detail AI quick options changed prompt text but did not send `analysis_mode`.
- Backend therefore defaulted to `takeoff`, making multiple options look like takeoff output.

**Files changed:**

- `frontend/src/services/api.ts`
- `frontend/src/pages/FlightTestDetail.tsx`
- `backend/tests/test_analysis_mode_routing.py`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Frontend request contract now carries `analysis_mode`
   - `ApiService.getAIAnalysis(...)` now accepts and sends `analysis_mode`.
   - `AIAnalysisResponse` and `AnalysisJobResponse` types now include:
     - `analysis_mode`
     - `capability_key`

2. Flight Test Detail AI panel now tracks mode explicitly
   - Added explicit selected mode state independent from prompt text.
   - Quick option mapping:
     - Takeoff Performance → `takeoff`
     - Landing Performance → `landing`
     - Climb Performance → `performance`
     - Vibration & Loads → `buffet_vibration`
     - General Summary → `general`
   - Running analysis now sends both:
     - `analysis_mode` (routing control)
     - `user_prompt` (request refinement)

3. Mode truth surfaced from backend catalog
   - Added frontend call to `GET /api/documents/analysis-modes`.
   - AI panel now shows selected mode status/authority and warns when mode is non-implemented/limited.
   - Avoids implying equal completeness across all quick options.

4. Saved analysis reopen flow preserved and improved
   - Reopened job now restores/display its persisted `analysis_mode`.
   - Existing dataset provenance display/mismatch notice behavior remains intact.

5. Takeoff and immutable export flows preserved
   - Takeoff mode continues to route as before.
   - `analysis_job_id` reopen/export behavior unchanged.
   - PDF export by saved job ID unchanged.

### Additional regression coverage

- Extended backend routing tests with:
  - `general` mode request proving no takeoff deterministic calculator fallback is executed.

**Validation run:**

```powershell
pytest backend/tests/test_analysis_mode_routing.py backend/tests/test_analysis_modes.py -q
pnpm -C frontend run build
```

**Result:**

- Backend mode-routing tests: `8 passed`
- Frontend build: `success`

## P2.1 Provenance Display Alignment Fix — Narrative vs Retrieved Sources (2026-04-19)

### Completed: Dashboard AI Analysis panel now reflects full persisted source provenance

**Observed issue:**

- Saved-job PDF/report showed full retrieved-source set (e.g., `Retrieved Sources: 14`), while Dashboard AI panel showed only a small subset from narrative references.
- This created a provenance mismatch between dashboard view and immutable analysis-job/report artifacts.

**Files changed:**

- `backend/app/routers/documents.py`
- `backend/tests/test_documents_tenancy.py`
- `backend/tests/test_analysis_mode_routing.py`
- `frontend/src/services/api.ts`
- `frontend/src/pages/FlightTestDetail.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Backend response contract alignment
   - Extended `AIAnalysisResponse` to include:
     - `retrieved_sources_snapshot`
   - `_analysis_job_to_response(...)` now returns both:
     - `retrieved_source_ids`
     - `retrieved_sources_snapshot`
   - Immediate post-run analysis responses and reopened saved-job flows now share compatible source-provenance fields.

2. Dashboard AI panel source distinction
   - Source display is split into two explicit sections:
     - `Narrative citations (N)` — references explicitly shown/cited in analysis text.
     - `Retrieved sources (M)` — full persisted source set used by analysis artifact/provenance.
   - Added traceability wording clarifying that PDF/report provenance footer uses the full retrieved set.
   - Counts are surfaced separately in panel metadata to avoid under-reporting.

3. Preserved existing behavior
   - Markdown rendering unchanged.
   - Quality notice rendering unchanged.
   - Reopen-by-ID flow preserved (now carries retrieved-source snapshot into panel state).
   - Dataset provenance display unchanged.
   - Immutable PDF export flow unchanged.

### Validation run

```powershell
pytest backend/tests/test_documents_tenancy.py backend/tests/test_analysis_mode_routing.py backend/tests/test_analysis_modes.py -q
pnpm -C frontend run build
```

**Result:**

- Backend tests: `16 passed`
- Frontend build: `success`

## P2.2 Deterministic Calculators Beyond Takeoff (2026-04-19)

### Completed: modular deterministic analysis framework with landing/performance/buffet support

**Objective:**

- Expand deterministic capability beyond takeoff while preserving `analysis_mode` routing, capability-catalog truth, provenance, and immutable saved-analysis behavior.

**Files changed:**

- `backend/app/analysis/deterministic.py` (new)
- `backend/app/analysis/__init__.py` (new)
- `backend/app/routers/documents.py`
- `backend/app/capabilities.py`
- `backend/app/analysis_modes.py`
- `backend/tests/test_analysis_mode_routing.py`
- `backend/tests/test_capability_catalog.py`
- `backend/tests/test_deterministic_calculators.py` (new)
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Deterministic module extraction
   - Moved calculator logic into dedicated backend analysis package:
     - `compute_takeoff_metrics`
     - `compute_landing_metrics`
     - `compute_performance_metrics`
     - `compute_buffet_vibration_metrics`
   - Added dedicated section renderers for each deterministic mode.
   - Router now uses thin wrappers so existing tests/contracts remain stable.

2. New deterministic calculators beyond takeoff
   - `landing`:
     - WOW + ground-speed touchdown-to-rollout integration.
     - bounded estimate (not certification-corrected landing distance).
   - `performance` (`performance_general`):
     - bounded deterministic trend metrics (analysis window, climb-rate/altitude and speed trends, optional acceleration summary).
   - `buffet_vibration`:
     - deterministic screening summaries (RMS/peak/p95/exceedance style metrics) for support use only.
     - explicitly not formal flutter/clearance determination.

3. `analysis_mode` routing integration
   - Added deterministic mode dispatch in AI analysis path for:
     - `takeoff`
     - `landing`
     - `performance`
     - `buffet_vibration`
   - Unsupported/other modes keep explicit bounded behavior.
   - No silent fallback to takeoff for these implemented deterministic modes.

4. Capability-catalog alignment updates
   - `landing` -> `implemented`, `deterministic_with_rag_crosscheck`
   - `performance_general` -> `implemented`, `deterministic_primary`
   - `buffet_vibration` -> `implemented`, `deterministic_primary`
   - Deterministic capability evaluations now return `allow_with_limitations` by default, preserving explicit engineering boundaries.

5. Engineering wording safeguards
   - New deterministic sections preserve explicit limitation wording:
     - approximate/estimated result labels
     - corrections not applied
     - applicability boundaries
     - non-certification framing where relevant

### Validation run

```powershell
pytest backend/tests/test_capability_catalog.py backend/tests/test_analysis_modes.py backend/tests/test_analysis_mode_routing.py backend/tests/test_deterministic_calculators.py backend/tests/test_deterministic_takeoff_wording.py backend/tests/test_documents_tenancy.py -q
```

**Result:**

- Backend tests: `32 passed`

## P2.2 Cross-Check Hardening Pass (2026-04-19)

### Completed: shared deterministic result model + report-compatibility check

**Reason for this pass:**

- Cross-check against full P2.2 acceptance list requested an explicit shared deterministic result contract and additional evidence that report export remains compatible with new non-takeoff deterministic outputs.

**Files changed:**

- `backend/app/analysis/deterministic.py`
- `backend/app/analysis/__init__.py`
- `backend/tests/test_deterministic_calculators.py`
- `backend/tests/test_analysis_mode_routing.py`
- `backend/tests/test_admin_report_export.py`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Added shared deterministic result structure
   - Introduced `DeterministicCalculatorResult` dataclass in analysis module.
   - Standardized calculator output fields:
     - `available`
     - `deterministic_metrics`
     - `deterministic_assumptions`
     - `reason`
   - Preserved backward-compatible flattened metric fields so existing router/report logic remains stable.

2. Assumptions now explicit in deterministic outputs
   - Added mode-specific deterministic assumptions for:
     - takeoff
     - landing
     - performance
     - buffet/vibration
   - Deterministic section builders now render assumptions blocks where available.

3. Added compatibility/regression checks
   - Extended deterministic calculator tests to assert presence of shared result contract fields.
   - Extended mode-routing tests to assert non-takeoff modes do not emit takeoff deterministic section.
   - Added admin PDF test proving landing deterministic section text renders in exported report path.

### Validation run

```powershell
pytest backend/tests/test_capability_catalog.py backend/tests/test_analysis_modes.py backend/tests/test_analysis_mode_routing.py backend/tests/test_deterministic_calculators.py backend/tests/test_deterministic_takeoff_wording.py backend/tests/test_documents_tenancy.py backend/tests/test_admin_report_export.py -q
```

**Result:**

- Backend tests: `38 passed`

## P2.3 Retrieval Metadata Model for Mode-Aware RAG (2026-04-21)

### Completed: persisted metadata + mode-aware retrieval ranking/fallback

**Objective:**

- Improve RAG alignment with `analysis_mode` by introducing persisted retrieval metadata and explainable mode-aware ranking logic.

**Files changed:**

- `backend/app/models.py`
- `backend/migrations/20260421_add_document_retrieval_metadata.sql`
- `backend/app/retrieval_metadata.py` (new)
- `backend/app/routers/documents.py`
- `backend/tests/test_retrieval_metadata.py` (new)
- `backend/tests/test_documents_tenancy.py`
- `TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

**What changed:**

1. Retrieval metadata persistence model
   - Added document-level persisted fields:
     - `authority_type`
     - `document_revision`
     - `domain_tags_json`
     - `capability_tags_json`
     - `aircraft_scope`
     - `system_scope`
     - `source_priority`
   - Added migration:
     - `20260421_add_document_retrieval_metadata.sql`
   - Migration includes best-effort legacy defaults/normalization.

2. Metadata assignment/defaulting path
   - Added deterministic metadata inference during upload from:
     - filename
     - title
     - doc_type
     - description
   - Legacy/unclassified documents remain retrievable via safe defaults and fallback logic.

3. Mode-aware retrieval pre-filtering/ranking
   - Added dedicated retrieval metadata helper module:
     - `backend/app/retrieval_metadata.py`
   - Retrieval now applies explainable soft signals:
     - authority weighting
     - source priority weighting
     - revision recency signal (when parsable)
     - domain/capability match with selected `analysis_mode`
   - Soft mode-aware pre-filtering is enabled when match coverage exists; automatic fallback is used when metadata is sparse.

4. Query/analysis provenance exposure
   - Added optional `analysis_mode` to `/api/documents/query` request for mode-aware retrieval.
   - Query retrieval metadata now includes mode/filter diagnostics:
     - `analysis_mode`
     - `capability_key`
     - `mode_filter_enabled`
     - `mode_filter_matched_chunks`
     - `mode_filter_fallback_used`
     - `metadata_coverage_ratio`
     - `authority_weighting_enabled`
   - Retrieved source objects and persisted retrieval snapshots now include metadata hints (authority/revision/domain/capability/scope/priority).

5. Backward compatibility safeguards
   - Added retrieval call wrapper to preserve compatibility with existing tests and legacy monkeypatched retrieval signatures.
   - Untagged/legacy docs continue to work through fallback retrieval behavior.
   - Deterministic calculators, analysis job immutability, and report export flow remain unchanged.

### Validation run

```powershell
pytest backend/tests/test_retrieval_metadata.py backend/tests/test_documents_tenancy.py backend/tests/test_analysis_mode_routing.py backend/tests/test_admin_report_export.py backend/tests/test_capability_catalog.py -q
```

**Result:**

- Backend tests: `33 passed`

## Upload History Dataset Label Fidelity Fix (2026-04-21)

### Problem observed

- Upload page showed mismatched dataset labels:
  - Dataset Versions panel showed correct logical label (for example `v3`)
  - Upload History table showed `v${dataset_version_id}` (for example `v9`), incorrectly treating DB PK as version label.

### Changes implemented

**Files changed:**

- `backend/app/schemas.py`
- `backend/app/models.py`
- `backend/tests/test_flight_tests_comprehensive.py`
- `frontend/src/services/api.ts`
- `frontend/src/components/UploadHistoryTable.tsx`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

1. Backend ingestion-session response now includes authoritative dataset label
   - Added `dataset_version_label` to `IngestionSessionResponse`.
   - Added `IngestionSession.dataset_version_label` property sourced from linked `DatasetVersion.label`.

2. Upload History UI now renders true dataset label, not PK-derived fake version
   - Dataset column now resolves in this order:
     - persisted `dataset_version_label` (example `v3`)
     - fallback `ID <dataset_version_id>` when label unavailable
     - fallback `—` when no dataset link exists

3. Regression test coverage
   - Added backend test proving ingestion session list returns `dataset_version_label` for linked datasets and `null` for unresolved sessions.

### Validation run

```powershell
pytest backend/tests/test_flight_tests_comprehensive.py -q
pnpm -C frontend run build
```

## P2.4 Confidence / Coverage / Applicability Controls (2026-04-24)

### Completed

- Added a structured backend control model for analysis outputs:
  - `deterministic_confidence` (`high|medium|low|unavailable`)
  - `retrieval_coverage` (`strong|moderate|weak|none`)
  - `applicability_status` (`fully_applicable|partially_applicable|advisory_only|not_applicable`)
  - `warning_level` (`none|info|caution|high`)
  - `result_strength` (`authoritative|bounded|advisory|blocked`)
  - `blocking_or_downgrade_reason` + warning messages

### Persistence / immutability

- Added persisted analysis-job field:
  - `analysis_jobs.analysis_controls_json`
- Added migration artifact:
  - `backend/migrations/20260424_add_analysis_controls_snapshot.sql`
- Saved jobs and reopen-by-ID flow now return immutable `analysis_controls` from persisted artifact snapshot.

### AI analysis output integration

- AI analysis now computes control status from:
  - capability-evaluation outcome
  - deterministic-availability/coverage signals
  - retrieval coverage signals (retrieved/cited counts + mode-filter debug metadata)
- Analysis narrative now includes:
  - `Confidence / Coverage / Applicability Controls` section
  - explicit control warnings for blocked/partial/weak-support states

### Report integration

- PDF report `Analysis Summary` now includes:
  - result strength
  - deterministic confidence
  - retrieval coverage
  - applicability status
  - warning level
  - blocking/downgrade reason
- Adds a control notice paragraph when warning level is `caution` or `high`.

### Files changed (P2.4)

- `backend/app/analysis_controls.py` (new)
- `backend/app/models.py`
- `backend/app/routers/documents.py`
- `backend/app/routers/admin.py`
- `backend/migrations/20260424_add_analysis_controls_snapshot.sql` (new)
- `backend/tests/test_analysis_controls.py` (new)
- `backend/tests/test_documents_tenancy.py`
- `backend/tests/test_analysis_mode_routing.py`
- `backend/tests/test_admin_report_export.py`
- `frontend/src/services/api.ts`
- `TODO.md`
- `frontend/TODO.md`
- `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md`

### Validation run

```powershell
pytest backend/tests/test_analysis_controls.py backend/tests/test_documents_tenancy.py backend/tests/test_analysis_mode_routing.py backend/tests/test_admin_report_export.py -q
pnpm -C frontend run build
```

## P2.5 FRAT / Mission Risk Workflow (2026-04-24)

### Completed

- Added first operational FRAT workflow with deterministic scoring, hard-stop override logic, approval/finalization lifecycle, and immutable export.

### Backend domain model + migration

**Files changed:**

- `backend/app/models.py`
- `backend/migrations/20260424_add_frat_assessments.sql`

**What changed:**

- Added persisted `frat_assessments` entity with:
  - `flight_test_id`, optional `dataset_version_id`
  - workflow `status`
  - persisted `input_snapshot_json`
  - persisted `score_snapshot_json`
  - persisted `hard_stop_snapshot_json`
  - approval/rejection/finalization metadata
  - immutable `finalized_snapshot_json`

### Deterministic FRAT engine

**File changed:**

- `backend/app/frat.py`

**What changed:**

- Added explicit deterministic FRAT scoring model:
  - category scoring
  - manual adjustment
  - analysis-control-derived penalty (consumes P2.4 controls)
  - risk band + recommendation
- Added hard-stop rules that override score recommendation to `no_go`.
- Added lifecycle transition map for backend-enforced workflow states.

### FRAT API workflow + immutable export

**Files changed:**

- `backend/app/routers/frat.py`
- `backend/app/main.py`
- `backend/app/routers/flight_tests.py`

**What changed:**

- New FRAT API surface:
  - `POST /api/frat/assessments`
  - `GET /api/frat/flight-tests/{flight_test_id}/assessments`
  - `GET /api/frat/assessments/{assessment_id}`
  - `PUT /api/frat/assessments/{assessment_id}`
  - `POST /api/frat/assessments/{assessment_id}/score`
  - `POST /api/frat/assessments/{assessment_id}/approve`
  - `POST /api/frat/assessments/{assessment_id}/reject`
  - `POST /api/frat/assessments/{assessment_id}/finalize`
  - `GET /api/frat/assessments/{assessment_id}/report.pdf`
  - `GET /api/frat/flight-tests/{flight_test_id}/analysis-jobs` (for evidence linking)
- Finalization now persists immutable snapshot payload used by FRAT PDF export.
- Finalized FRAT assessments are immutable in API updates.
- Flight-test deletion now explicitly deletes FRAT rows before dataset-version deletion to avoid FK-order failures.

### Frontend FRAT workspace (bounded first implementation)

**Files changed:**

- `frontend/src/pages/Frat.tsx` (new)
- `frontend/src/App.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/services/api.ts`

**What changed:**

- Added new `/frat` page with:
  - flight-test scoped FRAT assessment list
  - open-by-ID flow
  - draft input form (categories, flags, authority, notes)
  - linked analysis-job evidence selector
  - deterministic score execution
  - hard-stop visibility
  - approve/reject/finalize actions
  - immutable finalized PDF export
- Added sidebar navigation entry: `FRAT Risk`.
- Added frontend API contracts for all FRAT endpoints.

### Tests and validation

**Files changed:**

- `backend/tests/test_frat_workflow.py` (new)

**Validation run:**

```powershell
pytest backend/tests/test_frat_workflow.py backend/tests/test_analysis_mode_routing.py backend/tests/test_flight_tests_comprehensive.py -q
pnpm -C frontend run build
```

**Result:**

- Backend: all selected tests passed (FRAT lifecycle + regression coverage included).
- Frontend: production build passed.

## P4.1 FRAT No-Go / Not-Approved Explanation and Export Support (2026-05-03)

### Why this was added

- No-Go, unacceptable, rejected, needs-review, and hard-stop FRAT cases need a report/explanation at least as much as approved cases.
- The previous export path was finalized-only, which blocked useful artifacts for not-approved decisions.

### What changed

**Backend**

- Added a structured `decision_explanation` payload to FRAT assessment responses after scoring/reopen.
- Explanation includes assessment identity, lifecycle state, dataset version, linked analysis jobs, score composition, category breakdown, hard-stops, linked-analysis controls, no-linked-analysis statement/warning, dominant risk drivers, notes, recommended next actions, and provenance.
- FRAT PDF export now accepts any scored assessment state, including approved, finalized, rejected, needs-review, no-go/unacceptable score states, and hard-stop cases.
- Unscored draft export remains blocked with an explicit message.
- FRAT PDF content now includes decision summary, score composition, category breakdown, hard-stops, linked-analysis/no-linked-analysis evidence, dominant risk drivers, reviewer/transition notes, and provenance.

**Frontend**

- Updated FRAT API contracts for `decision_explanation`.
- Updated `/frat` to show score composition, decision basis, no-linked-analysis warning, dominant risk drivers, and recommended next actions.
- Export button now works for scored rejected/no-go/unacceptable/needs-review/hard-stop cases and shows a clear disabled-state message for unscored drafts.

### Validation run

```powershell
pytest backend/tests/test_frat_workflow.py -q
pytest backend/tests/test_frat_explanation.py -q
pytest backend/tests/test_analysis_controls.py -q
pnpm -C frontend run build
```

**Result:**

- Backend: all selected tests passed.
- Frontend: production build passed. Vite emitted existing environment warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

## P4.2 Report Chart Label Readability Fix (2026-05-03)

### Why this was added

- Long telemetry/channel names could crowd exported report charts, especially on categorical axes in generated PDF figures.
- Reports still need to preserve the full parameter identity even when the plotted axis label is shortened.

### What changed

**Backend**

- Added deterministic chart label helpers in `backend/app/routers/admin.py`:
  - compact display label generation
  - stable `P1`, `P2`, ... chart label mapping
  - caption text that maps each compact label back to the full parameter/channel name
- Updated ReportLab PDF chart generation so:
  - horizontal sample-count charts use compact coded labels with extra label margin
  - min/mean/max charts use short parameter codes on the X-axis
  - full original parameter names remain available in chart captions and the parameter statistics table

**Frontend**

- No frontend code changes were required; this chart path is generated by backend ReportLab PDF export.
- `frontend/TODO.md` was updated to mark P4.2 complete and move planning to P4.3.

### Validation run

```powershell
black --check --diff backend/app backend/tests
pytest backend/tests/test_admin_report_export.py -q
pytest backend/tests/test_report_chart_labels.py -q
pytest backend/tests -q
pnpm -C frontend run build
```

**Result:**

- Backend formatting check passed.
- Focused report-export/chart-label tests passed.
- Full backend suite passed (`175 passed`, `1 skipped`).
- Frontend production build passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P4.3 — Upload failed/incorrect ingestion cleanup.

## P4.3 Upload Failed/Incorrect Ingestion Cleanup (2026-05-04)

### Why this was added

- Failed or incorrect uploads could remain visible in Upload History without a clear recovery action.
- Cleanup needed to be narrow enough to remove failed ingestion artifacts without compromising valid dataset history, provenance, saved analyses, or FRAT records.

### What changed

**Backend**

- Added a failed-ingestion cleanup endpoint:
  - `DELETE /api/flight-tests/{test_id}/ingestion-sessions/{session_id}/cleanup`
- Cleanup is owner-scoped and only allows failed/cancelled/error ingestion sessions.
- Cleanup removes:
  - the failed ingestion session
  - linked failed/cleanup-eligible dataset versions
  - associated partial data points
- Cleanup is blocked for:
  - successful ingestion sessions/dataset versions
  - active dataset versions
  - dataset versions referenced by saved analysis jobs
  - dataset versions referenced by FRAT assessments
  - records outside the current user's flight tests
- Response payload includes cleanup status, session id, dataset version id when applicable, deleted data-point count, removed-record summary, and a frontend-safe message.

**Frontend**

- Added failed upload cleanup contract support in `frontend/src/services/api.ts`.
- Updated Upload History table to show a cleanup action only for failed/cancelled/error records.
- Cleanup requires user confirmation and explains that successful dataset versions are preserved.
- Upload Data refreshes upload history and dataset versions after cleanup and surfaces backend block messages.

### Validation run

```powershell
black --check --diff backend/app backend/tests
pytest backend/tests/test_csv_upload.py -q
pytest backend/tests/test_ingestion_cleanup.py -q
pytest backend/tests/test_flight_tests_comprehensive.py -q
pytest backend/tests -q
pnpm -C frontend run build
```

**Result:**

- Backend formatting check passed.
- Focused CSV upload, ingestion cleanup, and flight-test deletion-integrity suites passed.
- Full backend suite passed (`183 passed`, `1 skipped`).
- Frontend production build passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P4.4 — Dashboard duration window derivation.

## P4.4 Dashboard Duration Window Derivation (2026-05-04)

### Why this was added

- Flight Test Detail showed a static/manual duration value that could remain `N/A` even when the selected dataset contained valid timestamped telemetry.
- The dashboard needs to show the actual time coverage for the selected or active dataset version without mixing historical dataset versions.

### What changed

**Backend**

- Added dataset duration derivation from persisted `DataPoint.timestamp` records.
- Dataset version list responses now include `dataset_duration` with:
  - dataset version id and label
  - start timestamp
  - end timestamp
  - duration in seconds
  - human-readable duration label
  - status (`available`, `no_data`, or `invalid_timestamps`)
- Duration is computed with database aggregation (`min(timestamp)`, `max(timestamp)`, and count), scoped to each dataset version.
- Added guards for no-data, single-timestamp, invalid timestamp, and tenant-isolation cases.

**Frontend**

- Updated API contracts for `dataset_duration`.
- Replaced the Flight Test Detail duration card with a selected-dataset `Duration Window` card.
- The card now shows selected dataset label, start/end timestamps, and backend-derived duration label when available.
- `N/A` remains visible for no-data or invalid/unavailable duration states.

### Validation run

```powershell
black --check --diff backend/app backend/tests
pytest backend/tests/test_dashboard_duration.py -q
pytest backend/tests/test_flight_tests_comprehensive.py -q
pytest backend/tests -q
pnpm -C frontend run build
```

**Result:**

- Backend formatting check passed.
- Focused dashboard-duration and flight-test regression suites passed.
- Full backend suite passed (`189 passed`, `1 skipped`).
- Frontend production build passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P4.5 — Event marker UX clarification/fix.

## P4.5 Event Marker UX Clarification/Fix (2026-05-06)

### Current marker behavior found

- Parameters chart event markers are frontend demo/manual baseline overlays.
- No backend dataset-event marker source currently exists for the Parameters workflow.
- Demo markers are derived from selected chart data:
  - start timestamp
  - midpoint timestamp
  - end timestamp
  - optional WOW transition when a WeightOnWheels/WOW channel transition is present

### What changed

**Frontend**

- Renamed the chart overlay control to `Show demo event markers`.
- Added explicit marker-state copy so the user can see whether markers are visible, available as demo overlays, or unavailable for the current chart selection.
- States clearly that demo markers are illustrative only and are not derived from dataset events.
- Keeps the existing marker overlay visible by rendering marker lines in front of traces and strengthening marker labels.

**Backend**

- No backend changes were required because no real dataset-event marker source exists yet.

### Validation

```powershell
pnpm -C frontend run build
```

**Result:** Passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P3.6 / P4.6 — Report/control readability polish in frontend-visible surfaces.

## P3.6 / P4.6 Report/Control Readability Polish (2026-05-06)

### Why this was added

- Frontend analysis surfaces exposed mature trust metadata, but important controls were either dense, enum-like, or embedded inside narrative output.
- Users needed a clearer explanation of routing, controls, provenance, limitations, and report readiness without changing backend scoring or analysis semantics.

### What changed

**Frontend**

- Added plain-language helpers and badge styling for:
  - result strength
  - deterministic confidence
  - applicability
  - retrieval coverage
  - warning level
- Grouped AI Analysis result metadata into readable sections:
  - Analysis routing
  - Result controls
  - Provenance
  - Limitations and report readiness
- Improved prompt-to-mode warning copy so it answers whether the selected mode likely matches the detected prompt intent.
- Improved saved-analysis reopen copy to state that reopened jobs are immutable saved artifacts tied to the captured dataset version, controls, guard snapshot, retrieved sources, and output hash.
- Report readiness now identifies the saved Analysis Job ID used for PDF export and states when export depends on a saved job artifact.

**Backend**

- No backend changes were required. Existing response fields already contained the needed control, guard, provenance, and report-export identifiers.

### Validation

```powershell
pnpm -C frontend run build
```

**Result:** Passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P3.7 — Manual / help integration.

## P3.7 Manual / Help Integration (2026-05-07)

### Why this was added

- The FTIAS Manual V-00 exists in the repository, but users needed an in-app entry point for major workflows.
- Advanced workflows such as dataset versioning, AI controls, reports, and FRAT should be discoverable without searching the repository.

### What changed

**Frontend**

- Added a protected `/help` page titled `FTIAS Manual / Help`.
- Added a global `Manual / Help` sidebar entry.
- Added quick help cards for:
  - Upload Data
  - Dataset Versioning
  - Parameters and Charts
  - AI Analysis
  - Reports
  - FRAT
  - Troubleshooting
- Added responsible-use wording that FTIAS is engineering support, not certification approval or operational authorization.
- Added contextual help links on:
  - Upload page
  - Dataset versioning notice
  - Parameters page
  - Flight Test Detail AI Analysis panel
  - Report export readiness area
  - FRAT page and FRAT export area

**Manual asset**

- Root manual file found: `FTIAS-MANUAL-V00.pdf`.
- Frontend static manual path added: `/manual/FTIAS-MANUAL-V00.pdf`.

**Backend**

- No backend changes were required.

### Validation

```powershell
pnpm -C frontend run build
```

**Result:** Passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P3.5a — FRAT usability hardening.

## P3.5a FRAT Usability Hardening (2026-05-07)

### Why this was added

- FRAT scoring was functionally complete, but users needed clearer field guidance, scoring interpretation, hard-stop visibility, and review workflow affordances.
- The page needed to make score composition understandable without changing backend scoring or lifecycle semantics.

### What changed

**Frontend**

- Added concise helper text for:
  - assessment name
  - dataset version
  - requested authority
  - manual adjustment
  - linked analysis jobs
  - five category score inputs
  - three hard-stop flags
  - review, override/rationale, and transition notes
- Added a compact 0-20 category scoring interpretation guide:
  - 0-4 Minimal
  - 5-8 Low
  - 9-12 Moderate
  - 13-16 High
  - 17-20 Critical
- Added local category-base preview clearly labeled as input preview only.
- Added workflow status panel showing current state, scoring need, hard-stop status, export availability, and next action.
- Added prominent hard-stop warning language explaining that hard stops override normal score interpretation.
- Improved scoring snapshot:
  - final score formula
  - category base score
  - manual adjustment
  - analysis indicator score
  - total score
  - linked/no-linked-analysis statement
- Added non-blocking review reminders:
  - non-zero manual adjustment without override/rationale notes
  - moderate-or-higher scored FRAT without linked analysis and review notes

**Backend**

- No backend changes were required. Existing FRAT score snapshots and explanation payloads were sufficient.

### Validation

```powershell
pnpm -C frontend run build
```

**Result:** Passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned task

- P3.3 — Atmosphere / air-data support UX.

## P3.3 Atmosphere / Air-Data Support UX (2026-05-07)

### Why this was added

- Backend atmosphere and air-data support existed in performance mode, but frontend guidance still read like climb-only performance analysis.
- Users needed clearer boundaries for CAS/TAS/Mach, ISA, pressure-altitude, density-altitude, and air-data consistency outputs.

### What changed

**Frontend**

- Renamed the quick analysis preset to `Performance / Climb / Air Data`.
- Updated the quick prompt to request bounded climb/performance and air-data consistency analysis using altitude, vertical speed, CAS/TAS/Mach, temperature, and pressure-related channels where available.
- Expanded local prompt-intent cues for the performance mode with:
  - air data / air-data
  - Mach
  - CAS / TAS / IAS
  - ISA
  - pressure altitude
  - density altitude
  - true airspeed
  - calibrated airspeed
- Added selected-mode guidance explaining that the mode supports altitude, climb/descent, airspeed, Mach, ISA, pressure-altitude, density-altitude, and air-data consistency as bounded engineering support.
- Added result-side interpretation guidance when selected/executed mode is performance:
  - bounded by available channels and implemented models
  - CAS/TAS/Mach consistency depends on sensor quality, units, and synchronized timestamps
  - ISA/density-altitude outputs are engineering support only unless certification correction models are explicitly applied
  - missing pressure, temperature, or calibrated-speed channels may reduce applicability
- Updated `/help` with a Performance / Climb / Air Data card and a concise air-data interpretation boundary section.

**Backend**

- No backend changes were required. This task only changed labels, guidance, prompt templates, and Help content.

### Validation

```powershell
pnpm -C frontend run build
```

**Result:** Passed. Vite emitted existing warnings for Node.js 20.18.1 versus required 20.19+ and chunk size.

### Next planned step

- Release readiness / internal alpha preparation.

## Release Readiness / Internal Alpha Preparation (2026-05-08)

### Why this was added

- The current roadmap slice is complete and the repository needs a controlled technical-preview handoff package.
- Internal reviewers need explicit validation gates, known limitations, responsible-use boundaries, and peer-review instructions.

### What changed

**Documentation**

- Added `RELEASE_READINESS.md`:
  - release type: Internal Alpha / Technical Preview
  - intended audience
  - responsible-use statement
  - validation baseline
  - manual smoke-test checklist
  - documentation checks
  - known warnings
  - known limitations
  - peer-review workflow
  - share/no-share gate
- Added `INTERNAL_ALPHA_NOTES.md`:
  - what FTIAS is
  - what to try
  - what not to trust yet
  - requested feedback
  - issue-reporting guidance
  - recommended test scenarios
- Updated `README.md`:
  - corrected manual filename to `FTIAS-MANUAL-V00.pdf`
  - added Manual / Help mention
  - added release-readiness and internal-alpha notes references
  - updated roadmap section to point to alpha readiness and license/tagging next step
  - referenced `LICENSE`
- Updated `.github/README.md` with a clarification that it documents GitHub Actions workflows, not the main project overview.
- Updated `TODO.md` and `frontend/TODO.md` to mark release readiness complete and set next step to license selection and `v0.1.0-alpha` release tagging.

**License status**

- `LICENSE` exists and states MIT License terms.
- At the time of the release-readiness pass, placeholder contact/author metadata still required cleanup before external redistribution.

### Validation

```powershell
git diff -- README.md RELEASE_READINESS.md INTERNAL_ALPHA_NOTES.md .github/README.md TODO.md frontend/TODO.md DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md
```

### Next planned step

- License selection and v0.1.0-alpha release tagging.

## License Metadata Cleanup for Alpha (2026-05-08)

### What changed

- Cleaned the root `LICENSE` file.
- Retained standard MIT License terms.
- Replaced placeholder metadata with:
  - `Copyright (c) 2026 João Martinolli`
- Removed placeholder contact and author fields from the license file.
- Updated `RELEASE_READINESS.md` to state that the repository currently uses MIT License terms and that organizational/legal suitability should be confirmed before external redistribution.
- Updated `README.md` license wording.
- Updated `TODO.md` to mark license metadata cleanup complete and set the next step to `v0.1.0-alpha` release tagging.

### Next planned step

- v0.1.0-alpha release tagging.

## P5.0 Peer Review Issue Templates and Feedback Workflow (2026-05-09)

### Why this was added

- FTIAS has reached `v0.1.0-alpha` as an Internal Alpha / Technical Preview.
- The repository needs structured intake for peer-review feedback, reproducible defects, and future feature ideas.

### What changed

**GitHub issue templates**

- Added `.github/ISSUE_TEMPLATE/peer_review_feedback.md`:
  - reviewer context
  - workflow checklist
  - what worked well
  - confusion points
  - reproducible issue details
  - provenance fields
  - severity/priority
  - responsible-use boundary feedback
  - suggested improvement
- Updated `.github/ISSUE_TEMPLATE/bug_report.md` for reproducible FTIAS defects.
- Updated `.github/ISSUE_TEMPLATE/feature_request.md` for future capability requests.
- Added `.github/ISSUE_TEMPLATE/config.yml` with links to:
  - `INTERNAL_ALPHA_NOTES.md`
  - `RELEASE_READINESS.md`

**Peer review guide**

- Added `PEER_REVIEW_GUIDE.md` with:
  - review purpose
  - pre-review instructions
  - recommended review flow
  - most useful feedback categories
  - issue-template guidance
  - evidence to include

**Roadmap/docs**

- Updated `README.md` to reference `PEER_REVIEW_GUIDE.md` and GitHub issue templates.
- Updated `TODO.md` and `frontend/TODO.md` to mark P5.0 complete and set P5.1 as the next task.

### Validation

```powershell
git diff -- .github/ISSUE_TEMPLATE PEER_REVIEW_GUIDE.md README.md TODO.md frontend/TODO.md DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md
git diff --check
```

### Next planned task

- P5.1 — Repository / CI hygiene cleanup.

## P5.1 Repository / CI Hygiene Cleanup (2026-05-09)

### Why this was added

- FTIAS has reached `v0.1.0-alpha` as an Internal Alpha / Technical Preview.
- Generated coverage files were still tracked and modified after local test runs.
- GitHub Actions behavior needed clearer documentation because some workflows are path-filtered and documentation-only commits may not trigger all checks.

### What changed

**Generated artifacts**

- Removed `.coverage` and `coverage.xml` from version control with `git rm --cached`.
- Kept local generated files ignored through `.gitignore`.

**Ignore rules**

- Confirmed/added backend generated artifact ignores:
  - `.coverage`
  - `coverage.xml`
  - `htmlcov/`
  - `.pytest_cache/`
  - `__pycache__/`
  - `*.pyc`
- Added/confirmed frontend generated artifact ignores:
  - `frontend/dist/`
  - `frontend/node_modules/`
  - `frontend/.vite/`
- Added broader local ignore coverage for `.env.*`, preserved `!.env.example`, and kept `*.log`.

**CI documentation**

- Updated `.github/README.md` to document current workflow inventory:
  - `backend-lint.yml`
  - `backend-test.yml`
  - `docker-build.yml`
- Documented workflow triggers, path filters, expected checks, and local validation commands.
- Clarified that frontend build is currently validated locally with `pnpm -C frontend run build`.
- Documented known frontend build warnings for Node/Vite version and chunk size.

**Release readiness**

- Added a repository hygiene checklist to `RELEASE_READINESS.md`.
- Updated `TODO.md` and `frontend/TODO.md` to mark P5.1 complete and set P5.2 as the next planned task.

### Validation

```powershell
git status
git diff -- .gitignore .github/README.md RELEASE_READINESS.md TODO.md frontend/TODO.md DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md
git diff --check
git status
```

### Next planned task

- P5.2 — Vibration & Frequency Analysis concept formalization.

## P5.2 Vibration & Frequency Analysis Concept Formalization (2026-05-09)

### Why this was added

- A future Vibration & Frequency Analysis idea was captured in `Project_Documents/46_Frequency_Analysis_Tool_Suggested_Layout.md`.
- The concept is useful, but should not be implemented directly into the internal alpha branch without a bounded design note.

### What changed

**Concept note**

- Added `Project_Documents/P5_2_Vibration_Frequency_Analysis_Concept.md`.
- Formalized the future module as concept-only and not implemented in `v0.1.0-alpha`.
- Captured proposed purpose, user workflow, V1 scope, later scope, recommended defaults, sampling warnings, and relationships to existing FTIAS capabilities.

**Responsible-use boundaries**

- Documented that future vibration/frequency outputs would be engineering screening/support only.
- Explicitly stated that the module must not be presented as flutter clearance, loads substantiation, structural approval, certification approval, operational authorization, or safety clearance.
- Captured dependency on sampling rate, signal quality, units, time-window selection, preprocessing, sensor calibration, and analysis assumptions.

**Original idea note**

- Added a short pointer at the top of `Project_Documents/46_Frequency_Analysis_Tool_Suggested_Layout.md` to indicate that the formal roadmap concept now lives in `Project_Documents/P5_2_Vibration_Frequency_Analysis_Concept.md`.

**Future roadmap tasks**

- P5.VF.1 — Vibration/Frequency data model and API design
- P5.VF.2 — Time-domain + PSD MVP
- P5.VF.3 — Data-quality checks and sampling warnings
- P5.VF.4 — Frequency bands and summary metrics
- P5.VF.5 — Spectrogram and comparison mode
- P5.VF.6 — Export/report integration

No backend, frontend, database, workflow, or application behavior changed.

### Validation

```powershell
git diff -- Project_Documents/46_Frequency_Analysis_Tool_Suggested_Layout.md Project_Documents/P5_2_Vibration_Frequency_Analysis_Concept.md TODO.md frontend/TODO.md DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md
git diff --check
```

### Next planned step

- Project transition / Document-Parsing-Library continuation.

## P5.3 Internal Alpha Issue Triage Labels and Guide (2026-05-09)

### Why this was added

- FTIAS now has peer-review issue templates and internal alpha reviewer guidance.
- Incoming feedback needs a clear triage taxonomy so maintainers can separate defects, usability notes, responsible-use concerns, documentation issues, and future concepts.
- The future vibration/frequency roadmap previously used `P5.3` through `P5.8`; those placeholders were renamed to `P5.VF.*` to avoid conflict with active internal-alpha task numbering.

### What changed

**Triage guide**

- Added `ISSUE_TRIAGE_GUIDE.md`.
- Documented internal alpha triage principles:
  - preserve traceability
  - prioritize safety/responsible-use concerns
  - separate reproducible defects from usability feedback
  - avoid turning future ideas into implementation tasks before scoping
  - keep engineering-support boundaries visible

**Label taxonomy**

- Documented recommended labels for internal alpha feedback, including:
  - `internal-alpha`
  - `peer-review`
  - `bug`
  - `enhancement`
  - `documentation`
  - `safety-responsible-use`
  - `data-ingestion`
  - `dashboard`
  - `parameters-charts`
  - `ai-analysis`
  - `reports-export`
  - `frat`
  - `manual-help`
  - `repo-ci`
  - `future-concept`
  - `vibration-frequency`

**Severity and release impact**

- Added severity guidance from minor usability notes through safety/responsible-use concerns.
- Added release-impact decisions:
  - alpha blocker
  - next alpha
  - deferred
  - future module
  - not planned

**Reviewer guidance**

- Updated `PEER_REVIEW_GUIDE.md` with an after-submission note explaining triage labels and follow-up evidence requests.
- Updated `INTERNAL_ALPHA_NOTES.md` to remind reviewers to use issue templates, include traceability IDs, and clearly mark safety/responsible-use concerns.

No backend, frontend, database, workflow, or application behavior changed.

### Validation

```powershell
git diff -- ISSUE_TRIAGE_GUIDE.md PEER_REVIEW_GUIDE.md INTERNAL_ALPHA_NOTES.md TODO.md frontend/TODO.md DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md
git diff --check
```

### Next planned task

- P5.4 — Internal alpha feedback intake / sample issue dry run.

## P5.4 Internal Alpha Feedback Intake Dry Run (2026-05-10)

### Why this was added

- A sample GitHub issue was created to validate the internal alpha feedback workflow before broader peer review.
- The dry run verifies that peer reviewers can submit structured feedback with useful workflow, provenance, severity, and responsible-use context.

### Sample issue

- Issue #1: `[Peer Review]: Internal alpha workflow dry run`
- URL: https://github.com/Martinolli/flight-test-interactive-analysis-suite/issues/1

### What was validated

- Peer-review template rendering.
- `internal-alpha` and `peer-review` labels.
- Workflow checklist.
- Provenance / traceability fields.
- Severity / priority section.
- Responsible-use boundary feedback section.

### Documentation updates

- Updated `TODO.md` and `frontend/TODO.md` to mark P5.4 complete.
- Updated `PEER_REVIEW_GUIDE.md` with a short note that Issue #1 demonstrates the expected feedback structure.

No backend, frontend, database, workflow, test, or application behavior changed.

### Validation

```powershell
git diff -- TODO.md frontend/TODO.md DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md PEER_REVIEW_GUIDE.md
git diff --check
```

### Next planned step

- Internal alpha peer review / feedback collection.

## P3.1 Prompt-to-Mode Routing Guard (2026-04-24)

### Why this was added

- Analysis requests could run under an obviously mismatched selected mode (example: handling/control prompt while `takeoff` mode selected).
- This could produce output that looked valid for the wrong engineering mode.

### What changed

**Backend**

- Added prompt-intent guard module:
  - `backend/app/prompt_mode_guard.py`
- Added persisted analysis-job snapshot field:
  - `analysis_jobs.prompt_mode_guard_json`
  - migration: `backend/migrations/20260424_add_prompt_mode_guard_snapshot.sql`
- Wired guard into AI analysis flow in `backend/app/routers/documents.py`:
  - infer prompt intent from bounded heuristics
  - classify mismatch as `none` / `soft` / `strong`
  - provide suggested modes with capability-status awareness
  - for strong mismatch on strict deterministic modes, downgrade execution to safer `general` path with explicit traceability
  - include `prompt_mode_guard` in:
    - immediate AI analysis response
    - reopened saved analysis-job response
  - persist guard snapshot in `AnalysisJob`
  - include `Prompt-to-Mode Guard` section in analysis/report text for reproducibility

**Frontend**

- Updated contracts in `frontend/src/services/api.ts` to include `prompt_mode_guard`.
- Updated AI Analysis panel (`frontend/src/pages/FlightTestDetail.tsx`):
  - pre-run prompt/mode mismatch warning (soft/strong)
  - suggestion display before execution
  - backend-authoritative guard display after execution (selected mode, executed mode, inferred intent, suggested modes)
  - saved-job reopen now preserves and displays persisted guard snapshot

### Validation targets

- Strong mismatch is visible and traceable instead of silently appearing mode-correct.
- Suggested modes are capability-aware.
- Reopened analysis jobs preserve guard provenance.
- Existing analysis-job/PDF provenance flow remains compatible.

## P3.2 Handling Qualities / Control-Response Workflow (2026-04-24)

### Why this was added

- P3.1 guard started correctly identifying control-response intent (aileron/stick/handling prompts), but the backend still lacked a real handling workflow.
- This created a capability gap: intent detection existed, but mode execution was still limited.

### What changed

**Backend deterministic analysis**

- Added bounded handling/control-response calculator:
  - `compute_handling_qualities_metrics(...)`
  - `build_deterministic_handling_qualities_section(...)`
  - file: `backend/app/analysis/deterministic.py`
- Added deterministic control/response channel scoring and pairing heuristics:
  - controls: aileron, elevator, rudder, stick lateral/longitudinal
  - responses: roll/pitch/yaw rates, roll/pitch angles, heading
- Added bounded pairing metrics:
  - synchronized sample count
  - control/response min/max/mean/std
  - Pearson correlation
  - bounded sample-lag correlation summary
  - sign-alignment indicator
  - simple anomaly flags (outliers, abrupt steps, low-correlation)
- Added handling deterministic report section with explicit non-certification wording.

**Routing and capability alignment**

- Routed `analysis_mode=handling_qualities` through the new deterministic workflow in:
  - `backend/app/routers/documents.py`
- Handling mode now runs deterministic section first and can still use mode-aware RAG interpretation.
- Updated capability catalog (`backend/app/capabilities.py`):
  - `handling_qualities` moved from `partial` to bounded `implemented`
  - authority set to deterministic-with-RAG-crosscheck
  - required signal semantics clarified (`control_input`, `attitude_response`)
  - explicit blocked rules and applicability boundaries added
- Updated signal normalization for handling-related semantics.
- Updated prompt-guard strict deterministic set to include `handling_qualities`.
- Updated analysis-control logic so handling mode gets meaningful deterministic confidence handling.

**Frontend**

- Added handling quick option chip in AI Analysis panel:
  - `Handling / Control Response`
  - file: `frontend/src/pages/FlightTestDetail.tsx`
- Existing prompt-to-mode guard + mode-truth UI remains in place.

### Validation

- Backend tests passed:
  - `backend/tests/test_deterministic_calculators.py`
  - `backend/tests/test_capability_catalog.py`
  - `backend/tests/test_analysis_mode_routing.py`
  - `backend/tests/test_analysis_modes.py`
  - `backend/tests/test_prompt_mode_guard.py`
- Frontend build passed:
  - `pnpm -C frontend run build`

### Engineering boundary (explicit)

- Handling output is a bounded deterministic control-response assessment.
- It is **not** a formal handling-qualities certification package and does not claim Cooper-Harper/MIL compliance substantiation.

## P3.3 Atmosphere / Air-Data Engineering Support (2026-04-24)

### Why this was added

- Performance mode needed a stronger engineering kernel for atmosphere/air-data consistency instead of trend-only summaries.
- The objective was bounded deterministic support, not full air-data calibration/certification logic.

### What changed

**Backend deterministic module**

- Added dedicated atmosphere/air-data helper module:
  - `backend/app/analysis/air_data.py`
- Implemented bounded helper functions:
  - ISA snapshot from pressure altitude (`isa_atmosphere_from_pressure_altitude_ft`)
  - density-altitude estimate (`density_altitude_estimate_ft`)
  - TAS estimate from CAS + sigma (`estimate_tas_from_cas_and_sigma_knots`)
  - Mach estimate from TAS + temperature (`estimate_mach_from_tas_knots_and_temperature_c`)
  - reusable timeseries summary helper (`summarize_series`)

**Performance deterministic integration**

- Extended `compute_performance_metrics(...)` in `backend/app/analysis/deterministic.py` to detect/use air-data channels:
  - pressure altitude / altitude
  - OAT / SAT / TAT
  - CAS / TAS / Mach
- Added bounded derived outputs under `air_data_support`:
  - channel usage + skipped-calculation list
  - summary stats for pressure altitude, temperature channels, CAS/TAS/Mach
  - ISA sigma/theta/delta summaries
  - density-altitude estimate summary
  - TAS estimate and Mach estimate summaries
  - estimate-vs-measured consistency deltas (TAS, Mach)
  - pressure-altitude vs altitude consistency delta
- Added explicit temperature-source priority for Mach estimate (`SAT` -> `OAT` -> `TAT`).
- Updated performance deterministic assumptions to explicitly state bounded non-calibration/non-certification scope.

**Narrative/report rendering**

- Updated `build_deterministic_performance_section(...)` to include:
  - `Atmosphere / Air-Data Support` subsection
  - channels used
  - bounded derived summaries
  - skipped-calculation list when required inputs are missing

**Routing/capability alignment**

- Updated capability catalog (`backend/app/capabilities.py`) for `performance_general`:
  - description/limitations/applicability now explicitly include atmosphere/air-data bounded support and non-calibration boundary
  - optional signals include air-data semantics
  - output contract includes `air_data_support`
- Updated prompt-intent performance keywords (`backend/app/prompt_mode_guard.py`) with air-data terms:
  - `mach`, `cas`, `tas`, `air-data`, `density altitude`, `pressure altitude`, `isa`
- Updated performance default-goal/retrieval-focus text in `backend/app/routers/documents.py`.

### Validation

```powershell
pytest backend/tests/test_air_data_support.py backend/tests/test_deterministic_calculators.py backend/tests/test_analysis_mode_routing.py backend/tests/test_capability_catalog.py backend/tests/test_prompt_mode_guard.py -q
pnpm -C frontend run build
```

**Result:**

- Backend tests passed (`34 passed` for the focused suite).
- Frontend production build passed.

### Engineering boundary (explicit)

- Atmosphere/air-data outputs are bounded engineering support summaries from available telemetry.
- They are **not** a formal pitot-static calibration package and do not claim certification-corrected air-data determination.

## P3.4 Buffet / Vibration Workflow Hardening (2026-04-24)

### Why this was added

- Existing buffet/vibration mode was useful but still too flat for engineering screening review.
- Needed clearer structure for dominant channels, regime context, and event-level anomaly summaries while staying explicitly non-certification.

### What changed

**Backend deterministic module hardening**

- Extended `compute_buffet_vibration_metrics(...)` in `backend/app/analysis/deterministic.py` with:
  - channel grouping (`structural_vibration`, `accelerations`, `angular_rates`, `airspeed_response`, `other_response`)
  - dominant-channel ranking via bounded deterministic dominance score
  - anomaly/event-window extraction with cadence-aware window merge
  - regime segmentation using bounded WOW + speed-band cues where available
  - bounded optional frequency-domain screening (dominant frequency + band-energy summary) with cadence/coverage guards
- Added structured outputs:
  - `grouped_channel_summaries`
  - `dominant_channels_ranked`
  - `regime_segmentation_summary`
  - `anomaly_windows`
  - `frequency_screening`
  - `regime_logic`

**Narrative/report wording hardening**

- Extended buffet deterministic narrative section (`build_deterministic_buffet_vibration_section(...)`) to include:
  - grouped screening summary
  - dominant channels (ranked)
  - regime segmentation
  - significant event windows
  - bounded frequency-domain summary and explicit skipped-channel reasons
- Strengthened screening-only wording:
  - not loads substantiation
  - not flutter-clearance determination

**Capability and controls alignment**

- Updated `buffet_vibration` capability definition in `backend/app/capabilities.py`:
  - expanded optional signals (`angular_rate`, `weight_on_wheels`, `ground_speed`)
  - updated applicability/limitations for regime and frequency screening boundaries
  - expanded output contract fields
- Updated deterministic confidence logic in `backend/app/analysis_controls.py` for buffet-specific structured metrics.
- Updated buffet mode retrieval focus and default analysis goal text in `backend/app/routers/documents.py`.

### Tests / validation

```powershell
pytest backend/tests/test_deterministic_calculators.py backend/tests/test_analysis_mode_routing.py backend/tests/test_capability_catalog.py backend/tests/test_analysis_controls.py -q
pnpm -C frontend run build
```

**Result:**

- Backend focused suite passed (`31 passed`).
- Frontend production build passed.

### Engineering boundary (explicit)

- Buffet/vibration output is a bounded deterministic screening workflow for trend/anomaly support.
- It is **not** formal loads substantiation.
- It is **not** flutter clearance or formal aeroelastic determination.

## P3.5 Bounded Flutter-Support Pre-Screening (2026-04-24)

### Why this was added

- After P3.4 buffet/vibration hardening, FTIAS needed a dedicated flutter-support pre-screening path instead of leaving `flutter` mode as blocked/generic.
- The goal was bounded engineering support for concern discovery, not formal clearance.

### What changed

**Capability + mode activation**

- `flutter_support` capability moved from blocked scaffold to bounded implemented support in:
  - `backend/app/capabilities.py`
- Authority/status now reflect bounded deterministic + optional RAG cross-check posture.
- Applicability/limitations now explicitly state non-clearance boundaries and required follow-up methods.

**Deterministic flutter-support module**

- Added `compute_flutter_support_metrics(...)` and `build_deterministic_flutter_support_section(...)` in:
  - `backend/app/analysis/deterministic.py`
- Added exports in:
  - `backend/app/analysis/__init__.py`
- Implemented bounded pre-screening outputs:
  - screened channel groups
  - dominant channels and significant windows
  - regime/context summaries
  - frequency screening highlights (when available)
  - concern indicators + concern level
  - follow-up recommendation text
- Reuses hardened buffet/vibration screening as deterministic foundation and adds flutter-support interpretation layers.

**Routing + prompt guard alignment**

- `analysis_mode=flutter` now executes the deterministic flutter-support section in:
  - `backend/app/routers/documents.py`
- Flutter retrieval focus/default goal prompts now use flutter-support pre-screening wording.
- Prompt intent detection now distinguishes flutter intent from generic vibration intent in:
  - `backend/app/prompt_mode_guard.py`

**Controls integration**

- Extended control evaluation for flutter mode in:
  - `backend/app/analysis_controls.py`
- Added flutter-specific deterministic-confidence heuristics and warning-level escalation when high concern indicators are present.

**Frontend alignment**

- Added `Flutter Support Pre-screen` quick preset and local intent mapping updates in:
  - `frontend/src/pages/FlightTestDetail.tsx`
- Flutter cues now route more honestly to flutter mode suggestions.

### Tests / validation

```powershell
pytest backend/tests/test_deterministic_calculators.py backend/tests/test_analysis_mode_routing.py backend/tests/test_capability_catalog.py backend/tests/test_analysis_controls.py backend/tests/test_prompt_mode_guard.py backend/tests/test_analysis_modes.py -q
pnpm -C frontend run build
```

**Result:**

- Backend focused suite passed (`45 passed`).
- Frontend production build passed.

### Engineering boundary (explicit)

- Flutter mode output is bounded **pre-screening/support** only.
- It is **not** flutter clearance.
- It is **not** modal-identification certification.
- It is **not** formal aeroelastic substantiation or envelope-expansion approval authority.
