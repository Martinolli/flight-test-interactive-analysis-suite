"""
FTIAS Backend - Documents Router
RAG pipeline: ingest PDF standards/handbooks with Docling,
embed with OpenAI text-embedding-3-small, store in pgvector,
and answer questions with the built-in LLM.
"""

import logging
import os
import tempfile
import time
from typing import List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_AVAILABLE = False

try:
    from docling.document_converter import DocumentConverter as _DocumentConverter
    _DOCLING_AVAILABLE = True
except ImportError:
    _DocumentConverter = None  # type: ignore[assignment,misc]
    _DOCLING_AVAILABLE = False
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.models import DataPoint, Document, DocumentChunk, FlightTest, TestParameter, User

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# OpenAI client (reads OPENAI_API_KEY from environment)
# ---------------------------------------------------------------------------
_openai_client = None
EMBEDDING_BATCH_SIZE = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")))
DOCLING_NUM_THREADS = max(1, int(os.getenv("DOCLING_NUM_THREADS", "4")))
DOCLING_FAST_THRESHOLD_MB = max(1, int(os.getenv("DOCLING_FAST_THRESHOLD_MB", "25")))
DOCLING_MAX_CHUNK_CHARS = max(0, int(os.getenv("DOCLING_MAX_CHUNK_CHARS", "5000")))


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _require_ai_packages():
    """Raise a clear 503 if optional AI packages are not installed."""
    if not _OPENAI_AVAILABLE or not _DOCLING_AVAILABLE:
        missing = []
        if not _OPENAI_AVAILABLE:
            missing.append("openai")
        if not _DOCLING_AVAILABLE:
            missing.append("docling")
        raise HTTPException(
            status_code=503,
            detail=(
                f"AI packages not installed: {', '.join(missing)}. "
                "Run: pip install openai docling sentence-transformers pgvector"
            ),
        )


def get_openai_client():
    global _openai_client
    _require_ai_packages()
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY is not configured. "
                       "Add it to your .env file to enable AI features.",
            )
        _openai_client = _OpenAI(api_key=api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DocumentOut(BaseModel):
    id: int
    filename: str
    title: Optional[str]
    doc_type: Optional[str]
    description: Optional[str]
    total_pages: Optional[int]
    total_chunks: Optional[int]
    file_size_bytes: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class QueryRequest(BaseModel):
    question: str
    top_k: int = 6
    flight_test_id: Optional[int] = None  # optional context filter


class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]


class AIAnalysisResponse(BaseModel):
    analysis: str
    flight_test_name: str
    parameters_analysed: int


# ---------------------------------------------------------------------------
# Helper: embed a single text string
# ---------------------------------------------------------------------------

def embed_text(text_content: str) -> List[float]:
    """Return a 1536-dim embedding vector for the given text."""
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text_content,
    )
    return response.data[0].embedding


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return embeddings for multiple strings in one API request."""
    if not texts:
        return []
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Helper: parse and chunk a PDF with Docling
# ---------------------------------------------------------------------------

def _split_long_text(text_content: str, max_chars: int) -> List[str]:
    """Split oversized chunks into smaller pieces to avoid tokenizer slow paths."""
    if max_chars <= 0 or len(text_content) <= max_chars:
        return [text_content]

    pieces: List[str] = []
    current = ""
    for paragraph in text_content.split("\n\n"):
        if len(paragraph) > max_chars:
            if current:
                pieces.append(current.strip())
                current = ""
            for i in range(0, len(paragraph), max_chars):
                part = paragraph[i : i + max_chars].strip()
                if part:
                    pieces.append(part)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                pieces.append(current.strip())
            current = paragraph

    if current:
        pieces.append(current.strip())

    return pieces or [text_content]


def parse_and_chunk_pdf(
    pdf_path: str,
    file_size_bytes: Optional[int] = None,
    doc_id: Optional[int] = None,
) -> Tuple[List[dict], Optional[int]]:
    """
    Use Docling to parse a PDF and return a list of chunk dicts:
      { text, page_numbers, section_title }

    Docling's HybridChunker respects section boundaries and keeps
    tables intact as single chunks — critical for standards/handbooks.

    Performance tuning applied (see Project_Documents/42_Docling_Performance_Analysis.md):
    - do_ocr=False  : aviation standards are text-based PDFs (not scanned images)
                      OCR is the single biggest bottleneck (~70% of processing time)
    - do_table_structure=True : preserve tables — critical for performance data tables
    - do_picture_classification/description=False : not needed for text RAG
    - generate_page/picture_images=False : no image output needed
    - AcceleratorOptions(num_threads=4) : use all available CPU cores in the container
    - HybridChunker with tiktoken cl100k_base : avoids downloading BAAI model at runtime
    """
    try:
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.transforms.chunker.hybrid_chunker import HybridChunker

        # ----------------------------------------------------------------
        # Pipeline options: optimised for text-based aviation PDFs
        # ----------------------------------------------------------------
        pipeline_options = PdfPipelineOptions()

        # OCR: disable for native-text PDFs (FAR, CS-25, RTCA DO-xxx, etc.)
        # Enable only if you are ingesting scanned/image-only documents.
        pipeline_options.do_ocr = False

        force_fast_mode = _env_flag("DOCLING_FAST_MODE", False)
        auto_fast_for_large = _env_flag("DOCLING_AUTO_FAST_FOR_LARGE_FILES", True)
        table_structure_enabled = _env_flag("DOCLING_TABLE_STRUCTURE", True)

        file_size_mb = (
            (file_size_bytes / (1024 * 1024))
            if file_size_bytes is not None
            else None
        )
        is_large_file = (
            file_size_mb is not None and file_size_mb >= DOCLING_FAST_THRESHOLD_MB
        )
        use_fast_mode = force_fast_mode or (auto_fast_for_large and is_large_file)

        # Table extraction is accurate but expensive. In fast mode we disable it.
        use_table_structure = table_structure_enabled and not use_fast_mode
        pipeline_options.do_table_structure = use_table_structure
        if use_table_structure:
            pipeline_options.table_structure_options = TableStructureOptions(
                do_cell_matching=True
            )

        # Enrichments: disable all — not needed for text-based RAG
        pipeline_options.do_picture_classification = False
        pipeline_options.do_picture_description = False
        pipeline_options.do_code_enrichment = False
        pipeline_options.do_formula_enrichment = False

        # Image generation: disable — we only need text output
        pipeline_options.generate_page_images = False
        pipeline_options.generate_picture_images = False
        pipeline_options.generate_parsed_pages = False

        # CPU acceleration: configurable thread count for container tuning
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=DOCLING_NUM_THREADS,
            device=AcceleratorDevice.CPU,
        )

        logger.info(
            "Document %s parse config: fast_mode=%s auto_fast=%s file_size_mb=%s "
            "table_structure=%s threads=%d",
            doc_id if doc_id is not None else "?",
            force_fast_mode,
            auto_fast_for_large,
            round(file_size_mb, 2) if file_size_mb is not None else "unknown",
            use_table_structure,
            DOCLING_NUM_THREADS,
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        result = converter.convert(pdf_path)
        doc = result.document

        # Use default HybridChunker tokenizer (sentence-transformers/all-MiniLM-L6-v2)
        # This is downloaded once and cached in ~/.cache/huggingface inside the container.
        # It is 80 MB and significantly smaller than BAAI/bge-small-en-v1.5 (130 MB).
        # To pre-warm the cache, run: docker exec ftias-backend python /app/prewarm_docling.py
        chunker = HybridChunker(max_tokens=512)
        chunks_iter = chunker.chunk(doc)

        chunks = []
        for chunk in chunks_iter:
            # Extract page numbers from chunk metadata
            pages = set()
            if hasattr(chunk, "meta") and chunk.meta:
                for item in getattr(chunk.meta, "doc_items", []):
                    for prov in getattr(item, "prov", []):
                        page = getattr(prov, "page_no", None)
                        if page is not None:
                            pages.add(page)

            # Extract section heading
            section_title = None
            if hasattr(chunk, "meta") and chunk.meta:
                headings = getattr(chunk.meta, "headings", None)
                if headings:
                    section_title = " > ".join(headings)

            text_content = chunk.text.strip()
            if not text_content:
                continue

            for text_piece in _split_long_text(text_content, DOCLING_MAX_CHUNK_CHARS):
                chunks.append(
                    {
                        "text": text_piece,
                        "page_numbers": (
                            "-".join(str(p) for p in sorted(pages)) if pages else None
                        ),
                        "section_title": section_title,
                    }
                )

        total_pages = None
        pages_obj = getattr(doc, "pages", None)
        if pages_obj is not None:
            try:
                total_pages = len(pages_obj)
            except TypeError:
                total_pages = None

        return chunks, total_pages

    except Exception as exc:
        logger.error("Docling parsing failed: %s", exc)
        raise RuntimeError(f"PDF parsing failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

def _process_document_upload(doc_id: int, pdf_path: str):
    """
    Parse, chunk, embed and persist a document in a background worker.
    This keeps the upload HTTP request fast and avoids client-side timeouts.
    """
    started = time.monotonic()
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error("Document %d not found for background processing", doc_id)
            return

        chunks_data, total_pages = parse_and_chunk_pdf(
            pdf_path=pdf_path,
            file_size_bytes=doc.file_size_bytes,
            doc_id=doc_id,
        )
        logger.info(
            "Document %d chunking complete: pages=%s chunks=%d",
            doc_id,
            total_pages,
            len(chunks_data),
        )

        embeddings: List[Optional[List[float]]] = [None] * len(chunks_data)
        chunk_texts = [chunk["text"] for chunk in chunks_data]

        total_batches = (
            (len(chunk_texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
            if chunk_texts
            else 0
        )
        for batch_num, start in enumerate(
            range(0, len(chunk_texts), EMBEDDING_BATCH_SIZE),
            start=1,
        ):
            batch = chunk_texts[start : start + EMBEDDING_BATCH_SIZE]
            if batch_num == 1 or batch_num == total_batches or batch_num % 10 == 0:
                logger.info(
                    "Document %d embedding progress: batch %d/%d",
                    doc_id,
                    batch_num,
                    total_batches,
                )
            try:
                batch_embeddings = embed_texts(batch)
                for idx, embedding in enumerate(batch_embeddings):
                    embeddings[start + idx] = embedding
            except Exception as batch_exc:
                logger.warning(
                    "Batch embedding failed for doc %d chunks %d-%d: %s",
                    doc_id,
                    start,
                    min(start + EMBEDDING_BATCH_SIZE - 1, len(chunk_texts) - 1),
                    batch_exc,
                )
                # Fallback to single-chunk calls so one transient error does not
                # fail the entire document.
                for idx, text_content in enumerate(batch):
                    absolute_idx = start + idx
                    try:
                        embeddings[absolute_idx] = embed_text(text_content)
                    except Exception as emb_exc:
                        logger.warning(
                            "Embedding failed for doc %d chunk %d: %s",
                            doc_id,
                            absolute_idx,
                            emb_exc,
                        )

        chunk_objects = []
        for idx, chunk_info in enumerate(chunks_data):
            chunk_objects.append(
                DocumentChunk(
                    document_id=doc_id,
                    chunk_index=idx,
                    text=chunk_info["text"],
                    page_numbers=chunk_info.get("page_numbers"),
                    section_title=chunk_info.get("section_title"),
                    embedding=embeddings[idx],
                )
            )

        batch_size = 100
        for i in range(0, len(chunk_objects), batch_size):
            db.bulk_save_objects(chunk_objects[i : i + batch_size])
            db.commit()

        doc.total_pages = total_pages
        doc.total_chunks = len(chunk_objects)
        doc.status = "ready"
        doc.error_message = None
        db.commit()

        elapsed = time.monotonic() - started
        logger.info(
            "Document %d indexed: pages=%s chunks=%d duration=%.1fs",
            doc_id,
            total_pages,
            len(chunk_objects),
            elapsed,
        )

    except Exception as exc:
        logger.exception("Document processing failed for doc %d: %s", doc_id, exc)
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "error"
                doc.error_message = str(exc)
                db.commit()
        except Exception:
            logger.exception("Failed to mark document %d as error", doc_id)
    finally:
        db.close()
        try:
            os.unlink(pdf_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# POST /api/documents/upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF document (standard, handbook, regulation).
    Docling parses it, HybridChunker splits it, OpenAI embeds each chunk,
    and the embeddings are stored in pgvector for semantic search.
    """
    _require_ai_packages()
    # Validate API key up-front so we fail fast instead of creating a stuck
    # "processing" record that will error in the background worker.
    get_openai_client()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    tmp_path = ""
    file_size = 0
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                file_size += len(chunk)
                tmp.write(chunk)
    except Exception as exc:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")
    finally:
        await file.close()

    # Create the Document record immediately so the frontend can poll status
    doc = Document(
        filename=file.filename,
        title=title or file.filename,
        doc_type=doc_type,
        description=description,
        file_size_bytes=file_size,
        status="processing",
        uploaded_by_id=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_process_document_upload, doc.id, tmp_path)

    return _doc_to_out(doc)


# ---------------------------------------------------------------------------
# GET /api/documents
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents in the library, newest first."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [_doc_to_out(d) for d in docs]


# ---------------------------------------------------------------------------
# DELETE /api/documents/{doc_id}
# ---------------------------------------------------------------------------

@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and all its chunks from the library."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    db.commit()
    return {"message": f"Document '{doc.filename}' deleted successfully."}


# ---------------------------------------------------------------------------
# POST /api/documents/query  — semantic search + LLM answer
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic search over the document library.
    1. Embed the question.
    2. Find the top-k most similar chunks via pgvector cosine distance.
    3. Pass the chunks as context to the LLM and return its answer.
    """
    _require_ai_packages()
    # Embed the question
    try:
        query_embedding = embed_text(request.question)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding failed: {exc}")

    # Vector similarity search using pgvector <=> operator (cosine distance)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = text(
        """
        SELECT
            dc.id,
            dc.text,
            dc.page_numbers,
            dc.section_title,
            d.filename,
            d.title,
            1 - (dc.embedding <=> :embedding ::vector) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.status = 'ready'
          AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> :embedding ::vector
        LIMIT :top_k
        """
    )

    rows = db.execute(
        sql,
        {"embedding": embedding_str, "top_k": request.top_k},
    ).fetchall()

    if not rows:
        return QueryResponse(
            answer=(
                "No relevant documents found in the library. "
                "Please upload some standards or handbooks first."
            ),
            sources=[],
        )

    # Build context string for the LLM
    context_parts = []
    sources = []
    for row in rows:
        source_label = (
            f"{row.title or row.filename}"
            + (f", p.{row.page_numbers}" if row.page_numbers else "")
            + (f" — {row.section_title}" if row.section_title else "")
        )
        context_parts.append(f"[{source_label}]\n{row.text}")
        sources.append(
            {
                "filename": row.filename,
                "title": row.title,
                "page_numbers": row.page_numbers,
                "section_title": row.section_title,
                "similarity": round(float(row.similarity), 4),
            }
        )

    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are an expert flight test engineer and technical analyst. "
        "Answer the user's question using ONLY the provided document excerpts. "
        "Cite the source document and page number for each key claim. "
        "If the answer is not in the excerpts, say so clearly."
    )

    user_prompt = (
        f"Question: {request.question}\n\n"
        f"Document excerpts:\n\n{context}"
    )

    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        answer = completion.choices[0].message.content
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM call failed: {exc}",
        )

    return QueryResponse(answer=answer, sources=sources)


# ---------------------------------------------------------------------------
# POST /api/documents/flight-tests/{flight_test_id}/ai-analysis
# ---------------------------------------------------------------------------

@router.post(
    "/flight-tests/{flight_test_id}/ai-analysis",
    response_model=AIAnalysisResponse,
)
def ai_analysis(
    flight_test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an AI analysis report for a flight test.

    Computes per-parameter statistics (min, max, mean, std dev, sample count),
    retrieves the most relevant document chunks from the library as context,
    and asks the LLM to produce a structured analysis report.
    """
    _require_ai_packages()
    # Fetch the flight test
    ft = db.query(FlightTest).filter(FlightTest.id == flight_test_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Flight test not found.")

    # Compute statistics per parameter
    stats_rows = (
        db.query(
            TestParameter.name,
            TestParameter.unit,
            func.min(DataPoint.value).label("min_val"),
            func.max(DataPoint.value).label("max_val"),
            func.avg(DataPoint.value).label("avg_val"),
            func.stddev(DataPoint.value).label("std_val"),
            func.count(DataPoint.id).label("sample_count"),
        )
        .join(DataPoint, DataPoint.parameter_id == TestParameter.id)
        .filter(DataPoint.flight_test_id == flight_test_id)
        .group_by(TestParameter.name, TestParameter.unit)
        .all()
    )

    if not stats_rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for this flight test. Upload a CSV first.",
        )

    # Build a compact statistics table for the prompt
    stats_lines = ["Parameter | Unit | Min | Max | Mean | Std Dev | Samples"]
    stats_lines.append("-" * 80)
    for row in stats_rows:
        stats_lines.append(
            f"{row.name} | {row.unit or '-'} | "
            f"{row.min_val:.3f} | {row.max_val:.3f} | "
            f"{row.avg_val:.3f} | "
            f"{(row.std_val or 0):.3f} | {row.sample_count}"
        )
    stats_table = "\n".join(stats_lines)

    # Retrieve relevant document context using the flight test name + parameter names
    context_text = ""
    try:
        param_names = [r.name for r in stats_rows[:5]]  # top 5 params for query
        query_str = (
            f"flight test analysis {ft.aircraft_type or ''} "
            + " ".join(param_names)
        )
        query_embedding = embed_text(query_str)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        sql = text(
            """
            SELECT dc.text, d.title, dc.page_numbers, dc.section_title
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.status = 'ready' AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> :embedding ::vector
            LIMIT 4
            """
        )
        doc_rows = db.execute(sql, {"embedding": embedding_str}).fetchall()
        if doc_rows:
            parts = []
            for r in doc_rows:
                label = (
                    f"{r.title or 'Document'}"
                    + (f", p.{r.page_numbers}" if r.page_numbers else "")
                )
                parts.append(f"[{label}]\n{r.text}")
            context_text = "\n\n---\n\n".join(parts)
    except Exception as ctx_exc:
        logger.warning("Could not retrieve document context: %s", ctx_exc)

    # Build the LLM prompt
    system_prompt = (
        "You are a senior flight test engineer. "
        "Analyse the provided flight test statistics and produce a structured report. "
        "Include: (1) Executive Summary, (2) Parameter Analysis with notable observations, "
        "(3) Potential Anomalies or Concerns, (4) Recommendations. "
        "Be concise and technical. Use the document excerpts as reference standards "
        "where relevant, citing source and page."
    )

    user_prompt = (
        f"Flight Test: {ft.test_name}\n"
        f"Aircraft: {ft.aircraft_type or 'Not specified'}\n"
        f"Test Date: {ft.test_date.strftime('%Y-%m-%d') if ft.test_date else 'Not specified'}\n"
        f"Description: {ft.description or 'None'}\n\n"
        f"Parameter Statistics:\n{stats_table}"
    )

    if context_text:
        user_prompt += f"\n\nReference Document Excerpts:\n\n{context_text}"

    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        analysis_text = completion.choices[0].message.content
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM analysis failed: {exc}",
        )

    return AIAnalysisResponse(
        analysis=analysis_text,
        flight_test_name=ft.test_name,
        parameters_analysed=len(stats_rows),
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        title=doc.title,
        doc_type=doc.doc_type,
        description=doc.description,
        total_pages=doc.total_pages,
        total_chunks=doc.total_chunks,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        error_message=doc.error_message,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )
