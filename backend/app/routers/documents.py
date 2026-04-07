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
from typing import Any, Dict, List, Optional, Tuple

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
QUERY_MAX_TOKENS = max(512, min(4096, int(os.getenv("QUERY_MAX_TOKENS", "1800"))))
QUERY_TEMPERATURE = max(0.0, min(1.0, float(os.getenv("QUERY_TEMPERATURE", "0.1"))))
QUERY_MODEL = os.getenv("QUERY_LLM_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini")


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
    top_k: int = QUERY_TOP_K_DEFAULT
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


def _choose_param_id(params: List[dict], scorer) -> Optional[int]:
    best_id = None
    best_score = float("-inf")
    for p in params:
        score = scorer(p["name"], p.get("unit"))
        if score > best_score:
            best_score = score
            best_id = p["id"]
    return best_id if best_score > 0 else None


def _score_ground_speed(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "ground speed" in n or ("ground" in n and "speed" in n):
        score += 6
    if "airspeed" in n:
        score -= 2
    if re.search(r"\bgs\b", n):
        score += 2
    if "speed" in n:
        score += 1
    if "kt" in u:
        score += 2
    return score


def _score_wow(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    score = 0.0
    if "weight on wheels" in n:
        score += 8
    if re.search(r"\bwow\b", n):
        score += 5
    if "wheel" in n and "weight" in n:
        score += 3
    return score


def _score_longitudinal_accel(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "longitudinal" in n and "accel" in n:
        score += 6
    if "x accel" in n or "x_accel" in n or "longitudinal x" in n:
        score += 4
    if "accel" in n:
        score += 1
    if u == "g":
        score += 1
    return score


def _compute_takeoff_metrics(db: Session, flight_test_id: int) -> dict:
    """Compute takeoff run metrics from time-series data (deterministic)."""
    param_rows = (
        db.query(TestParameter.id, TestParameter.name, TestParameter.unit)
        .join(DataPoint, DataPoint.parameter_id == TestParameter.id)
        .filter(DataPoint.flight_test_id == flight_test_id)
        .distinct()
        .all()
    )
    params = [{"id": r.id, "name": r.name, "unit": r.unit} for r in param_rows]
    if not params:
        return {"available": False, "reason": "No parameters found for flight test."}

    ground_speed_id = _choose_param_id(params, _score_ground_speed)
    wow_ids = [p["id"] for p in params if _score_wow(p["name"], p.get("unit")) > 0]
    accel_id = _choose_param_id(params, _score_longitudinal_accel)

    if ground_speed_id is None:
        return {"available": False, "reason": "Ground speed parameter not found."}
    if not wow_ids:
        return {"available": False, "reason": "Weight-on-wheels parameter not found."}

    selected_ids = set([ground_speed_id, *wow_ids])
    if accel_id is not None:
        selected_ids.add(accel_id)

    rows = (
        db.query(DataPoint.timestamp, DataPoint.parameter_id, DataPoint.value)
        .filter(
            DataPoint.flight_test_id == flight_test_id,
            DataPoint.parameter_id.in_(selected_ids),
        )
        .order_by(DataPoint.timestamp.asc())
        .all()
    )
    if not rows:
        return {"available": False, "reason": "No datapoints found for required parameters."}

    timeline: Dict[Any, Dict[int, float]] = {}
    for r in rows:
        timeline.setdefault(r.timestamp, {})[r.parameter_id] = float(r.value)

    points = []
    for ts in sorted(timeline.keys()):
        vals = timeline[ts]
        gs = vals.get(ground_speed_id)
        if gs is None:
            continue
        wow_values = [vals[w_id] for w_id in wow_ids if w_id in vals]
        wow_avg = (sum(wow_values) / len(wow_values)) if wow_values else None
        accel_val = vals.get(accel_id) if accel_id is not None else None
        points.append({"ts": ts, "gs_kt": gs, "wow": wow_avg, "accel": accel_val})

    if len(points) < 2:
        return {"available": False, "reason": "Insufficient timeseries points for takeoff calculation."}

    liftoff_idx = None
    for i in range(1, len(points)):
        prev_pt = points[i - 1]
        cur_pt = points[i]
        if prev_pt["wow"] is None or cur_pt["wow"] is None:
            continue
        if prev_pt["wow"] >= 0.5 and cur_pt["wow"] < 0.5 and cur_pt["gs_kt"] >= 30:
            liftoff_idx = i
            break
    if liftoff_idx is None:
        for i, pt in enumerate(points):
            if pt["wow"] is not None and pt["wow"] < 0.5 and pt["gs_kt"] >= 30:
                liftoff_idx = i
                break
    if liftoff_idx is None:
        return {"available": False, "reason": "Could not detect liftoff transition from WOW signals."}

    start_idx = None
    for i in range(liftoff_idx, -1, -1):
        pt = points[i]
        if (pt["wow"] is None or pt["wow"] >= 0.5) and pt["gs_kt"] <= 5:
            start_idx = i
            break
    if start_idx is None:
        # fallback: earliest on-ground sample before liftoff
        candidates = [
            i for i in range(0, liftoff_idx + 1)
            if points[i]["wow"] is None or points[i]["wow"] >= 0.5
        ]
        start_idx = candidates[0] if candidates else 0

    if start_idx >= liftoff_idx:
        return {"available": False, "reason": "Invalid takeoff segment boundaries."}

    knot_to_fts = 1.687809857
    distance_ft = 0.0
    valid_intervals = 0
    for i in range(start_idx + 1, liftoff_idx + 1):
        p0 = points[i - 1]
        p1 = points[i]
        dt = (p1["ts"] - p0["ts"]).total_seconds()
        if dt <= 0 or dt > 10:
            continue
        v0 = max(p0["gs_kt"], 0.0) * knot_to_fts
        v1 = max(p1["gs_kt"], 0.0) * knot_to_fts
        distance_ft += ((v0 + v1) / 2.0) * dt
        valid_intervals += 1

    if valid_intervals == 0:
        return {"available": False, "reason": "No valid time intervals for distance integration."}

    start_pt = points[start_idx]
    liftoff_pt = points[liftoff_idx]
    duration_s = (liftoff_pt["ts"] - start_pt["ts"]).total_seconds()
    mean_accel_fts2 = None
    if duration_s > 0:
        mean_accel_fts2 = (
            (liftoff_pt["gs_kt"] - start_pt["gs_kt"]) * knot_to_fts
        ) / duration_s

    accel_samples = [
        pt["accel"] for pt in points[start_idx: liftoff_idx + 1]
        if pt["accel"] is not None
    ]
    accel_mean_g = (sum(accel_samples) / len(accel_samples)) if accel_samples else None
    accel_sensor_fts2 = (accel_mean_g * 32.174) if accel_mean_g is not None else None

    return {
        "available": True,
        "distance_ft": round(distance_ft, 1),
        "distance_m": round(distance_ft * 0.3048, 1),
        "wow_channels_used": len(wow_ids),
        "wow_ground_threshold": 0.5,
        "start_timestamp": start_pt["ts"].isoformat(),
        "liftoff_timestamp": liftoff_pt["ts"].isoformat(),
        "start_wow_mean": round(start_pt["wow"], 3) if start_pt["wow"] is not None else None,
        "liftoff_wow_mean": round(liftoff_pt["wow"], 3) if liftoff_pt["wow"] is not None else None,
        "start_speed_kt": round(start_pt["gs_kt"], 2),
        "liftoff_speed_kt": round(liftoff_pt["gs_kt"], 2),
        "run_time_s": round(duration_s, 2),
        "mean_accel_fts2": round(mean_accel_fts2, 3) if mean_accel_fts2 is not None else None,
        "sensor_accel_mean_g": round(accel_mean_g, 4) if accel_mean_g is not None else None,
        "sensor_accel_mean_fts2": round(accel_sensor_fts2, 3) if accel_sensor_fts2 is not None else None,
        "sample_intervals_used": valid_intervals,
    }


def _build_deterministic_takeoff_section(metrics: dict) -> str:
    """Render deterministic takeoff section directly from computed data."""
    if not metrics.get("available"):
        return (
            "## Deterministic Calculation (Flight Data) [DATA]\n"
            "Deterministic takeoff metrics are unavailable for this dataset.\n\n"
            f"- Reason: {metrics.get('reason', 'Unknown')}\n"
        )

    knot_to_fts = 1.687809857
    vi_kt = float(metrics["start_speed_kt"])
    vf_kt = float(metrics["liftoff_speed_kt"])
    t_s = float(metrics["run_time_s"])
    vi_fts = vi_kt * knot_to_fts
    vf_fts = vf_kt * knot_to_fts
    accel_fts2 = metrics.get("mean_accel_fts2")
    accel_for_eq = float(accel_fts2) if accel_fts2 is not None else None
    distance_integrated = float(metrics["distance_ft"])

    distance_kinematic = None
    if accel_for_eq is not None:
        distance_kinematic = (vi_fts * t_s) + (0.5 * accel_for_eq * (t_s ** 2))

    lines = [
        "## Deterministic Calculation (Flight Data) [DATA]",
        "",
        "### Computed Metrics",
        f"- Takeoff roll distance (integrated speed trace): **{metrics['distance_ft']} ft ({metrics['distance_m']} m)**",
        f"- Run time (start-to-liftoff): **{metrics['run_time_s']} s**",
        f"- Start speed: **{metrics['start_speed_kt']} kt**",
        f"- Liftoff speed: **{metrics['liftoff_speed_kt']} kt**",
        f"- Mean acceleration from speed trace: **{metrics.get('mean_accel_fts2', 'n/a')} ft/s^2**",
        (
            f"- Mean acceleration from sensor: **{metrics.get('sensor_accel_mean_g', 'n/a')} g "
            f"({metrics.get('sensor_accel_mean_fts2', 'n/a')} ft/s^2)**"
        ),
        f"- Integration intervals used: **{metrics['sample_intervals_used']}**",
        "",
        "### WOW-Based Segment Definition",
        (
            f"- WOW channels used: **{metrics.get('wow_channels_used', 'n/a')}** "
            "(LH/RH wheels when available)"
        ),
        (
            f"- On-ground condition: **mean WOW >= {metrics.get('wow_ground_threshold', 0.5)}** "
            "(approximately WOW=1)"
        ),
        (
            f"- Airborne condition: **mean WOW < {metrics.get('wow_ground_threshold', 0.5)}** "
            "(approximately WOW=0)"
        ),
        (
            f"- Start sample: **{metrics.get('start_timestamp', 'n/a')}** "
            f"(WOW={metrics.get('start_wow_mean', 'n/a')}, GS={metrics['start_speed_kt']} kt)"
        ),
        (
            f"- Liftoff sample: **{metrics.get('liftoff_timestamp', 'n/a')}** "
            f"(WOW={metrics.get('liftoff_wow_mean', 'n/a')}, GS={metrics['liftoff_speed_kt']} kt)"
        ),
        "",
        "### Equations",
        "- Velocity conversion: V_ft_s = V_kt x 1.687809857",
        "- Mean acceleration from speed trace: a = (Vf - Vi) / t",
        "- Kinematic distance check: d = Vi x t + 0.5 x a x t^2",
        "",
        "### Substitution (units preserved)",
        f"- Vi = {vi_kt} kt = {vi_fts:.3f} ft/s",
        f"- Vf = {vf_kt} kt = {vf_fts:.3f} ft/s",
        f"- t = {t_s} s",
    ]
    if accel_for_eq is not None:
        lines.append(f"- a = ({vf_fts:.3f} - {vi_fts:.3f}) / {t_s:.2f} = {accel_for_eq:.3f} ft/s^2")
    if distance_kinematic is not None:
        lines.append(
            f"- Kinematic distance check: d ≈ {distance_kinematic:.1f} ft "
            f"(integrated result: {distance_integrated:.1f} ft)"
        )
    lines.extend(
        [
            "",
            "Use the integrated speed-trace distance as the primary deterministic takeoff result [DATA].",
        ]
    )
    return "\n".join(lines)


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
            sources=[],
        )

    system_prompt = (
        "You are an expert flight test engineer and technical analyst. "
        "Use ONLY the provided source excerpts. "
        "Write a detailed technical answer with explicit assumptions, equations, "
        "step-by-step method, and units where relevant. "
        "For every technical claim or calculation step, cite source IDs like [S1]. "
        "If critical inputs are missing, state exactly what is missing and do not invent values. "
        "End your response with a single line: USED_SOURCES: S1,S2"
    )

    user_prompt = (
        f"Question: {request.question}\n\n"
        "Instructions:\n"
        "- Be comprehensive and precise.\n"
        "- Include equations in markdown form when useful.\n"
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

    used_source_ids = _extract_used_source_ids(answer)
    answer = re.sub(r"(?im)^USED_SOURCES:\s*.*$", "", answer).strip()

    if used_source_ids:
        cited = [s for s in sources if s.get("source_id") in set(used_source_ids)]
        if cited:
            sources = cited

    response_sources = [{k: v for k, v in s.items() if k != "text"} for s in sources]
    return QueryResponse(answer=answer, sources=response_sources)


# ---------------------------------------------------------------------------
# POST /api/documents/flight-tests/{flight_test_id}/ai-analysis
# ---------------------------------------------------------------------------

class AIAnalysisRequest(BaseModel):
    user_prompt: str | None = None


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

    # If the user supplied a specific analysis goal, use it; otherwise use the default.
    if body.user_prompt and body.user_prompt.strip():
        analysis_goal = body.user_prompt.strip()
    else:
        analysis_goal = (
            "Produce a structured report with: (1) Executive Summary, "
            "(2) Parameter Analysis with notable observations, "
            "(3) Potential Anomalies or Concerns, (4) Recommendations."
        )

    # Deterministic takeoff metrics from time-series data (authoritative section)
    takeoff_metrics = _compute_takeoff_metrics(db=db, flight_test_id=flight_test_id)
    deterministic_section = _build_deterministic_takeoff_section(takeoff_metrics)

    # Hybrid document retrieval with stable source IDs
    param_names = [r.name for r in stats_rows[:10]]
    retrieval_focus = (
        "takeoff distance ground roll liftoff runway acceleration "
        "weight on wheels procedures certification"
    )
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

    # Build the LLM prompt (LLM writes interpretation/cross-check only)
    system_prompt = (
        "You are a senior flight test engineer. "
        "A deterministic takeoff section has already been computed by software and must not be recalculated "
        "or numerically modified. "
        "Your task is to produce interpretation and standards cross-check only, using ONLY provided source excerpts. "
        "Cite standards claims with [Sx]. For deterministic data references, use [DATA]. "
        "Do not emit USED_SOURCES footer."
    )

    user_prompt = (
        f"Flight Test: {ft.test_name}\n"
        f"Aircraft: {ft.aircraft_type or 'Not specified'}\n"
        f"Test Date: {ft.test_date.strftime('%Y-%m-%d') if ft.test_date else 'Not specified'}\n"
        f"Description: {ft.description or 'None'}\n\n"
        f"Analysis Goal: {analysis_goal}\n\n"
        f"Parameter Statistics:\n{stats_table}\n\n"
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

    if context_text:
        user_prompt += f"\n\nReference Document Excerpts:\n\n{context_text}"

    analysis_model = os.getenv("ANALYSIS_LLM_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    analysis_temperature = max(0.0, min(1.0, float(os.getenv("ANALYSIS_TEMPERATURE", "0.2"))))
    analysis_max_tokens = max(1200, min(4096, int(os.getenv("ANALYSIS_MAX_TOKENS", "2600"))))

    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model=analysis_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=analysis_temperature,
            max_tokens=analysis_max_tokens,
        )
        analysis_text = completion.choices[0].message.content or ""
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM analysis failed: {exc}",
        )

    analysis_text = re.sub(r"(?im)^USED_SOURCES:\s*.*$", "", analysis_text).strip()

    # Optional strict citation-density repair for Standards Cross-Check section.
    min_citation_density = max(
        0.0, min(1.0, float(os.getenv("ANALYSIS_MIN_CITATION_DENSITY", "0.75")))
    )
    standards_section = _extract_standards_cross_check_section(analysis_text)
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
            f"{analysis_text}"
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
                analysis_text = repaired_text
        except Exception as repair_exc:
            logger.warning("Citation density repair skipped due to LLM error: %s", repair_exc)

    inline_source_ids = _extract_inline_source_ids(analysis_text)
    if inline_source_ids and sources:
        cited_sources = [s for s in sources if s.get("source_id") in set(inline_source_ids)]
    else:
        cited_sources = []

    final_analysis = deterministic_section.strip() + "\n\n" + analysis_text.strip()

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

    return AIAnalysisResponse(
        analysis=final_analysis,
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
