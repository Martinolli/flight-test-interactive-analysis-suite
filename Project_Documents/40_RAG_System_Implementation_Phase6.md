# 40 — RAG System Implementation: Phase 6 Complete

**Date:** 27 March 2026  
**Sprint:** Phase 6 — AI-Powered Document Analysis (RAG Pipeline)  
**Status:** Implementation Complete — Ready for Integration Testing

---

## Overview

Phase 6 delivers a full **Retrieval-Augmented Generation (RAG)** system to FTIAS, enabling AI-powered analysis of flight test data cross-referenced against indexed standards and handbooks (MIL-STD, FAR/CS, RTCA DO-xxx, NATOPS, etc.).

---

## Architecture Summary

| Component | Technology | Purpose |
|---|---|---|
| PDF Parser | **Docling** (IBM) | Preserves tables, section hierarchy, cross-references |
| Chunker | **HybridChunker** | Respects section boundaries; keeps tables intact |
| Embeddings | **OpenAI text-embedding-3-small** (1536 dims) | Semantic vector representation |
| Vector Store | **PostgreSQL + pgvector** | Multi-user, integrated with existing DB |
| LLM | **OpenAI GPT-4o-mini** | Answer generation and flight test analysis |
| Database Image | `pgvector/pgvector:pg15` | Replaces standard postgres:15 |

---

## Files Created / Modified

### Backend

| File | Change |
|---|---|
| `backend/app/models.py` | Added `Document` and `DocumentChunk` models with `Vector(1536)` embedding column |
| `backend/app/routers/documents.py` | New router: upload, list, delete, query, ai-analysis endpoints |
| `backend/app/main.py` | Registered `documents` router at `/api/documents` |
| `backend/requirements.txt` | Added `docling>=2.82.0`, `openai>=2.30.0`, `pgvector>=0.4.2`, `sentence-transformers>=5.3.0` |
| `docker-compose.yml` | Updated PostgreSQL image to `pgvector/pgvector:pg15` |

### Frontend

| File | Change |
|---|---|
| `frontend/src/services/api.ts` | Added `Document`, `QueryResponse`, `AIAnalysisResponse` types + API methods |
| `frontend/src/pages/DocumentLibrary.tsx` | New page: upload, list, delete documents with status tracking |
| `frontend/src/pages/AIQuery.tsx` | New page: chat-style semantic search against document library |
| `frontend/src/pages/FlightTestDetail.tsx` | Added `AIAnalysisPanel` component for per-test AI analysis |
| `frontend/src/components/Sidebar.tsx` | Added grouped navigation with "AI & Documents" section |
| `frontend/src/App.tsx` | Registered `/documents` and `/ai-query` routes |

---

## API Endpoints

### `POST /api/documents/upload`
Accepts a PDF file with optional metadata (`title`, `doc_type`, `description`). Runs the full ingestion pipeline:
1. Saves file to a temporary path.
2. Docling parses the PDF, extracting text, tables, and section headings.
3. HybridChunker splits the document into semantically coherent chunks (max 512 tokens each).
4. Each chunk is embedded with `text-embedding-3-small`.
5. Chunks are batch-inserted into `document_chunks` with their vector embeddings.
6. The `Document` record is updated to `status = "ready"`.

### `GET /api/documents/`
Returns all documents ordered by creation date (newest first).

### `DELETE /api/documents/{doc_id}`
Removes the document and all associated chunks (cascade delete).

### `POST /api/documents/query`
Semantic search + LLM answer generation:
1. Embeds the user's question.
2. Finds the top-k most similar chunks via pgvector cosine distance (`<=>` operator).
3. Passes chunks as context to GPT-4o-mini with a flight test engineer system prompt.
4. Returns the answer and source citations.

### `POST /api/documents/flight-tests/{flight_test_id}/ai-analysis`
Generates a structured flight test analysis report:
1. Computes per-parameter statistics (min, max, mean, std dev, sample count) from the database.
2. Embeds a query combining the aircraft type and parameter names.
3. Retrieves the 4 most relevant document chunks as reference context.
4. Asks GPT-4o-mini to produce a report with: Executive Summary, Parameter Analysis, Anomalies/Concerns, and Recommendations.

---

## Database Schema

### `documents` table
```sql
CREATE TABLE documents (
    id              SERIAL PRIMARY KEY,
    filename        VARCHAR(512) NOT NULL,
    title           VARCHAR(512),
    doc_type        VARCHAR(100),          -- 'standard', 'handbook', etc.
    description     TEXT,
    total_pages     INTEGER,
    total_chunks    INTEGER,
    file_size_bytes INTEGER,
    status          VARCHAR(50) DEFAULT 'processing',  -- processing | ready | error
    error_message   TEXT,
    uploaded_by_id  INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);
```

### `document_chunks` table
```sql
CREATE TABLE document_chunks (
    id             SERIAL PRIMARY KEY,
    document_id    INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index    INTEGER NOT NULL,
    text           TEXT NOT NULL,
    page_numbers   VARCHAR(255),     -- e.g. "12-14"
    section_title  VARCHAR(512),     -- heading hierarchy from Docling
    embedding      VECTOR(1536),     -- OpenAI text-embedding-3-small
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Performance index for cosine similarity search
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

> **Note:** The `ivfflat` index is recommended once the library contains >1,000 chunks. For smaller libraries the sequential scan is fast enough.

---

## Frontend Features

### Document Library (`/documents`)
- Drag-and-drop PDF upload with progress bar.
- Metadata form: title, document type, description.
- Table view showing all documents with status badges (Processing / Ready / Error).
- Delete with confirmation dialog.
- Info banner explaining Docling parsing and processing time expectations.

### AI Standards Query (`/ai-query`)
- Chat-style interface for ad-hoc questions against the document library.
- Example questions pre-populated for common flight test standards queries.
- Collapsible source citations showing document title, page numbers, section heading, and similarity score.
- Keyboard shortcut: Enter to send, Shift+Enter for new line.

### AI Analysis Panel (on `/flight-tests/:id`)
- "Analyse with AI" button triggers the per-test analysis endpoint.
- Displays structured report (Executive Summary, Parameter Analysis, Anomalies, Recommendations).
- Collapsible panel with "Re-run Analysis" option.
- Error handling with retry link.

### Sidebar Navigation
Reorganised into three groups:
- **Flight Tests:** Dashboard, Upload Data, Parameters
- **AI & Documents:** Document Library, AI Standards Query
- **Account:** Profile, Settings

---

## Configuration Required

To enable AI features, set the following environment variable in `backend/.env`:

```env
OPENAI_API_KEY=sk-...
```

Without this key, the upload endpoint will still ingest and chunk documents, but embedding and LLM calls will return a `503` error with a descriptive message.

---

## Testing Checklist

- [ ] Start Docker services: `docker compose up -d`
- [ ] Verify pgvector extension: `docker exec ftias-postgres psql -U ftias_user -d ftias_db -c "\dx"`
- [ ] Upload a small PDF (e.g., a 10-page excerpt from FAR Part 25)
- [ ] Confirm document status changes from `processing` → `ready`
- [ ] Run a query: "What are the stall speed requirements?"
- [ ] Open a flight test with uploaded CSV data and click "Analyse with AI"
- [ ] Verify source citations appear in query responses

---

## Known Limitations

1. **Processing time:** Large documents (200+ pages) may take 2–5 minutes due to Docling's thorough parsing. The frontend shows a progress bar during upload but does not poll for background completion — the response is synchronous.
2. **Synchronous processing:** The upload endpoint blocks until processing is complete. For very large documents, consider adding a background task queue (Celery/ARQ) in a future phase.
3. **OpenAI dependency:** Both embedding and LLM calls require `OPENAI_API_KEY`. A future phase could add a local embedding model (e.g., `all-MiniLM-L6-v2` via sentence-transformers) as a fallback.
4. **No pagination:** The document list and query results are not paginated. This is acceptable for the current scale (< 100 documents).

---

## Next Steps (Phase 7)

- Add background task processing for large PDF uploads (non-blocking).
- Add a document re-indexing endpoint (re-parse and re-embed without re-uploading).
- Add a `total_pages` extraction from Docling result metadata.
- Consider adding a local embedding fallback using `sentence-transformers`.
- Add unit tests for the documents router (`tests/test_documents.py`).
