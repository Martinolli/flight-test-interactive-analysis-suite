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
