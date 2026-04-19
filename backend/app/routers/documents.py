"""
FTIAS Backend - Documents Router
RAG pipeline: ingest PDF standards/handbooks with Docling,
embed with OpenAI text-embedding-3-small, store in pgvector,
and answer questions with the built-in LLM.
"""

import logging
import os
import re
import tempfile
import time
import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

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

from app.analysis import (
    build_deterministic_buffet_vibration_section as _build_deterministic_buffet_vibration_section_impl,
    build_deterministic_landing_section as _build_deterministic_landing_section_impl,
    build_deterministic_performance_section as _build_deterministic_performance_section_impl,
    build_deterministic_takeoff_section as _build_deterministic_takeoff_section_impl,
    compute_buffet_vibration_metrics as _compute_buffet_vibration_metrics_impl,
    compute_landing_metrics as _compute_landing_metrics_impl,
    compute_performance_metrics as _compute_performance_metrics_impl,
    compute_takeoff_metrics as _compute_takeoff_metrics_impl,
)
from app.analysis_modes import (
    AnalysisModeDefinition,
    analysis_mode_authority,
    analysis_mode_status,
    get_analysis_mode_definition,
    list_analysis_modes,
    resolve_analysis_mode,
)
from app.auth import get_current_user
from app.capabilities import (
    CapabilityAuthority,
    CapabilityEvaluation,
    CapabilityImplementationStatus,
    CapabilityOutcome,
    evaluate_capability_request,
)
from app.database import SessionLocal, get_db
from app.models import (
    AnalysisJob,
    DataPoint,
    DatasetVersion,
    Document,
    DocumentChunk,
    FlightTest,
    TestParameter,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# OpenAI client (reads OPENAI_API_KEY from environment)
# ---------------------------------------------------------------------------
_openai_client = None
EMBEDDING_BATCH_SIZE = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")))
DOCLING_NUM_THREADS = max(1, int(os.getenv("DOCLING_NUM_THREADS", "4")))
DOCLING_FAST_THRESHOLD_MB = max(1, int(os.getenv("DOCLING_FAST_THRESHOLD_MB", "25")))
DOCLING_MAX_CHUNK_CHARS = max(0, int(os.getenv("DOCLING_MAX_CHUNK_CHARS", "5000")))
QUERY_TOP_K_DEFAULT = max(1, min(20, int(os.getenv("QUERY_TOP_K_DEFAULT", "8"))))
QUERY_VECTOR_CANDIDATES = max(
    QUERY_TOP_K_DEFAULT, min(80, int(os.getenv("QUERY_VECTOR_CANDIDATES", "30")))
)
QUERY_LEXICAL_CANDIDATES = max(
    QUERY_TOP_K_DEFAULT, min(80, int(os.getenv("QUERY_LEXICAL_CANDIDATES", "20")))
)
QUERY_CONTEXT_LIMIT = max(
    QUERY_TOP_K_DEFAULT, min(20, int(os.getenv("QUERY_CONTEXT_LIMIT", "12")))
)
QUERY_MIN_UNIQUE_DOCUMENTS = max(
    1, min(QUERY_CONTEXT_LIMIT, int(os.getenv("QUERY_MIN_UNIQUE_DOCUMENTS", "3")))
)
QUERY_MAX_CHUNKS_PER_DOCUMENT = max(
    1, min(QUERY_CONTEXT_LIMIT, int(os.getenv("QUERY_MAX_CHUNKS_PER_DOCUMENT", "3")))
)
QUERY_MAX_TOKENS = max(512, min(4096, int(os.getenv("QUERY_MAX_TOKENS", "1800"))))
QUERY_TEMPERATURE = max(0.0, min(1.0, float(os.getenv("QUERY_TEMPERATURE", "0.1"))))
QUERY_MODEL = os.getenv("QUERY_LLM_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini")
QUERY_MIN_CITATION_DENSITY = max(
    0.0, min(1.0, float(os.getenv("QUERY_MIN_CITATION_DENSITY", "0.6")))
)
QUERY_WARNING_CITATION_DENSITY = max(
    0.0,
    min(
        1.0,
        float(
            os.getenv(
                "QUERY_WARNING_CITATION_DENSITY",
                str(max(0.35, QUERY_MIN_CITATION_DENSITY - 0.2)),
            )
        ),
    ),
)
QUERY_STRICT_CITATIONS = _env_flag("QUERY_STRICT_CITATIONS", True)


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
    top_k: int = QUERY_TOP_K_DEFAULT
    flight_test_id: Optional[int] = None  # optional context filter


class QueryCoverage(BaseModel):
    citation_density: float
    warning_threshold: float
    repair_threshold: float
    has_inline_citations: bool
    retrieved_sources_count: int
    cited_sources_count: int
    unique_documents_retrieved: int
    unique_documents_cited: int


class QueryRetrievalMetadata(BaseModel):
    requested_top_k: int
    context_limit: int
    vector_candidates: int
    lexical_candidates: int
    min_unique_documents: int
    max_chunks_per_document: int


class QueryResponse(BaseModel):
    answer: str
    summary: Optional[str] = None
    answer_type: str = "technical_explanation"
    technical_scope: str = "standards_query"
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    calculation_notes: List[str] = Field(default_factory=list)
    recommended_next_queries: List[str] = Field(default_factory=list)
    sources: List[dict]
    warnings: List[str] = Field(default_factory=list)
    coverage: QueryCoverage
    retrieval_metadata: QueryRetrievalMetadata


class AIAnalysisResponse(BaseModel):
    analysis: str
    flight_test_name: str
    analysis_mode: str = "takeoff"
    capability_key: Optional[str] = None
    dataset_version_id: Optional[int] = None
    parameters_analysed: int
    analysis_job_id: int
    model_name: str
    model_version: Optional[str] = None
    output_sha256: str
    created_at: str
    retrieved_source_ids: List[str] = Field(default_factory=list)
    retrieved_sources_snapshot: List[dict] = Field(default_factory=list)


class AnalysisJobResponse(BaseModel):
    id: int
    flight_test_id: int
    flight_test_name: str
    analysis_mode: str = "takeoff"
    capability_key: Optional[str] = None
    dataset_version_id: Optional[int] = None
    parameters_analysed: int
    status: str
    model_name: str
    model_version: Optional[str] = None
    prompt_text: str
    analysis: str
    output_sha256: str
    created_at: str
    updated_at: Optional[str] = None
    retrieved_source_ids: List[str] = Field(default_factory=list)
    retrieved_sources_snapshot: List[dict] = Field(default_factory=list)
    parameter_stats_snapshot: List[dict] = Field(default_factory=list)


class AnalysisModeOut(BaseModel):
    key: str
    label: str
    description: str
    capability_key: str
    capability_status: str
    authority: str
    default: bool


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


def _extract_used_source_ids(answer: str) -> List[str]:
    """Extract source IDs like S1/S2 from inline citations or USED_SOURCES footer."""
    inline_ids = set(re.findall(r"\[(S\d+)\]", answer))
    if inline_ids:
        return sorted(inline_ids, key=lambda x: int(x[1:]) if x[1:].isdigit() else 10_000)
    footer_match = re.search(r"(?im)^USED_SOURCES:\s*(.+)$", answer)
    footer_ids = set()
    if footer_match:
        footer_ids.update(re.findall(r"(S\d+)", footer_match.group(1)))
    return sorted(footer_ids, key=lambda x: int(x[1:]) if x[1:].isdigit() else 10_000)


def _extract_inline_source_ids(answer: str) -> List[str]:
    """Extract source IDs from inline citations only (strict mode)."""
    ids = set(re.findall(r"\[(S\d+)\]", answer))
    return sorted(ids, key=lambda x: int(x[1:]) if x[1:].isdigit() else 10_000)


def _strip_used_sources_footer(answer: str) -> str:
    return re.sub(r"(?im)^USED_SOURCES:\s*.*$", "", answer or "").strip()


def _extract_unknown_inline_source_ids(answer: str, allowed_source_ids: set[str]) -> List[str]:
    inline_ids = _extract_inline_source_ids(answer)
    return [source_id for source_id in inline_ids if source_id not in allowed_source_ids]


def _sanitize_invalid_inline_citations(answer: str, allowed_source_ids: set[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        source_id = match.group(1)
        return match.group(0) if source_id in allowed_source_ids else ""

    sanitized = re.sub(r"\[(S\d+)\]", _replace, answer or "")
    sanitized = re.sub(r" {2,}", " ", sanitized)
    return sanitized.strip()


def _is_brief_request(question: str) -> bool:
    q = (question or "").lower()
    return any(
        key in q
        for key in (
            "succinct",
            "concise",
            "brief",
            "short answer",
            "short summary",
            "preliminar",
            "preliminary",
        )
    )


def _is_risk_assessment_request(question: str) -> bool:
    q = (question or "").lower()
    if "risk assessment" in q:
        return True
    if "hazard" in q and ("likelihood" in q or "severity" in q):
        return True
    if "likelihood and severity" in q:
        return True
    return False


def _build_query_source_legend(sources: List[dict]) -> str:
    lines: List[str] = []
    for source in sources:
        source_id = source.get("source_id", "")
        label = (
            f"{source.get('title') or source.get('filename')}"
            + (f", p.{source.get('page_numbers')}" if source.get("page_numbers") else "")
            + (f" — {source.get('section_title')}" if source.get("section_title") else "")
        )
        lines.append(f"- {source_id}: {label}")
    return "\n".join(lines)


def _repair_query_answer_citations(
    *,
    client,
    question: str,
    answer: str,
    sources: List[dict],
    is_brief: bool,
    is_risk_assessment: bool,
) -> str:
    source_legend = _build_query_source_legend(sources)
    format_instructions = (
        "- Keep it concise (<= 220 words) with dense technical content.\n"
        if is_brief
        else "- Keep specialist depth and avoid generic phrasing.\n"
    )
    if is_risk_assessment:
        format_instructions += (
            "- Use this structure:\n"
            "  1) Assumptions (short bullets)\n"
            "  2) Risk Matrix table with columns:\n"
            "     Hazard | Likelihood (qualitative) | Severity (qualitative) | Scenario | Mitigation | Residual Risk\n"
            "  3) Go/No-Go gates (short bullets)\n"
        )

    repair_system = (
        "You are a technical editor for flight test documentation. "
        "Revise the answer for citation integrity and specialist tone only. "
        "Every substantive claim should carry at least one inline [Sx] citation. "
        "Use ONLY source IDs present in the Source ID legend. "
        "Do not invent new source IDs. "
        "Do not output USED_SOURCES footer. "
        "Do not use LaTeX delimiters ($$, \\(...\\), \\[...\\]); use plain-text equations."
    )
    repair_user = (
        f"Question:\n{question}\n\n"
        f"Source ID legend:\n{source_legend}\n\n"
        "Formatting requirements:\n"
        f"{format_instructions}\n"
        f"Current answer to revise:\n{answer}"
    )

    completion = client.chat.completions.create(
        model=QUERY_MODEL,
        messages=[
            {"role": "system", "content": repair_system},
            {"role": "user", "content": repair_user},
        ],
        temperature=0.0,
        max_tokens=QUERY_MAX_TOKENS,
    )
    return _strip_used_sources_footer(completion.choices[0].message.content or "")


def _extract_standards_cross_check_section(text_content: str) -> str:
    """Extract Standards Cross-Check section body for citation-density validation."""
    pattern = re.compile(
        r"(?is)"
        r"(?:^\s*\(?2\)?\s*[).:-]?\s*Standards Cross-Check\s*$|^\s*Standards Cross-Check\s*$)"
        r"(.*?)"
        r"(?=^\s*\(?3\)?\s*[).:-]?\s*Risks/Assumptions\s*$|^\s*Risks/Assumptions\s*$|\Z)",
        flags=re.MULTILINE,
    )
    match = pattern.search(text_content or "")
    if match:
        return match.group(1).strip()
    return ""


def _citation_density(text_content: str) -> float:
    """Return fraction of substantive sentences containing at least one [Sx] citation."""
    if not text_content:
        return 1.0
    raw_sentences = re.split(r"(?<=[.!?])\s+", text_content)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) >= 25]
    if not sentences:
        return 1.0
    cited = sum(1 for s in sentences if re.search(r"\[S\d+\]", s))
    return cited / len(sentences)


def _query_citation_density(answer: str) -> float:
    """
    Citation density tuned for user-facing query answers.
    Ignores structural markdown lines (headings/tables/list wrappers) to avoid false warnings.
    """
    if not answer:
        return 1.0

    candidate_lines: List[str] = []
    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if len(line) < 35:
            continue
        if line.startswith("#"):
            continue
        if line.startswith(("- ", "* ", "+ ")):
            continue
        if re.match(r"^\d+[).]\s+", line):
            continue
        if "|" in line:
            continue
        if not re.search(r"[A-Za-z]", line):
            continue
        candidate_lines.append(line)

    if not candidate_lines:
        return _citation_density(answer)

    cited = sum(1 for line in candidate_lines if re.search(r"\[S\d+\]", line))
    return cited / len(candidate_lines)


def _extract_summary(answer: str) -> Optional[str]:
    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith(("- ", "* ", "+ ")):
            continue
        if re.match(r"^\d+[).]\s+", line):
            continue
        if "|" in line:
            continue
        return line[:420]
    return None


def _extract_markdown_section_items(
    answer: str,
    heading_keywords: list[str],
    *,
    max_items: int = 6,
) -> List[str]:
    lines = (answer or "").splitlines()
    if not lines:
        return []

    heading_index = -1
    keywords = [k.lower() for k in heading_keywords]
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip().lower()
        if not line:
            continue
        cleaned = line.lstrip("#").strip()
        if any(k in cleaned for k in keywords):
            heading_index = idx
            break

    if heading_index < 0:
        return []

    items: List[str] = []
    for raw_line in lines[heading_index + 1:]:
        line = raw_line.strip()
        if not line:
            if items:
                break
            continue
        normalized = line.lower().lstrip("#").strip()
        if (
            line.startswith("#")
            or re.match(r"^\d+[).:-]\s+\w+", line)
            or normalized.endswith(":")
        ):
            # stop at the next section-like heading after collecting something
            if items:
                break
            continue

        item = re.sub(r"^[-*+]\s*", "", line)
        item = re.sub(r"^\d+[).]\s*", "", item).strip()
        if len(item) < 8:
            continue
        items.append(item[:240])
        if len(items) >= max_items:
            break
    return items


def _extract_calculation_notes(answer: str, max_items: int = 6) -> List[str]:
    notes: List[str] = []
    for raw_line in (answer or "").splitlines():
        line = raw_line.strip()
        if len(line) < 12:
            continue
        if "|" in line:
            continue
        lowered = line.lower()
        if (
            "=" in line
            or "formula" in lowered
            or "equation" in lowered
            or "calculate" in lowered
            or "computed" in lowered
        ):
            notes.append(line[:240])
        if len(notes) >= max_items:
            break
    return notes


def _default_recommended_next_queries(
    *,
    question: str,
    has_coverage_warning: bool,
    is_risk_assessment: bool,
    answer_type: str,
) -> List[str]:
    base: List[str] = []
    if is_risk_assessment:
        base.extend(
            [
                "Refine the qualitative risk matrix with aircraft-specific operating envelope limits.",
                "List objective no-go gates with measurable pass/fail criteria for each release condition.",
            ]
        )
    if answer_type == "calculation_guidance":
        base.append(
            "Provide the exact input values available and request a step-by-step deterministic calculation."
        )
    if has_coverage_warning:
        base.append(
            "Cite the exact sections/pages that justify each high-severity risk statement."
        )
    if not base:
        base.append(
            "Request a document-by-document comparison table with citations for each conclusion."
        )
    # De-duplicate while preserving order
    deduped: List[str] = []
    for item in base:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]


def _infer_answer_type(question: str, is_risk_assessment: bool) -> str:
    q = (question or "").lower()
    if is_risk_assessment:
        return "risk_assessment"
    if any(token in q for token in ("calculate", "calculation", "distance", "performance")):
        return "calculation_guidance"
    if any(token in q for token in ("compare", "difference", "versus", "vs")):
        return "comparison"
    return "technical_explanation"


def _build_source_label(row: Any) -> str:
    return (
        f"{row.title or row.filename}"
        + (f", p.{row.page_numbers}" if row.page_numbers else "")
        + (f" — {row.section_title}" if row.section_title else "")
    )


def _retrieve_hybrid_sources(
    db: Session,
    question: str,
    requested_top_k: int,
    owner_user_id: int,
) -> tuple[list[dict], str]:
    """Hybrid retrieval (vector + lexical), returns ranked sources and context text."""
    try:
        query_embedding = embed_text(question)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding failed: {exc}")

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    vector_sql = text(
        """
        SELECT
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.text,
            dc.page_numbers,
            dc.section_title,
            d.filename,
            d.title
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.status = 'ready'
          AND d.uploaded_by_id = :owner_user_id
          AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> :embedding ::vector
        LIMIT :limit_n
        """
    )
    vector_rows = db.execute(
        vector_sql,
        {
            "embedding": embedding_str,
            "limit_n": QUERY_VECTOR_CANDIDATES,
            "owner_user_id": owner_user_id,
        },
    ).fetchall()

    lexical_rows = []
    lexical_sql = text(
        """
        SELECT
            dc.id,
            dc.document_id,
            dc.chunk_index,
            dc.text,
            dc.page_numbers,
            dc.section_title,
            d.filename,
            d.title,
            ts_rank_cd(
                to_tsvector('english', dc.text),
                websearch_to_tsquery('english', :question)
            ) AS lexical_score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.status = 'ready'
          AND d.uploaded_by_id = :owner_user_id
          AND websearch_to_tsquery('english', :question) @@ to_tsvector('english', dc.text)
        ORDER BY lexical_score DESC
        LIMIT :limit_n
        """
    )
    try:
        lexical_rows = db.execute(
            lexical_sql,
            {
                "question": question,
                "limit_n": QUERY_LEXICAL_CANDIDATES,
                "owner_user_id": owner_user_id,
            },
        ).fetchall()
    except Exception as lex_exc:
        logger.warning("Lexical retrieval fallback to vector-only: %s", lex_exc)
        lexical_rows = []

    if not vector_rows and not lexical_rows:
        return [], ""

    # Reciprocal rank fusion
    rrf_k = 60
    rrf_scores: Dict[int, float] = {}
    row_by_id: Dict[int, Any] = {}
    for rank, row in enumerate(vector_rows, start=1):
        row_by_id[row.id] = row
        rrf_scores[row.id] = rrf_scores.get(row.id, 0.0) + (1.0 / (rrf_k + rank))
    for rank, row in enumerate(lexical_rows, start=1):
        row_by_id[row.id] = row
        rrf_scores[row.id] = rrf_scores.get(row.id, 0.0) + (0.8 / (rrf_k + rank))

    ranked_rows = [row_by_id[row_id] for row_id, _ in sorted(
        rrf_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )]

    context_limit = min(max(requested_top_k, QUERY_CONTEXT_LIMIT), len(ranked_rows))
    desired_unique_docs = min(QUERY_MIN_UNIQUE_DOCUMENTS, context_limit)
    per_doc_cap = min(QUERY_MAX_CHUNKS_PER_DOCUMENT, context_limit)

    context_rows: List[Any] = []
    selected_row_ids: set[int] = set()
    doc_chunk_counts: Dict[int, int] = {}

    # Pass 1: prioritize cross-document diversity (one chunk per document).
    for row in ranked_rows:
        if len(context_rows) >= context_limit:
            break
        if row.id in selected_row_ids:
            continue
        doc_id = int(row.document_id)
        if doc_chunk_counts.get(doc_id, 0) > 0:
            continue
        context_rows.append(row)
        selected_row_ids.add(row.id)
        doc_chunk_counts[doc_id] = 1
        if len(doc_chunk_counts) >= desired_unique_docs:
            break

    # Pass 2: fill remaining slots while capping over-representation per document.
    for row in ranked_rows:
        if len(context_rows) >= context_limit:
            break
        if row.id in selected_row_ids:
            continue
        doc_id = int(row.document_id)
        if doc_chunk_counts.get(doc_id, 0) >= per_doc_cap:
            continue
        context_rows.append(row)
        selected_row_ids.add(row.id)
        doc_chunk_counts[doc_id] = doc_chunk_counts.get(doc_id, 0) + 1

    if not context_rows:
        context_rows = ranked_rows[:context_limit]

    sources: List[dict] = []
    context_parts: List[str] = []
    for idx, row in enumerate(context_rows, start=1):
        source_id = f"S{idx}"
        source_label = _build_source_label(row)
        sources.append(
            {
                "source_id": source_id,
                "filename": row.filename,
                "title": row.title,
                "page_numbers": row.page_numbers,
                "section_title": row.section_title,
                "similarity": round(rrf_scores.get(row.id, 0.0), 4),
                "text": row.text,
            }
        )
        context_parts.append(f"[{source_id}] {source_label}\n{row.text}")

    return sources, "\n\n---\n\n".join(context_parts)


def _is_certification_result_requested(text_prompt: str) -> bool:
    prompt = (text_prompt or "").lower()
    if not prompt:
        return False
    keywords = [
        "certification",
        "certified",
        "screen height",
        "balanced field",
        "corrected takeoff distance",
        "corrected landing distance",
        "regulatory takeoff distance",
        "regulatory landing distance",
    ]
    return any(keyword in prompt for keyword in keywords)


def _compute_takeoff_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    return _compute_takeoff_metrics_impl(
        db=db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        request_certification_result=request_certification_result,
    )


def _build_deterministic_takeoff_section(metrics: dict) -> str:
    return _build_deterministic_takeoff_section_impl(metrics)


def _compute_landing_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    return _compute_landing_metrics_impl(
        db=db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        request_certification_result=request_certification_result,
    )


def _build_deterministic_landing_section(metrics: dict) -> str:
    return _build_deterministic_landing_section_impl(metrics)


def _compute_performance_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    return _compute_performance_metrics_impl(
        db=db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        request_certification_result=request_certification_result,
    )


def _build_deterministic_performance_section(metrics: dict) -> str:
    return _build_deterministic_performance_section_impl(metrics)


def _compute_buffet_vibration_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    return _compute_buffet_vibration_metrics_impl(
        db=db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        request_certification_result=request_certification_result,
    )


def _build_deterministic_buffet_vibration_section(metrics: dict) -> str:
    return _build_deterministic_buffet_vibration_section_impl(metrics)


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
    parse_chunk_duration_s = 0.0
    embed_duration_s = 0.0
    persist_duration_s = 0.0
    finalize_duration_s = 0.0
    total_batches = 0
    embedded_count = 0
    missing_embeddings = 0
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error("Document %d not found for background processing", doc_id)
            return

        parse_chunk_started = time.monotonic()
        chunks_data, total_pages = parse_and_chunk_pdf(
            pdf_path=pdf_path,
            file_size_bytes=doc.file_size_bytes,
            doc_id=doc_id,
        )
        parse_chunk_duration_s = time.monotonic() - parse_chunk_started
        logger.info(
            "Document %d chunking complete: pages=%s chunks=%d duration=%.2fs",
            doc_id,
            total_pages,
            len(chunks_data),
            parse_chunk_duration_s,
        )

        embed_started = time.monotonic()
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
        embed_duration_s = time.monotonic() - embed_started
        embedded_count = sum(1 for e in embeddings if e is not None)
        missing_embeddings = len(embeddings) - embedded_count
        logger.info(
            "Document %d embedding complete: chunks=%d embedded=%d missing=%d batches=%d duration=%.2fs",
            doc_id,
            len(chunk_texts),
            embedded_count,
            missing_embeddings,
            total_batches,
            embed_duration_s,
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

        persist_started = time.monotonic()
        batch_size = 100
        for i in range(0, len(chunk_objects), batch_size):
            db.bulk_save_objects(chunk_objects[i : i + batch_size])
            db.commit()
        persist_duration_s = time.monotonic() - persist_started

        finalize_started = time.monotonic()
        doc.total_pages = total_pages
        doc.total_chunks = len(chunk_objects)
        doc.status = "ready"
        doc.error_message = None
        db.commit()
        finalize_duration_s = time.monotonic() - finalize_started

        elapsed = time.monotonic() - started
        logger.info(
            "Document %d indexed: pages=%s chunks=%d duration=%.1fs",
            doc_id,
            total_pages,
            len(chunk_objects),
            elapsed,
        )
        logger.info(
            "Document %d ingestion timings: parse_chunk=%.2fs embed=%.2fs persist=%.2fs finalize=%.2fs total=%.2fs",
            doc_id,
            parse_chunk_duration_s,
            embed_duration_s,
            persist_duration_s,
            finalize_duration_s,
            elapsed,
        )

    except Exception as exc:
        elapsed = time.monotonic() - started
        logger.exception(
            "Document processing failed for doc %d: %s (parse_chunk=%.2fs embed=%.2fs persist=%.2fs finalize=%.2fs total=%.2fs)",
            doc_id,
            exc,
            parse_chunk_duration_s,
            embed_duration_s,
            persist_duration_s,
            finalize_duration_s,
            elapsed,
        )
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
    docs = (
        db.query(Document)
        .filter(Document.uploaded_by_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
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
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.uploaded_by_id == current_user.id)
        .first()
    )
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

    requested_top_k = max(1, min(20, request.top_k or QUERY_TOP_K_DEFAULT))

    sources, context = _retrieve_hybrid_sources(
        db=db,
        question=request.question,
        requested_top_k=requested_top_k,
        owner_user_id=current_user.id,
    )
    if not sources:
        return QueryResponse(
            answer=(
                "No relevant documents found in the library. "
                "Please upload some standards or handbooks first."
            ),
            summary="No indexed evidence was found for this query.",
            answer_type="insufficient_evidence",
            technical_scope="standards_query",
            assumptions=[],
            limitations=["No relevant source documents were retrieved."],
            calculation_notes=[],
            recommended_next_queries=[
                "Upload standards/handbooks relevant to this topic and rerun the query.",
                "Ask a narrower question including target system, test phase, and regulation family.",
            ],
            sources=[],
            warnings=["No relevant source evidence was retrieved for this query."],
            coverage=QueryCoverage(
                citation_density=0.0,
                warning_threshold=QUERY_WARNING_CITATION_DENSITY,
                repair_threshold=QUERY_MIN_CITATION_DENSITY,
                has_inline_citations=False,
                retrieved_sources_count=0,
                cited_sources_count=0,
                unique_documents_retrieved=0,
                unique_documents_cited=0,
            ),
            retrieval_metadata=QueryRetrievalMetadata(
                requested_top_k=requested_top_k,
                context_limit=QUERY_CONTEXT_LIMIT,
                vector_candidates=QUERY_VECTOR_CANDIDATES,
                lexical_candidates=QUERY_LEXICAL_CANDIDATES,
                min_unique_documents=QUERY_MIN_UNIQUE_DOCUMENTS,
                max_chunks_per_document=QUERY_MAX_CHUNKS_PER_DOCUMENT,
            ),
        )

    brief_request = _is_brief_request(request.question)
    risk_request = _is_risk_assessment_request(request.question)
    answer_type = _infer_answer_type(request.question, risk_request)
    source_legend = _build_query_source_legend(sources)

    format_instructions = (
        "- Keep the response succinct (max 220 words), but technically specific.\n"
        if brief_request
        else "- Provide specialist depth with concrete engineering detail.\n"
    )
    if risk_request:
        format_instructions += (
            "- Use this structure:\n"
            "  1) Assumptions\n"
            "  2) Risk Matrix table with columns: Hazard | Likelihood | Severity | Scenario | Mitigation | Residual Risk\n"
            "  3) Go/No-Go gates\n"
        )

    system_prompt = (
        "You are a senior flight-test engineer writing for specialist readers. "
        "Use ONLY the provided source excerpts. "
        "Every substantive technical claim must include at least one inline [Sx] citation. "
        "Use only source IDs present in the Source ID legend. "
        "Do not invent citations, standards, equations, or numeric values. "
        "If key inputs are missing, explicitly state what is missing and why it blocks a precise answer. "
        "Do not output a USED_SOURCES footer. "
        "Use plain-text equations and markdown tables where helpful."
    )

    user_prompt = (
        f"Question:\n{request.question}\n\n"
        "Source ID legend:\n"
        f"{source_legend}\n\n"
        "Formatting requirements:\n"
        f"{format_instructions}"
        "- Keep citations tightly mapped to claims.\n\n"
        f"Source excerpts:\n\n{context}"
    )

    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model=QUERY_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=QUERY_TEMPERATURE,
            max_tokens=QUERY_MAX_TOKENS,
        )
        answer = completion.choices[0].message.content or ""
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM call failed: {exc}",
        )

    answer = _strip_used_sources_footer(answer)
    allowed_source_ids = {str(s.get("source_id")) for s in sources if s.get("source_id")}
    warnings: List[str] = []

    inline_source_ids = _extract_inline_source_ids(answer)
    unknown_source_ids = _extract_unknown_inline_source_ids(answer, allowed_source_ids)
    citation_density = _query_citation_density(answer)
    warning_citation_density = citation_density
    retrieved_unique_doc_labels = {
        str((s.get("title") or s.get("filename") or "")).strip()
        for s in sources
        if (s.get("title") or s.get("filename"))
    }

    requires_repair = (
        bool(unknown_source_ids)
        or (QUERY_STRICT_CITATIONS and not inline_source_ids)
        or (bool(sources) and citation_density < QUERY_MIN_CITATION_DENSITY)
    )
    if requires_repair:
        try:
            repaired = _repair_query_answer_citations(
                client=client,
                question=request.question,
                answer=answer,
                sources=sources,
                is_brief=brief_request,
                is_risk_assessment=risk_request,
            )
            if repaired:
                answer = repaired
        except Exception as repair_exc:
            logger.warning("Query answer citation repair skipped due to LLM error: %s", repair_exc)

        answer = _sanitize_invalid_inline_citations(answer, allowed_source_ids)
        inline_source_ids = _extract_inline_source_ids(answer)
        unknown_source_ids = _extract_unknown_inline_source_ids(answer, allowed_source_ids)
        citation_density = _query_citation_density(answer)
        warning_citation_density = citation_density

    if unknown_source_ids:
        answer = _sanitize_invalid_inline_citations(answer, allowed_source_ids)
        warnings.append("Removed invalid source citation IDs that were not present in retrieved evidence.")
        inline_source_ids = _extract_inline_source_ids(answer)

    if QUERY_STRICT_CITATIONS and sources and not inline_source_ids:
        warnings.append(
            "Insufficient citation coverage: answer contains no valid inline [Sx] citations."
        )
    elif sources and warning_citation_density < QUERY_WARNING_CITATION_DENSITY:
        warnings.append(
            "Insufficient citation coverage: some technical statements may not be fully referenced."
        )

    retrieved_sources_count = len(sources)

    used_source_ids = inline_source_ids
    if not QUERY_STRICT_CITATIONS:
        used_source_ids = _extract_used_source_ids(answer) or inline_source_ids

    if used_source_ids:
        cited = [s for s in sources if s.get("source_id") in set(used_source_ids)]
        if cited:
            sources = cited

    if (
        retrieved_unique_doc_labels
        and len(retrieved_unique_doc_labels) < QUERY_MIN_UNIQUE_DOCUMENTS
    ):
        warnings.append(
            "Retrieved evidence is concentrated in too few documents for this query. "
            "Consider more specific terms or additional reference material."
        )

    assumptions = _extract_markdown_section_items(answer, ["assumptions"])
    limitations = _extract_markdown_section_items(answer, ["limitations", "constraints", "gaps"])
    calculation_notes = _extract_calculation_notes(answer)
    coverage_warning_present = any("citation coverage" in warning.lower() for warning in warnings)
    recommended_next_queries = _extract_markdown_section_items(
        answer,
        ["recommended next queries", "next queries", "next steps"],
        max_items=4,
    )
    if not recommended_next_queries:
        recommended_next_queries = _default_recommended_next_queries(
            question=request.question,
            has_coverage_warning=coverage_warning_present,
            is_risk_assessment=risk_request,
            answer_type=answer_type,
        )

    cited_unique_doc_labels = {
        str((s.get("title") or s.get("filename") or "")).strip()
        for s in sources
        if (s.get("title") or s.get("filename"))
    }

    response_sources = [{k: v for k, v in s.items() if k != "text"} for s in sources]
    return QueryResponse(
        answer=answer,
        summary=_extract_summary(answer),
        answer_type=answer_type,
        technical_scope="standards_query",
        assumptions=assumptions,
        limitations=limitations,
        calculation_notes=calculation_notes,
        recommended_next_queries=recommended_next_queries,
        sources=response_sources,
        warnings=warnings,
        coverage=QueryCoverage(
            citation_density=round(warning_citation_density, 3),
            warning_threshold=QUERY_WARNING_CITATION_DENSITY,
            repair_threshold=QUERY_MIN_CITATION_DENSITY,
            has_inline_citations=bool(inline_source_ids),
            retrieved_sources_count=retrieved_sources_count,
            cited_sources_count=len(response_sources),
            unique_documents_retrieved=len(retrieved_unique_doc_labels),
            unique_documents_cited=len(cited_unique_doc_labels),
        ),
        retrieval_metadata=QueryRetrievalMetadata(
            requested_top_k=requested_top_k,
            context_limit=QUERY_CONTEXT_LIMIT,
            vector_candidates=QUERY_VECTOR_CANDIDATES,
            lexical_candidates=QUERY_LEXICAL_CANDIDATES,
            min_unique_documents=QUERY_MIN_UNIQUE_DOCUMENTS,
            max_chunks_per_document=QUERY_MAX_CHUNKS_PER_DOCUMENT,
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/documents/analysis-modes
# ---------------------------------------------------------------------------

@router.get("/analysis-modes", response_model=List[AnalysisModeOut])
def get_analysis_modes(
    _current_user: User = Depends(get_current_user),
):
    """Return available analysis modes and their capability-backed status."""
    response: List[AnalysisModeOut] = []
    for mode in list_analysis_modes():
        response.append(
            AnalysisModeOut(
                key=mode.key,
                label=mode.label,
                description=mode.description,
                capability_key=mode.capability_key,
                capability_status=analysis_mode_status(mode).value,
                authority=analysis_mode_authority(mode).value,
                default=mode.default,
            )
        )
    return response


# ---------------------------------------------------------------------------
# Analysis job helpers
# ---------------------------------------------------------------------------

def _get_accessible_flight_test(
    *,
    db: Session,
    flight_test_id: int,
    current_user: User,
) -> FlightTest:
    query = db.query(FlightTest).filter(FlightTest.id == flight_test_id)
    if not current_user.is_superuser:
        query = query.filter(FlightTest.created_by_id == current_user.id)
    flight_test = query.first()
    if not flight_test:
        raise HTTPException(status_code=404, detail="Flight test not found.")
    return flight_test


def _safe_json_load(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


_ANALYSIS_MODE_PROMPT_RE = re.compile(
    r"^\[analysis_mode:(?P<mode>[a-z_]+)\]\s*(?P<prompt>.*)$",
    flags=re.DOTALL,
)


def _encode_prompt_with_mode(user_prompt: str, analysis_mode: str) -> str:
    raw = (user_prompt or "").strip()
    return f"[analysis_mode:{analysis_mode}] {raw}".strip()


def _decode_prompt_mode(prompt_text: str) -> Tuple[Optional[str], str]:
    text = prompt_text or ""
    match = _ANALYSIS_MODE_PROMPT_RE.match(text.strip())
    if not match:
        return None, text
    return match.group("mode"), match.group("prompt")


def _build_mode_routing_section(
    *,
    mode: AnalysisModeDefinition,
    capability_eval: CapabilityEvaluation,
) -> str:
    lines = [
        "## Analysis Mode Routing",
        f"- Requested mode: **{mode.key}** ({mode.label})",
        f"- Capability key: **{capability_eval.capability_key}**",
        f"- Capability status: **{capability_eval.status.value}**",
        f"- Authority classification: **{capability_eval.authority.value}**",
        f"- Routing outcome: **{capability_eval.outcome.value}**",
    ]
    if capability_eval.reason_key:
        lines.append(f"- Rule reason key: **{capability_eval.reason_key}**")
    lines.append(f"- Routing note: {capability_eval.user_message}")
    if capability_eval.missing_required_signals:
        lines.append(
            "- Missing required signals: "
            + ", ".join(capability_eval.missing_required_signals)
        )
    if capability_eval.applicability_boundaries:
        lines.append("")
        lines.append("### Applicability Boundaries")
        for item in capability_eval.applicability_boundaries:
            lines.append(f"- {item}")
    if capability_eval.limitations:
        lines.append("")
        lines.append("### Limitations")
        for item in capability_eval.limitations:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _build_non_takeoff_deterministic_section(
    *,
    mode: AnalysisModeDefinition,
    capability_eval: CapabilityEvaluation,
) -> str:
    lines = [
        "## Deterministic Calculation (Mode Scope) [DATA]",
        (
            f"No deterministic {mode.label.lower()} calculator is executed in this release for "
            f"`analysis_mode={mode.key}`."
        ),
        f"- Outcome: **{capability_eval.outcome.value}**",
    ]
    if capability_eval.reason_key:
        lines.append(f"- Reason key: **{capability_eval.reason_key}**")
    if capability_eval.outcome == CapabilityOutcome.STANDARDS_ONLY_GUIDANCE:
        lines.append("- Behavior: standards/context guidance only (no authoritative deterministic metric).")
    elif capability_eval.outcome == CapabilityOutcome.BLOCKED:
        lines.append("- Behavior: analysis is capability-gated; deterministic result is blocked.")
    elif capability_eval.outcome == CapabilityOutcome.PARTIAL_ESTIMATE:
        lines.append("- Behavior: partial estimate only with explicit limitations.")
    else:
        lines.append("- Behavior: mode can provide narrative guidance with explicit applicability boundaries.")
    return "\n".join(lines)


def _analysis_retrieval_focus_for_mode(mode_key: str) -> str:
    focus_map = {
        "takeoff": "takeoff distance ground roll liftoff runway acceleration weight on wheels procedures certification",
        "landing": "landing distance touchdown braking deceleration runway procedures standards",
        "performance": "performance flight envelope climb cruise drag thrust standards",
        "handling_qualities": "handling qualities controllability stability pilot workload flying qualities",
        "buffet_vibration": "buffet vibration structural response instrumentation standards",
        "flutter": "flutter aeroelastic stability modal analysis safety limitations",
        "propulsion_systems": "propulsion engine performance thrust fuel system monitoring limits",
        "electrical_systems": "electrical system monitoring loads generators buses protections standards",
        "general": "flight test standards procedures engineering analysis assumptions limitations",
    }
    return focus_map.get(mode_key, focus_map["general"])


def _default_analysis_goal_for_mode(mode: AnalysisModeDefinition) -> str:
    if mode.key == "takeoff":
        return (
            "Produce a structured report with: (1) Executive Summary, "
            "(2) Parameter Analysis with notable observations, "
            "(3) Potential Anomalies or Concerns, (4) Recommendations."
        )
    if mode.key == "general":
        return (
            "Produce a structured engineering interpretation with standards cross-check, "
            "explicit assumptions, limitations, and recommended follow-up analysis."
        )
    return (
        f"Provide a mode-scoped engineering assessment for {mode.label}. "
        "Explicitly state current implementation limits, blocked conditions, and required additional data."
    )


def _capability_eval_from_deterministic_metrics(
    metrics: dict,
    mode: AnalysisModeDefinition,
) -> CapabilityEvaluation:
    outcome = metrics.get("capability_outcome") or "allow_with_limitations"
    status_value = metrics.get("capability_status")
    authority_value = metrics.get("capability_authority")
    resolved_status = analysis_mode_status(mode)
    resolved_authority = analysis_mode_authority(mode)

    if status_value in {item.value for item in CapabilityImplementationStatus}:
        resolved_status = CapabilityImplementationStatus(status_value)
    if authority_value in {item.value for item in CapabilityAuthority}:
        resolved_authority = CapabilityAuthority(authority_value)

    return CapabilityEvaluation(
        capability_key=str(metrics.get("capability_key") or mode.capability_key),
        label=mode.label,
        status=resolved_status,
        authority=resolved_authority,
        outcome=CapabilityOutcome(outcome) if outcome in {item.value for item in CapabilityOutcome} else CapabilityOutcome.ALLOW_WITH_LIMITATIONS,
        reason_key=metrics.get("capability_reason_key"),
        user_message=str(
            metrics.get("capability_user_message")
            or f"{mode.label} capability evaluation completed."
        ),
        missing_required_signals=list(metrics.get("capability_missing_signals") or []),
        applicability_boundaries=list(metrics.get("capability_applicability_boundaries") or []),
        limitations=list(metrics.get("capability_limitations") or []),
    )


def _build_mode_limited_analysis_text(
    *,
    mode: AnalysisModeDefinition,
    capability_eval: CapabilityEvaluation,
    analysis_goal: str,
    deterministic_available: bool = False,
) -> str:
    if deterministic_available:
        summary_line = (
            f"The selected analysis mode `{mode.key}` produced deterministic bounded results. "
            "This section captures applicability boundaries and follow-up guidance."
        )
    else:
        summary_line = (
            f"The selected analysis mode `{mode.key}` is currently routed as `{capability_eval.outcome.value}`. "
            "This response provides capability-aware boundaries and next-step guidance only."
        )

    lines = [
        "### Executive Summary",
        summary_line,
        "",
        "### Mode Applicability and Limits",
        f"- Capability status: **{capability_eval.status.value}**",
        f"- Authority classification: **{capability_eval.authority.value}**",
    ]
    if capability_eval.reason_key:
        lines.append(f"- Rule reason: **{capability_eval.reason_key}**")
    lines.extend(
        [
            f"- Routing message: {capability_eval.user_message}",
            "",
            "### Assumptions and Limitations",
        ]
    )
    if capability_eval.limitations:
        lines.extend([f"- {item}" for item in capability_eval.limitations])
    else:
        lines.append("- No additional limitations were provided by catalog rules.")
    lines.extend(["", "### Applicability Boundaries"])
    if capability_eval.applicability_boundaries:
        lines.extend([f"- {item}" for item in capability_eval.applicability_boundaries])
    else:
        lines.append("- Applicability boundaries are not yet defined for this mode.")
    lines.extend(
        [
            "",
            "### Recommendations",
            "- Use deterministic mode outputs as authoritative only within the stated applicability boundaries.",
            "- For unsupported domains, use standards/context guidance as advisory evidence only.",
            f"- Requested goal: {analysis_goal}",
        ]
    )
    return "\n".join(lines)


def _serialize_retrieval_snapshot(sources: List[dict], excerpt_chars: int = 320) -> List[dict]:
    snapshot: List[dict] = []
    for source in sources:
        snapshot.append(
            {
                "source_id": source.get("source_id"),
                "filename": source.get("filename"),
                "title": source.get("title"),
                "page_numbers": source.get("page_numbers"),
                "section_title": source.get("section_title"),
                "similarity": source.get("similarity"),
                "excerpt": (source.get("text") or "")[:excerpt_chars],
            }
        )
    return snapshot


def _serialize_parameter_stats_snapshot(stats_rows) -> List[dict]:
    snapshot: List[dict] = []
    for row in stats_rows:
        snapshot.append(
            {
                "name": row.name,
                "unit": row.unit,
                "min_val": float(row.min_val) if row.min_val is not None else None,
                "max_val": float(row.max_val) if row.max_val is not None else None,
                "avg_val": float(row.avg_val) if row.avg_val is not None else None,
                "std_val": float(row.std_val) if row.std_val is not None else None,
                "sample_count": int(row.sample_count) if row.sample_count is not None else 0,
            }
        )
    return snapshot


def _analysis_job_to_response(
    *,
    job: AnalysisJob,
    flight_test_name: str,
) -> AIAnalysisResponse:
    source_ids = _safe_json_load(job.retrieved_source_ids_json, [])
    if not isinstance(source_ids, list):
        source_ids = []
    retrieved_sources_snapshot = _safe_json_load(job.retrieved_sources_snapshot_json, [])
    if not isinstance(retrieved_sources_snapshot, list):
        retrieved_sources_snapshot = []
    analysis_mode, _clean_prompt = _decode_prompt_mode(job.prompt_text or "")
    selected_mode = get_analysis_mode_definition(analysis_mode) if analysis_mode else None
    if selected_mode is None:
        selected_mode = resolve_analysis_mode(None)
    return AIAnalysisResponse(
        analysis=job.analysis_text,
        flight_test_name=flight_test_name,
        analysis_mode=selected_mode.key,
        capability_key=selected_mode.capability_key,
        dataset_version_id=job.dataset_version_id,
        parameters_analysed=job.parameters_analysed,
        analysis_job_id=job.id,
        model_name=job.model_name,
        model_version=job.model_version,
        output_sha256=job.output_sha256,
        created_at=job.created_at.isoformat() if job.created_at else "",
        retrieved_source_ids=[str(item) for item in source_ids if item],
        retrieved_sources_snapshot=retrieved_sources_snapshot,
    )


def _resolve_dataset_version_for_analysis(
    *,
    db: Session,
    flight_test: FlightTest,
    requested_dataset_version_id: Optional[int],
) -> Optional[DatasetVersion]:
    if requested_dataset_version_id is not None:
        dataset_version = (
            db.query(DatasetVersion)
            .filter(
                DatasetVersion.id == requested_dataset_version_id,
                DatasetVersion.flight_test_id == flight_test.id,
            )
            .first()
        )
        if not dataset_version:
            raise HTTPException(status_code=404, detail="Dataset version not found.")
        return dataset_version

    if flight_test.active_dataset_version_id is None:
        return None

    dataset_version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.id == flight_test.active_dataset_version_id,
            DatasetVersion.flight_test_id == flight_test.id,
        )
        .first()
    )
    return dataset_version


@router.get(
    "/flight-tests/{flight_test_id}/ai-analysis/jobs/{analysis_job_id}",
    response_model=AnalysisJobResponse,
)
def get_ai_analysis_job(
    flight_test_id: int,
    analysis_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ft = _get_accessible_flight_test(
        db=db,
        flight_test_id=flight_test_id,
        current_user=current_user,
    )
    job = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.id == analysis_job_id,
            AnalysisJob.flight_test_id == ft.id,
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    if not current_user.is_superuser and job.created_by_id != current_user.id:
        raise HTTPException(status_code=404, detail="Analysis job not found.")

    retrieved_source_ids = _safe_json_load(job.retrieved_source_ids_json, [])
    if not isinstance(retrieved_source_ids, list):
        retrieved_source_ids = []
    retrieved_sources_snapshot = _safe_json_load(job.retrieved_sources_snapshot_json, [])
    if not isinstance(retrieved_sources_snapshot, list):
        retrieved_sources_snapshot = []
    parameter_stats_snapshot = _safe_json_load(job.parameter_stats_snapshot_json, [])
    if not isinstance(parameter_stats_snapshot, list):
        parameter_stats_snapshot = []
    analysis_mode, clean_prompt_text = _decode_prompt_mode(job.prompt_text or "")
    selected_mode = get_analysis_mode_definition(analysis_mode) if analysis_mode else None
    if selected_mode is None:
        selected_mode = resolve_analysis_mode(None)

    return AnalysisJobResponse(
        id=job.id,
        flight_test_id=job.flight_test_id,
        flight_test_name=ft.test_name,
        analysis_mode=selected_mode.key,
        capability_key=selected_mode.capability_key,
        dataset_version_id=job.dataset_version_id,
        parameters_analysed=job.parameters_analysed,
        status=job.status,
        model_name=job.model_name,
        model_version=job.model_version,
        prompt_text=clean_prompt_text,
        analysis=job.analysis_text,
        output_sha256=job.output_sha256,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
        retrieved_source_ids=[str(item) for item in retrieved_source_ids if item],
        retrieved_sources_snapshot=retrieved_sources_snapshot,
        parameter_stats_snapshot=parameter_stats_snapshot,
    )


# ---------------------------------------------------------------------------
# POST /api/documents/flight-tests/{flight_test_id}/ai-analysis
# ---------------------------------------------------------------------------

class AIAnalysisRequest(BaseModel):
    user_prompt: str | None = None
    dataset_version_id: Optional[int] = None
    analysis_mode: Optional[str] = None


@router.post(
    "/flight-tests/{flight_test_id}/ai-analysis",
    response_model=AIAnalysisResponse,
)
def ai_analysis(
    flight_test_id: int,
    body: AIAnalysisRequest = AIAnalysisRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an AI analysis report for a flight test.

    Computes per-parameter statistics (min, max, mean, std dev, sample count),
    retrieves the most relevant document chunks from the library as context,
    and asks the LLM to produce a structured analysis report.

    Optional body field:
    - user_prompt: Free-text analysis goal from the user (e.g. 'Analyse takeoff performance').
      When provided, this replaces the default generic analysis instruction.
    """
    _require_ai_packages()
    ft = _get_accessible_flight_test(
        db=db,
        flight_test_id=flight_test_id,
        current_user=current_user,
    )
    dataset_version = _resolve_dataset_version_for_analysis(
        db=db,
        flight_test=ft,
        requested_dataset_version_id=body.dataset_version_id,
    )
    dataset_version_id = dataset_version.id if dataset_version else None

    # Compute statistics per parameter
    stats_query = (
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
    )
    if dataset_version_id is not None:
        stats_query = stats_query.filter(
            DataPoint.dataset_version_id == dataset_version_id
        )
    stats_rows = stats_query.group_by(TestParameter.name, TestParameter.unit).all()

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

    requested_mode_key = (body.analysis_mode or "").strip().lower()
    if requested_mode_key and not get_analysis_mode_definition(requested_mode_key):
        supported = ", ".join([mode.key for mode in list_analysis_modes()])
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported analysis_mode '{requested_mode_key}'. "
                f"Supported modes: {supported}."
            ),
        )
    selected_mode = resolve_analysis_mode(requested_mode_key or None)

    # If the user supplied a specific analysis goal, use it; otherwise use the mode default.
    if body.user_prompt and body.user_prompt.strip():
        analysis_goal = body.user_prompt.strip()
    else:
        analysis_goal = _default_analysis_goal_for_mode(selected_mode)

    available_signal_names = [str(row.name) for row in stats_rows]
    mode_eval = evaluate_capability_request(
        selected_mode.capability_key,
        available_signals=available_signal_names,
        has_dataset=bool(stats_rows),
        has_standards_context=True,
    )
    mode_routing_section = _build_mode_routing_section(
        mode=selected_mode,
        capability_eval=mode_eval,
    )

    analysis_model = os.getenv("ANALYSIS_LLM_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    analysis_temperature = max(0.0, min(1.0, float(os.getenv("ANALYSIS_TEMPERATURE", "0.2"))))
    analysis_max_tokens = max(1200, min(4096, int(os.getenv("ANALYSIS_MAX_TOKENS", "2600"))))

    deterministic_section = ""
    llm_analysis_text = ""
    persisted_prompt_text = ""
    sources: List[dict] = []
    cited_sources: List[dict] = []
    context_text = ""
    run_llm = False

    certification_requested = _is_certification_result_requested(analysis_goal)
    deterministic_metrics = None

    if selected_mode.key == "takeoff":
        deterministic_metrics = _compute_takeoff_metrics(
            db=db,
            flight_test_id=flight_test_id,
            dataset_version_id=dataset_version_id,
            request_certification_result=certification_requested,
        )
        deterministic_section = _build_deterministic_takeoff_section(deterministic_metrics)
        run_llm = True
    elif selected_mode.key == "landing":
        deterministic_metrics = _compute_landing_metrics(
            db=db,
            flight_test_id=flight_test_id,
            dataset_version_id=dataset_version_id,
            request_certification_result=certification_requested,
        )
        deterministic_section = _build_deterministic_landing_section(deterministic_metrics)
        run_llm = False
    elif selected_mode.key == "performance":
        deterministic_metrics = _compute_performance_metrics(
            db=db,
            flight_test_id=flight_test_id,
            dataset_version_id=dataset_version_id,
            request_certification_result=certification_requested,
        )
        deterministic_section = _build_deterministic_performance_section(deterministic_metrics)
        run_llm = False
    elif selected_mode.key == "buffet_vibration":
        deterministic_metrics = _compute_buffet_vibration_metrics(
            db=db,
            flight_test_id=flight_test_id,
            dataset_version_id=dataset_version_id,
            request_certification_result=certification_requested,
        )
        deterministic_section = _build_deterministic_buffet_vibration_section(deterministic_metrics)
        run_llm = False
    else:
        deterministic_section = _build_non_takeoff_deterministic_section(
            mode=selected_mode,
            capability_eval=mode_eval,
        )
        # Only "general" currently runs routed LLM guidance path.
        run_llm = selected_mode.key == "general"

    if deterministic_metrics is not None:
        mode_eval = _capability_eval_from_deterministic_metrics(
            deterministic_metrics,
            selected_mode,
        )
        mode_routing_section = _build_mode_routing_section(
            mode=selected_mode,
            capability_eval=mode_eval,
        )

    if run_llm:
        param_names = [r.name for r in stats_rows[:10]]
        retrieval_focus = _analysis_retrieval_focus_for_mode(selected_mode.key)
        retrieval_question = (
            f"{analysis_goal}\n"
            f"Focus terms: {retrieval_focus}\n"
            f"Aircraft: {ft.aircraft_type or ''}\n"
            f"Flight test parameter names: {'; '.join(param_names)}"
        )
        sources, context_text = _retrieve_hybrid_sources(
            db=db,
            question=retrieval_question,
            requested_top_k=8,
            owner_user_id=current_user.id,
        )

        if selected_mode.key == "takeoff":
            system_prompt = (
                "You are a senior flight test engineer. "
                "A deterministic takeoff section has already been computed by software and must not be recalculated "
                "or numerically modified. "
                "Your task is to produce interpretation and standards cross-check only, using ONLY provided source excerpts. "
                "Cite standards claims with [Sx]. For deterministic data references, use [DATA]. "
                "Do not emit USED_SOURCES footer."
            )
            llm_user_prompt = (
                f"Flight Test: {ft.test_name}\n"
                f"Aircraft: {ft.aircraft_type or 'Not specified'}\n"
                f"Test Date: {ft.test_date.strftime('%Y-%m-%d') if ft.test_date else 'Not specified'}\n"
                f"Description: {ft.description or 'None'}\n\n"
                f"Analysis Goal: {analysis_goal}\n\n"
                f"Parameter Statistics:\n{stats_table}\n\n"
                "Mode Routing Section (authoritative):\n"
                f"{mode_routing_section}\n\n"
                "Deterministic Section (already computed and authoritative):\n"
                f"{deterministic_section}\n\n"
                "Requirements:\n"
                "- Do not recompute or alter deterministic values.\n"
                "- Write sections: (1) Executive Summary, (2) Standards Cross-Check, "
                "(3) Risks/Assumptions, (4) Recommendations.\n"
                "- In section (2) Standards Cross-Check, each substantive sentence must include at least one inline [Sx] citation.\n"
                "- If section (4) Recommendations references standards/procedures, include [Sx] there as well.\n"
                "- If standards evidence is missing, state that explicitly.\n"
            )
        else:
            system_prompt = (
                "You are a senior flight test engineer. "
                "Respect the backend mode routing decision and capability limits exactly as provided. "
                "Do not claim deterministic computed outputs unless explicitly present in the provided deterministic section. "
                "Use standards/context guidance with inline [Sx] citations when evidence exists. "
                "Do not emit USED_SOURCES footer."
            )
            llm_user_prompt = (
                f"Flight Test: {ft.test_name}\n"
                f"Aircraft: {ft.aircraft_type or 'Not specified'}\n"
                f"Test Date: {ft.test_date.strftime('%Y-%m-%d') if ft.test_date else 'Not specified'}\n"
                f"Description: {ft.description or 'None'}\n\n"
                f"Selected Analysis Mode: {selected_mode.key} ({selected_mode.label})\n"
                f"Analysis Goal: {analysis_goal}\n\n"
                f"Parameter Statistics:\n{stats_table}\n\n"
                "Mode Routing Section (authoritative):\n"
                f"{mode_routing_section}\n\n"
                "Deterministic Section:\n"
                f"{deterministic_section}\n\n"
                "Requirements:\n"
                "- Keep capability limitations explicit and prominent.\n"
                "- Do not fabricate unsupported deterministic metrics.\n"
                "- Write sections: (1) Executive Summary, (2) Mode Applicability and Limits, "
                "(3) Standards/Context Guidance, (4) Recommendations.\n"
            )

        if context_text:
            llm_user_prompt += f"\n\nReference Document Excerpts:\n\n{context_text}"

        try:
            client = get_openai_client()
            completion = client.chat.completions.create(
                model=analysis_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": llm_user_prompt},
                ],
                temperature=analysis_temperature,
                max_tokens=analysis_max_tokens,
            )
            llm_analysis_text = completion.choices[0].message.content or ""
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"LLM analysis failed: {exc}",
            )

        llm_analysis_text = re.sub(r"(?im)^USED_SOURCES:\s*.*$", "", llm_analysis_text).strip()

        # Optional strict citation-density repair for takeoff standards cross-check.
        if selected_mode.key == "takeoff":
            min_citation_density = max(
                0.0, min(1.0, float(os.getenv("ANALYSIS_MIN_CITATION_DENSITY", "0.75")))
            )
            standards_section = _extract_standards_cross_check_section(llm_analysis_text)
            standards_density = _citation_density(standards_section)
            if sources and standards_section and standards_density < min_citation_density:
                source_lines: List[str] = []
                for s in sources:
                    ref_label = (
                        f"{s.get('title') or s.get('filename')}"
                        + (f", p.{s.get('page_numbers')}" if s.get("page_numbers") else "")
                        + (f" — {s.get('section_title')}" if s.get("section_title") else "")
                    )
                    source_lines.append(f"- {s.get('source_id')}: {ref_label}")
                source_legend = "\n".join(source_lines)
                repair_system_prompt = (
                    "You are a technical editor. Revise the analysis to improve citation coverage only. "
                    "Preserve structure, numbers, and conclusions. "
                    "For Standards Cross-Check statements, ensure each substantive sentence has an inline [Sx] citation "
                    "using only source IDs from the provided legend. "
                    "Do not add a references section. Do not emit USED_SOURCES."
                )
                repair_user_prompt = (
                    "Source ID legend:\n"
                    f"{source_legend}\n\n"
                    "Revise the analysis below for citation density compliance:\n\n"
                    f"{llm_analysis_text}"
                )
                try:
                    repaired = client.chat.completions.create(
                        model=analysis_model,
                        messages=[
                            {"role": "system", "content": repair_system_prompt},
                            {"role": "user", "content": repair_user_prompt},
                        ],
                        temperature=0.0,
                        max_tokens=analysis_max_tokens,
                    )
                    repaired_text = (repaired.choices[0].message.content or "").strip()
                    repaired_text = re.sub(r"(?im)^USED_SOURCES:\s*.*$", "", repaired_text).strip()
                    if repaired_text:
                        llm_analysis_text = repaired_text
                except Exception as repair_exc:
                    logger.warning("Citation density repair skipped due to LLM error: %s", repair_exc)

        inline_source_ids = _extract_inline_source_ids(llm_analysis_text)
        if inline_source_ids and sources:
            cited_sources = [s for s in sources if s.get("source_id") in set(inline_source_ids)]
        else:
            cited_sources = []

        final_analysis = (
            mode_routing_section.strip()
            + "\n\n"
            + deterministic_section.strip()
            + "\n\n"
            + llm_analysis_text.strip()
        )
        if cited_sources:
            refs_lines = ["", "### References"]
            for s in cited_sources:
                ref_label = (
                    f"{s.get('title') or s.get('filename')}"
                    + (f", p.{s.get('page_numbers')}" if s.get("page_numbers") else "")
                    + (f" — {s.get('section_title')}" if s.get("section_title") else "")
                )
                refs_lines.append(
                    f"- [{s['source_id']}] {ref_label}"
                )
            final_analysis = f"{final_analysis}\n" + "\n".join(refs_lines)
        else:
            final_analysis = (
                f"{final_analysis}\n\n### References\n"
                "- No inline [Sx] citations were produced by the model for standards claims."
            )
        persisted_prompt_text = _encode_prompt_with_mode(llm_user_prompt, selected_mode.key)
    else:
        llm_analysis_text = _build_mode_limited_analysis_text(
            mode=selected_mode,
            capability_eval=mode_eval,
            analysis_goal=analysis_goal,
            deterministic_available=bool(
                deterministic_metrics is not None and deterministic_metrics.get("available")
            ),
        )
        final_analysis = (
            mode_routing_section.strip()
            + "\n\n"
            + deterministic_section.strip()
            + "\n\n"
            + llm_analysis_text.strip()
            + "\n\n### References\n- This mode path did not run standards retrieval in the current release."
        )
        persisted_prompt_text = _encode_prompt_with_mode(analysis_goal, selected_mode.key)

    retrieved_source_ids = [
        str(source.get("source_id"))
        for source in sources
        if source.get("source_id")
    ]
    retrieved_sources_snapshot = _serialize_retrieval_snapshot(sources)
    parameter_stats_snapshot = _serialize_parameter_stats_snapshot(stats_rows)
    output_sha256 = hashlib.sha256(final_analysis.encode("utf-8")).hexdigest()

    analysis_job = AnalysisJob(
        flight_test_id=ft.id,
        created_by_id=current_user.id,
        dataset_version_id=dataset_version_id,
        status="completed",
        model_name=analysis_model,
        model_version=os.getenv("ANALYSIS_MODEL_VERSION"),
        parameters_analysed=len(stats_rows),
        parameter_stats_snapshot_json=json.dumps(parameter_stats_snapshot),
        prompt_text=persisted_prompt_text,
        retrieved_source_ids_json=json.dumps(retrieved_source_ids),
        retrieved_sources_snapshot_json=json.dumps(retrieved_sources_snapshot),
        output_sha256=output_sha256,
        analysis_text=final_analysis,
    )
    db.add(analysis_job)
    db.commit()
    db.refresh(analysis_job)

    return _analysis_job_to_response(
        job=analysis_job,
        flight_test_name=ft.test_name,
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
