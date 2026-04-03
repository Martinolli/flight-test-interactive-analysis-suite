# FTIAS — Next Steps Roadmap (Post Session 5)
**Document:** 41 | **Date:** April 3, 2026 | **Status:** Planning

---

## Context

Session 5 brought the entire FTIAS application to a fully verified operational state. All pages load correctly, the RAG pipeline is functional, and PDF document ingestion is confirmed working. Two documents were uploaded in testing — one completed successfully (status: **Ready**), and one was still processing at the end of the session due to Docling's slow parsing speed.

The primary technical debt items are: the Docling performance problem, the lack of a background task queue, and the need to rebuild the Docker image to make the `libxcb1` fix persistent.

---

## Immediate Action Required (Before Next Session)

After the second document finishes processing, run these three commands from the project root to rebuild the Docker image with all system libraries baked in:

```powershell
docker compose down
docker compose build --no-cache backend
docker compose up -d
docker exec ftias-backend python /app/reset_password.py
```

The rebuild takes 10–20 minutes. The final command resets the `testuser` password after the fresh container starts.

---

## Priority 1 — PDF Parser Replacement (High)

### The Problem

Docling is a comprehensive document understanding library that performs layout analysis, table detection, figure extraction, and semantic chunking. This thoroughness makes it accurate but extremely slow — processing a typical 20-page aviation standard PDF takes 3–8 minutes on a standard laptop CPU. For a tool intended for operational use by flight test engineers, this is not acceptable.

### Candidate Replacements

| Parser | Speed | Accuracy | Cost | Dependencies |
|---|---|---|---|---|
| **pymupdf4llm** | Very fast (seconds) | Good — clean Markdown output | Free, open-source | `pymupdf4llm` pip package only |
| **LlamaParse** | Fast (cloud API) | Excellent — table-aware | Paid API (free tier available) | API key required |
| **pypdf + custom chunker** | Fast | Basic — plain text only | Free | `pypdf` |
| **Docling (current)** | Very slow (minutes) | Excellent — layout-aware | Free | Heavy (torch, transformers) |

### Recommended Approach

**Phase 1 (next session):** Replace Docling with `pymupdf4llm` as the default parser. It is a single pip package with no system library dependencies, produces clean Markdown from PDFs in seconds, and handles tables reasonably well. The swap is a drop-in replacement in the `parse_document()` function in `backend/app/routers/documents.py`.

**Phase 2 (future):** Add an optional LlamaParse path for users who need higher accuracy on complex documents (e.g., multi-column layouts, embedded tables). LlamaParse can be selected per-upload via a `parser` field in the upload form.

### Implementation Plan for pymupdf4llm

```python
# backend/app/routers/documents.py — replace the Docling block with:
import pymupdf4llm

def parse_document(file_path: str) -> list[str]:
    """Parse a PDF and return a list of text chunks."""
    md_text = pymupdf4llm.to_markdown(file_path)
    # Split into chunks of ~800 tokens with 100-token overlap
    chunks = chunk_text(md_text, chunk_size=800, overlap=100)
    return chunks
```

Add to `requirements.txt`:
```
pymupdf4llm>=0.0.17
```

Remove from `requirements.txt` (optional — reduces image size by ~3 GB):
```
docling
torch
torchvision
sentence-transformers
```

---

## Priority 2 — Background Task Queue (High)

### The Problem

The current `POST /api/documents/upload` endpoint is synchronous — it blocks the HTTP connection until the entire parse + chunk + embed pipeline completes. For large documents this means the browser waits for minutes with no feedback, and the connection may time out.

### Solution: FastAPI BackgroundTasks

FastAPI has a built-in `BackgroundTasks` mechanism that requires no extra dependencies (no Celery, no Redis). The endpoint returns immediately with `status: processing`, and the parsing runs in the background.

```python
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    ...
):
    # Save file, create DB record with status="processing"
    doc = create_document_record(...)
    # Schedule parsing in background
    background_tasks.add_task(process_document, doc.id, file_path)
    # Return immediately
    return {"id": doc.id, "status": "processing"}
```

The frontend already polls `GET /api/documents` every 10 seconds and updates the status badge automatically — no frontend changes are needed.

---

## Priority 3 — User Management Panel (Medium)

### The Problem

There is currently no UI for creating new users or resetting passwords. The only way to create a user is via the Swagger UI at `http://localhost:8000/docs`, and the only way to reset a password is by running `reset_password.py` inside the Docker container.

### Solution

Add an admin-only section to the Settings page (or a dedicated `/admin/users` route) with:
- A table listing all users (username, email, role, created date)
- A "Create User" button with a form (username, email, password, role)
- A "Reset Password" action per user
- A "Toggle Admin" action per user

The `User` model already has `is_superuser` and `role` fields. The backend `users` router already has `POST /api/users/` for creation. Only the frontend UI and a password-reset endpoint need to be added.

---

## Priority 4 — Automated Report Generation (Medium)

### The Problem

The AI Analysis panel generates a structured text report in the browser but there is no way to export it. Flight test engineers need to share reports with colleagues and include them in test reports.

### Solution

Add a "Export as PDF" button to the AI Analysis panel. The backend generates a formatted PDF using `reportlab` or `weasyprint` and returns it as a file download. The report should include:
- Flight test metadata (name, date, aircraft, duration)
- Statistical summary table (min, max, mean, std dev per parameter)
- The full AI analysis text
- FTIAS branding and page numbers

---

## Priority 5 — Unit Tests for Documents Router (Medium)

### The Problem

The documents router has no automated tests. Any refactoring (e.g., replacing Docling with pymupdf4llm) risks breaking the upload, query, or delete endpoints silently.

### Solution

Add `backend/tests/test_documents.py` with pytest tests covering:
- `POST /api/documents/upload` — mock the parser, verify DB record creation
- `GET /api/documents` — verify list endpoint returns correct schema
- `DELETE /api/documents/{id}` — verify document and chunks are removed
- `POST /api/documents/query` — mock OpenAI, verify response schema

---

## Summary Table

| Priority | Item | Effort | Dependency |
|---|---|---|---|
| **Immediate** | Rebuild Docker image | 20 min | None |
| **1 (High)** | Replace Docling with pymupdf4llm | 1–2 hours | None |
| **2 (High)** | Background task queue for uploads | 2–3 hours | None |
| **3 (Medium)** | User management panel | 3–4 hours | None |
| **4 (Medium)** | Automated PDF report export | 2–3 hours | None |
| **5 (Medium)** | Unit tests for documents router | 2–3 hours | Priority 1 complete |

---

*This document was prepared at the end of Session 5 to guide the Session 6 development plan.*
