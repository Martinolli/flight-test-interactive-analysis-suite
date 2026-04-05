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
