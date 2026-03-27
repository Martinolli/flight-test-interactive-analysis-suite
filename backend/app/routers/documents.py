"""
FTIAS Backend - Documents Router
RAG pipeline: ingest PDF standards/handbooks with Docling,
embed with OpenAI text-embedding-3-small, store in pgvector,
and answer questions with the built-in LLM.
"""

import logging
import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import DataPoint, Document, DocumentChunk, FlightTest, TestParameter, User

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# OpenAI client (reads OPENAI_API_KEY from environment)
# ---------------------------------------------------------------------------
_openai_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY is not configured. "
                       "Add it to your .env file to enable AI features.",
            )
        _openai_client = OpenAI(api_key=api_key)
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


# ---------------------------------------------------------------------------
# Helper: parse and chunk a PDF with Docling
# ---------------------------------------------------------------------------

def parse_and_chunk_pdf(pdf_path: str) -> List[dict]:
    """
    Use Docling to parse a PDF and return a list of chunk dicts:
      { text, page_numbers, section_title }

    Docling's HybridChunker respects section boundaries and keeps
    tables intact as single chunks — critical for standards/handbooks.
    """
    try:
        from docling.document_converter import DocumentConverter
        from docling_core.transforms.chunker.hybrid_chunker import HybridChunker

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        doc = result.document

        chunker = HybridChunker(tokenizer="BAAI/bge-small-en-v1.5", max_tokens=512)
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

            chunks.append(
                {
                    "text": text_content,
                    "page_numbers": (
                        "-".join(str(p) for p in sorted(pages)) if pages else None
                    ),
                    "section_title": section_title,
                }
            )

        return chunks

    except Exception as exc:
        logger.error("Docling parsing failed: %s", exc)
        raise RuntimeError(f"PDF parsing failed: {exc}") from exc


# ---------------------------------------------------------------------------
# POST /api/documents/upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=DocumentOut)
async def upload_document(
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
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    file_size = len(content)

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

    # Write to a temp file for Docling
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Parse with Docling
        chunks_data = parse_and_chunk_pdf(tmp_path)

        # Embed and persist each chunk
        chunk_objects = []
        for idx, chunk_info in enumerate(chunks_data):
            try:
                embedding = embed_text(chunk_info["text"])
            except Exception as emb_exc:
                logger.warning("Embedding failed for chunk %d: %s", idx, emb_exc)
                embedding = None

            chunk_objects.append(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    text=chunk_info["text"],
                    page_numbers=chunk_info.get("page_numbers"),
                    section_title=chunk_info.get("section_title"),
                    embedding=embedding,
                )
            )

        # Batch insert chunks
        BATCH = 100
        for i in range(0, len(chunk_objects), BATCH):
            db.bulk_save_objects(chunk_objects[i : i + BATCH])
            db.commit()

        # Update document metadata
        doc.total_chunks = len(chunk_objects)
        doc.status = "ready"
        db.commit()
        db.refresh(doc)

    except Exception as exc:
        logger.error("Document processing failed for doc %d: %s", doc.id, exc)
        doc.status = "error"
        doc.error_message = str(exc)
        db.commit()
        db.refresh(doc)
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {exc}",
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

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
