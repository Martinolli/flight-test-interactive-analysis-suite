# FTIAS Session 6 — Document Ingestion Overhaul (2026-04-05)

## Session Summary

This session resolved the remaining blockers in the RAG document ingestion pipeline and delivered a production-stable implementation. The core issue was that the upload HTTP request blocked until the entire PDF parse, chunk, embed, and persist cycle completed — causing apparent hangs for large documents and HTTP timeouts. A secondary issue was that the HybridChunker tokenizer was configured with a tiktoken identifier (`cl100k_base`) that Docling does not support.

All changes from this session are committed to `main` under commit `fc3d99b` (and the preceding tokenizer fix `2c6d0c3`).

---

## Problems Resolved

| # | Problem | Root Cause | Fix |
|---|---------|-----------|-----|
| 1 | Upload appeared to hang | Full PDF parse + embed ran synchronously inside the HTTP request | Moved to FastAPI `BackgroundTasks` |
| 2 | Many OpenAI API round-trips | Embeddings generated one chunk at a time | Batched embedding with `embed_texts()` |
| 3 | No visibility into processing state | Frontend did not poll for status changes | 5-second polling loop while `processing` count > 0 |
| 4 | HybridChunker tokenizer error | `cl100k_base` is a tiktoken name; Docling requires a Hugging Face model ID | Removed `tokenizer=` argument; uses default `sentence-transformers/all-MiniLM-L6-v2` |
| 5 | `DEBUG=release` caused Pydantic parse error | `BaseSettings` tried to cast `"release"` to `bool` | Added `@field_validator("DEBUG")` that maps `release/production` → `False` |
| 6 | Schema import failures in tests | `email-validator` package missing | Added `email-validator>=2.2.0` to `requirements.txt` |
| 7 | Uvicorn `--reload` interfered with background tasks | File-watcher restarts killed in-flight background workers | Removed `--reload` from both `docker-compose.yml` files |

---

## Architecture Change: Background Task Queue

### Before

```
POST /api/documents/upload
  ├─ save file to disk
  ├─ Docling parse (30–300 s)
  ├─ HybridChunker split
  ├─ embed each chunk (N × OpenAI API call)
  ├─ persist chunks to DB
  └─ return HTTP 200  ← client waits the entire time
```

### After

```
POST /api/documents/upload
  ├─ save file to temp path
  ├─ INSERT document row (status="processing")
  ├─ schedule _process_document_upload() as BackgroundTask
  └─ return HTTP 200 immediately  ← client unblocks

BackgroundTask (runs concurrently)
  ├─ Docling parse
  ├─ HybridChunker split + oversized-chunk guard
  ├─ embed_texts() in batches of EMBEDDING_BATCH_SIZE
  │    └─ per-chunk fallback if a batch fails
  ├─ bulk INSERT chunks
  └─ UPDATE document status → "ready" | "error"
```

---

## Docling Performance Configuration

All Docling tuning parameters are now environment-variable-driven, making them adjustable without a code change or container rebuild.

| Environment Variable | Default | Description |
|---|---|---|
| `DOCLING_NUM_THREADS` | `4` | CPU threads for Docling's accelerator |
| `DOCLING_FAST_MODE` | `false` | Disable table structure extraction globally |
| `DOCLING_AUTO_FAST_FOR_LARGE_FILES` | `true` | Auto-enable fast mode above size threshold |
| `DOCLING_FAST_THRESHOLD_MB` | `25` | File size (MB) that triggers auto fast mode |
| `DOCLING_TABLE_STRUCTURE` | `true` | Enable table structure extraction |
| `DOCLING_MAX_CHUNK_CHARS` | `5000` | Split oversized chunks to avoid tokenizer slow paths |
| `EMBEDDING_BATCH_SIZE` | `32` | Chunks per OpenAI embedding batch call |

**Recommended baseline for aviation standards (text-based PDFs):**

```env
DOCLING_NUM_THREADS=4
DOCLING_FAST_MODE=false
DOCLING_AUTO_FAST_FOR_LARGE_FILES=true
DOCLING_FAST_THRESHOLD_MB=25
DOCLING_TABLE_STRUCTURE=true
DOCLING_MAX_CHUNK_CHARS=5000
EMBEDDING_BATCH_SIZE=64
```

For very large documents (>50 MB) or when speed is more important than table accuracy:

```env
DOCLING_FAST_MODE=true
```

---

## Files Changed

| File | Change Type | Description |
|---|---|---|
| `backend/app/routers/documents.py` | Major refactor | Background task, batch embeddings, Docling env flags, oversized-chunk guard, progress logging |
| `frontend/src/pages/DocumentLibrary.tsx` | Enhancement | 5-second polling while processing; updated upload toast message |
| `backend/app/config.py` | Bug fix | `DEBUG` field validator accepts `release`/`production`/`dev` aliases |
| `backend/requirements.txt` | Dependency | Added `email-validator>=2.2.0` |
| `docker-compose.yml` | Config | Removed `--reload`; added all new env vars |
| `docker-compose.backend-only.yml` | Config | Same as above for the backend-only compose file |
| `.dockerignore` | New file | Excludes `node_modules`, `__pycache__`, `.git` from Docker build context |
| `DOC_PROCESSING_FIX_SUMMARY_2026-04-04.md` | New file | Full fix summary and Docker runbook (root of repo) |
| `backend/prewarm_docling.py` | New file | Pre-warms Docling models and tokenizer inside the container |

---

## Git Commits This Session

| Commit | Message |
|---|---|
| `fc3d99b` | feat: document ingestion stability & performance overhaul (2026-04-04) |
| `2c6d0c3` | fix: use default HybridChunker tokenizer instead of invalid cl100k_base |

---

## Validation

- Python compile check passed for all modified backend files.
- `pytest backend/tests/test_health.py -q` — passed.
- Manual end-to-end test: PDF upload returns immediately, document shows `Processing` status, transitions to `Ready` automatically after background indexing completes.
- AI Query and AI Analysis features confirmed working with indexed documents.

---

## Current Feature Status

| Feature | Status |
|---|---|
| User authentication (JWT) | Complete |
| Flight test CRUD | Complete |
| CSV data upload & parameter parsing | Complete |
| Time-series parameter visualisation | Complete |
| Document Library (upload, list, delete) | Complete |
| Background document ingestion | **Complete (this session)** |
| Semantic search (AI Query) | Complete |
| AI Analysis report (per flight test) | Complete |
| Docling performance tuning | **Complete (this session)** |
| Frontend status polling | **Complete (this session)** |

---

## Next Steps (Priority Order)

### Priority 1 — Rebuild Docker Image (Immediate)

The current container has `libxcb1` and `libgl1` installed manually (not persistent). A full rebuild is needed to make all fixes permanent:

```powershell
# From repo root
docker compose up -d --build backend
docker compose exec backend python /app/prewarm_docling.py
```

### Priority 2 — User Management Panel

An admin panel for viewing registered users, resetting passwords, and managing roles. This is the most-requested operational feature.

**Scope:**
- `GET /api/admin/users` — list all users with role and last-login
- `PATCH /api/admin/users/{id}` — update role or reset password
- Frontend: admin-only route in the sidebar

### Priority 3 — PDF Report Export from AI Analysis

Allow users to download the AI Analysis report as a formatted PDF.

**Scope:**
- Backend: `GET /api/flight-tests/{id}/ai-analysis/export` — generate PDF via `reportlab` or `weasyprint`
- Frontend: "Export PDF" button in the AI Analysis panel

### Priority 4 — Celery / Redis Task Queue (Optional Upgrade)

FastAPI `BackgroundTasks` is sufficient for single-worker deployments. If the system needs to scale to multiple workers or survive container restarts mid-ingestion, migrate to Celery + Redis.

**Trigger:** Only needed if ingestion jobs are lost after container restarts become a reported issue.

### Priority 5 — Persistent Docker Image Build

Move `libxcb1`, `libgl1`, and the Docling pre-warm into `backend.Dockerfile` so they survive container rebuilds without manual intervention.

**File:** `docker/backend.Dockerfile`

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Pre-warm Docling models at build time
RUN python /app/prewarm_docling.py
```
