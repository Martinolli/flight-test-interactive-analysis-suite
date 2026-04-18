"""
FTIAS Backend - Admin Router
Superuser-only endpoints:
  - User management (list, update role/password, delete)
  - PDF report export for AI Analysis results
"""

import io
import logging
import os
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth import get_current_superuser, get_password_hash
from app.capabilities import get_capability_definition
from app.database import get_db
from app.models import AnalysisJob, Document, FlightTest, User

logger = logging.getLogger(__name__)

router = APIRouter()


def _latex_to_plain(text: str) -> str:
    """Best-effort conversion of common LaTeX fragments to plain text."""
    if not text:
        return text

    # Block and inline math wrappers
    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text, flags=re.DOTALL)

    # Convert \frac{a}{b} iteratively
    for _ in range(6):
        new_text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
        if new_text == text:
            break
        text = new_text

    text = text.replace(r"\cdot", " * ")
    text = text.replace(r"\times", " x ")
    text = text.replace(r"\approx", " ≈ ")
    text = text.replace(r"\mathrm", "")
    text = text.replace(r"\text", "")
    text = re.sub(r"\\[a-zA-Z]+", "", text)  # remove remaining latex commands
    text = text.replace("{", "").replace("}", "")
    return text


def _sanitize_pdf_text(text: str) -> str:
    """Normalize text for stable PDF rendering and extraction."""
    if not text:
        return ""

    text = _latex_to_plain(text)

    # Normalize bullets to ASCII dash to avoid odd glyph mapping in PDF extraction
    text = text.replace("\u2022", "- ")
    text = text.replace("\uf0b7", "- ")

    # Remove non-printable control chars (keep newline/tab)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)

    # Collapse noisy whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_parameter_stats_snapshot(analysis_job: AnalysisJob) -> List[dict]:
    raw = analysis_job.parameter_stats_snapshot_json or "[]"
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return data


def _load_retrieved_sources_snapshot(analysis_job: AnalysisJob) -> List[dict]:
    raw = analysis_job.retrieved_sources_snapshot_json or "[]"
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _format_float(value: Any, decimals: int = 3) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{num:.{decimals}f}"


def _format_int(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "0"


def _safe_stat_value(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate_text(text: str, max_len: int = 40) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _normalise_stats_snapshot(stats_snapshot: List[dict]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in stats_snapshot or []:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "name": _sanitize_pdf_text(str(row.get("name") or "—")),
                "unit": _sanitize_pdf_text(str(row.get("unit") or "—")),
                "min_val": _safe_stat_value(row.get("min_val")),
                "max_val": _safe_stat_value(row.get("max_val")),
                "avg_val": _safe_stat_value(row.get("avg_val")),
                "std_val": _safe_stat_value(row.get("std_val")),
                "sample_count": int(row.get("sample_count") or 0),
            }
        )

    # Stable deterministic ordering for reproducible output
    normalized.sort(key=lambda item: ((item["name"] or "").lower(), item["sample_count"]))
    return normalized


def _dataset_provenance_dict(analysis_job: Optional[AnalysisJob]) -> Dict[str, str]:
    if not analysis_job:
        return {
            "dataset_version_id": "—",
            "dataset_label": "Not linked",
            "dataset_number": "—",
            "dataset_status": "—",
            "dataset_row_count": "—",
            "dataset_data_points": "—",
            "source_session_id": "—",
        }

    dataset = analysis_job.dataset_version
    if dataset is None:
        return {
            "dataset_version_id": str(analysis_job.dataset_version_id or "—"),
            "dataset_label": "Unavailable",
            "dataset_number": "—",
            "dataset_status": "—",
            "dataset_row_count": "—",
            "dataset_data_points": "—",
            "source_session_id": "—",
        }

    return {
        "dataset_version_id": str(dataset.id),
        "dataset_label": _sanitize_pdf_text(dataset.label or "—"),
        "dataset_number": str(dataset.version_number),
        "dataset_status": _sanitize_pdf_text(dataset.status or "—"),
        "dataset_row_count": _format_int(dataset.row_count) if dataset.row_count is not None else "—",
        "dataset_data_points": (
            _format_int(dataset.data_points_count)
            if dataset.data_points_count is not None
            else "—"
        ),
        "source_session_id": (
            str(dataset.source_session_id) if dataset.source_session_id is not None else "—"
        ),
    }


def _analysis_summary_dict(
    *,
    analysis_job: Optional[AnalysisJob],
    stats_snapshot: List[Dict[str, Any]],
    retrieved_sources_snapshot: List[dict],
) -> Dict[str, str]:
    if not analysis_job:
        return {
            "analysis_job_id": "—",
            "analysis_created_at": "—",
            "model": "—",
            "parameters_analysed": _format_int(len(stats_snapshot)),
            "retrieved_sources": _format_int(len(retrieved_sources_snapshot)),
            "output_sha256": "—",
        }

    created_at = (
        analysis_job.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if analysis_job.created_at
        else "—"
    )
    model_line = _sanitize_pdf_text(analysis_job.model_name or "—")
    if analysis_job.model_version:
        model_line = f"{model_line} ({_sanitize_pdf_text(analysis_job.model_version)})"

    return {
        "analysis_job_id": str(analysis_job.id),
        "analysis_created_at": created_at,
        "model": model_line,
        "parameters_analysed": _format_int(analysis_job.parameters_analysed),
        "retrieved_sources": _format_int(len(retrieved_sources_snapshot)),
        "output_sha256": analysis_job.output_sha256 or "—",
    }


def _classify_paragraph(text: str) -> str:
    normalized = text.strip().lower()
    if (
        normalized.startswith("warning")
        or normalized.startswith("caution")
        or normalized.startswith("risk")
        or normalized.startswith("limitation")
        or "quality notice" in normalized
        or "insufficient citation" in normalized
    ):
        return "warning"
    if (
        normalized.startswith("recommendation")
        or normalized.startswith("mitigation")
        or normalized.startswith("action")
        or normalized.startswith("next step")
    ):
        return "recommendation"
    if (
        normalized.startswith("finding")
        or normalized.startswith("observation")
        or normalized.startswith("result")
        or normalized.startswith("conclusion")
    ):
        return "finding"
    return "normal"


def _is_takeoff_groundroll_context(
    *,
    analysis_text: str,
    analysis_job: Optional[AnalysisJob],
) -> bool:
    haystack = f"{analysis_text or ''}\n{(analysis_job.prompt_text if analysis_job else '')}".lower()
    has_takeoff = "takeoff" in haystack
    has_groundroll = ("ground roll" in haystack) or ("liftoff" in haystack) or ("wow" in haystack)
    return has_takeoff and has_groundroll


def _section_key_for_heading(heading_text: str) -> str:
    title = heading_text.strip().lower()
    if not title:
        return "general"
    if any(token in title for token in ["deterministic", "computed metrics", "wow-based", "equations"]):
        return "deterministic"
    if any(token in title for token in ["standards cross-check", "standards", "compliance"]):
        return "standards"
    if any(token in title for token in ["assumption", "limitations", "risk", "constraint", "uncertainty"]):
        return "assumptions"
    if any(token in title for token in ["recommendation", "mitigation", "next step", "actions"]):
        return "recommendations"
    if any(token in title for token in ["applicability", "boundary", "scope", "validity"]):
        return "applicability"
    if "executive summary" in title or title == "summary":
        return "summary"
    if "reference" in title:
        return "references"
    return "general"


def _bucket_analysis_blocks(blocks: List[dict]) -> Dict[str, List[dict]]:
    buckets: Dict[str, List[dict]] = {
        "deterministic": [],
        "standards": [],
        "assumptions": [],
        "recommendations": [],
        "applicability": [],
        "summary": [],
        "general": [],
        "references": [],
    }
    current_section = "general"
    for block in blocks:
        if block.get("type") == "heading":
            new_section = _section_key_for_heading(str(block.get("text") or ""))
            if new_section == "general" and current_section in {
                "deterministic",
                "standards",
                "assumptions",
                "recommendations",
                "applicability",
            }:
                # Keep current classified section for sub-headings that do not map directly.
                continue
            current_section = new_section
            continue
        buckets.setdefault(current_section, []).append(block)
    return buckets


def _default_takeoff_limitations() -> List[str]:
    takeoff = get_capability_definition("takeoff")
    if takeoff and takeoff.default_limitations:
        return list(takeoff.default_limitations) + [
            "Result is an approximate engineering estimate, not a formal certification metric.",
        ]
    return [
        "Wind correction not applied.",
        "Runway slope correction not applied.",
        "Non-standard atmosphere correction not applied.",
        "WOW transition timing can shift the detected liftoff event.",
        "Sampling frequency and sensor quality can materially affect estimate precision.",
        "Result is an approximate engineering estimate, not a formal certification metric.",
    ]


def _default_takeoff_applicability() -> List[str]:
    takeoff = get_capability_definition("takeoff")
    if takeoff and takeoff.applicability_boundaries:
        return list(takeoff.applicability_boundaries)
    return [
        "Valid for estimated ground roll to liftoff from available WOW and ground-speed data.",
        "Not sufficient on its own for corrected certification takeoff distance to screen height.",
    ]


# ---------------------------------------------------------------------------
# Pydantic schemas (admin-specific)
# ---------------------------------------------------------------------------

class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class AdminUserUpdate(BaseModel):
    """Fields an admin can change on any user account."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    new_password: Optional[str] = None  # plain-text; will be hashed server-side


class AdminUserCreate(BaseModel):
    """Fields required to create a new user account."""
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    is_superuser: bool = False


# ---------------------------------------------------------------------------
# POST /api/admin/users  — create a new user
# ---------------------------------------------------------------------------

@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_superuser),
):
    """Create a new user account (admin only)."""
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken.")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already in use.")

    new_user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_superuser=payload.is_superuser,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("Admin %s created user %s", _admin.username, new_user.username)
    return _user_to_out(new_user)


# ---------------------------------------------------------------------------
# GET /api/admin/users  — list all users
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_superuser),
):
    """Return all registered users, newest first."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_to_out(u) for u in users]


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}  — update role / password / status
# ---------------------------------------------------------------------------

@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_superuser),
):
    """Update a user's role, active status, password, or name."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        # Check uniqueness
        conflict = db.query(User).filter(User.email == payload.email, User.id != user_id).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Email already in use.")
        user.email = payload.email
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_superuser is not None:
        # Prevent admin from demoting themselves
        if user.id == admin.id and not payload.is_superuser:
            raise HTTPException(
                status_code=400,
                detail="You cannot remove your own admin privileges.",
            )
        user.is_superuser = payload.is_superuser
    if payload.new_password:
        if len(payload.new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        user.hashed_password = get_password_hash(payload.new_password)

    db.commit()
    db.refresh(user)
    logger.info("Admin %s updated user %d", admin.username, user_id)
    return _user_to_out(user)


# ---------------------------------------------------------------------------
# DELETE /api/admin/users/{user_id}  — delete a user
# ---------------------------------------------------------------------------

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_superuser),
):
    """Permanently delete a user account."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    db.delete(user)
    db.commit()
    logger.info("Admin %s deleted user %d (%s)", admin.username, user_id, user.username)
    return {"message": f"User '{user.username}' deleted successfully."}


# ---------------------------------------------------------------------------
# GET /api/admin/flight-tests/{flight_test_id}/report.pdf
# ---------------------------------------------------------------------------

@router.get("/flight-tests/{flight_test_id}/report.pdf")
def export_ai_analysis_pdf(
    flight_test_id: int,
    analysis_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Generate and stream a PDF report for a persisted AI analysis job.
    Uses immutable saved analysis artifact and provenance.
    """
    ft = db.query(FlightTest).filter(FlightTest.id == flight_test_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Flight test not found.")
    analysis_job = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.id == analysis_job_id,
            AnalysisJob.flight_test_id == flight_test_id,
        )
        .first()
    )
    if not analysis_job:
        raise HTTPException(status_code=404, detail="Analysis job not found for this flight test.")

    pdf_bytes = _build_pdf(
        flight_test=ft,
        stats_snapshot=_load_parameter_stats_snapshot(analysis_job),
        analysis_text=analysis_job.analysis_text,
        generated_by=current_user.full_name or current_user.username,
        analysis_job=analysis_job,
    )

    filename = (
        f"FTIAS_Report_{ft.test_name.replace(' ', '_')}_"
        f"AJ{analysis_job.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# POST /api/admin/flight-tests/{flight_test_id}/report.pdf
# (accepts analysis text in request body — avoids URL length limits)
# ---------------------------------------------------------------------------

class PDFReportRequest(BaseModel):
    analysis_job_id: int


@router.post("/flight-tests/{flight_test_id}/report.pdf")
def export_ai_analysis_pdf_post(
    flight_test_id: int,
    body: PDFReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    POST variant of the PDF export endpoint.
    Accepts immutable analysis job ID in the request body.
    """
    ft = db.query(FlightTest).filter(FlightTest.id == flight_test_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Flight test not found.")
    analysis_job = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.id == body.analysis_job_id,
            AnalysisJob.flight_test_id == flight_test_id,
        )
        .first()
    )
    if not analysis_job:
        raise HTTPException(status_code=404, detail="Analysis job not found for this flight test.")

    pdf_bytes = _build_pdf(
        flight_test=ft,
        stats_snapshot=_load_parameter_stats_snapshot(analysis_job),
        analysis_text=analysis_job.analysis_text,
        generated_by=current_user.full_name or current_user.username,
        analysis_job=analysis_job,
    )

    filename = (
        f"FTIAS_Report_{ft.test_name.replace(' ', '_')}_"
        f"AJ{analysis_job.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# PDF builder (reportlab)
# ---------------------------------------------------------------------------

def _build_pdf(
    flight_test: FlightTest,
    stats_snapshot: List[dict],
    analysis_text: str,
    generated_by: str,
    analysis_job: Optional[AnalysisJob] = None,
) -> bytes:
    """
    Build an engineering-grade PDF report from immutable analysis-job artifacts.
    Section order:
      1. Cover / title
      2. Flight test metadata summary
      3. Dataset provenance summary
      4. Analysis summary
      5. Key charts / figures
      6. Parameter statistics summary
      7. AI analysis narrative
      8. Sources / provenance / references
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is not installed. Add 'reportlab>=4.0' to requirements.txt "
            "and rebuild the Docker image."
        ) from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=f"FTIAS Engineering Report — {flight_test.test_name}",
        author="FTIAS",
        pageCompression=0,
    )

    styles = getSampleStyleSheet()

    cover_title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#1e3a5f"),
        alignment=TA_CENTER,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#355070"),
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName="Helvetica",
    )
    cover_context_style = ParagraphStyle(
        "CoverContext",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#4f647a"),
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName="Helvetica",
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=13.5,
        textColor=colors.HexColor("#1e3a5f"),
        spaceBefore=15,
        spaceAfter=7,
        fontName="Helvetica-Bold",
    )
    subsection_style = ParagraphStyle(
        "SubSection",
        parent=styles["Heading3"],
        fontSize=11,
        textColor=colors.HexColor("#27496d"),
        spaceBefore=8,
        spaceAfter=5,
        fontName="Helvetica-Bold",
    )
    caption_style = ParagraphStyle(
        "FigureCaption",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#445668"),
        spaceBefore=3,
        spaceAfter=8,
        fontName="Helvetica-Oblique",
    )
    narrative_heading_style = ParagraphStyle(
        "NarrativeHeading",
        parent=styles["Heading3"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1f3b57"),
        spaceBefore=7,
        spaceAfter=3,
        fontName="Helvetica-Bold",
    )
    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=colors.HexColor("#5f7387"),
        fontName="Helvetica",
    )
    meta_value_style = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#1d2733"),
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=6,
        fontName="Helvetica",
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#5f7387"),
        spaceBefore=3,
        fontName="Helvetica",
    )

    story = []
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    normalized_stats = _normalise_stats_snapshot(stats_snapshot)
    retrieved_sources_snapshot = (
        _load_retrieved_sources_snapshot(analysis_job)
        if analysis_job is not None
        else []
    )
    dataset_summary = _dataset_provenance_dict(analysis_job)
    analysis_summary = _analysis_summary_dict(
        analysis_job=analysis_job,
        stats_snapshot=normalized_stats,
        retrieved_sources_snapshot=retrieved_sources_snapshot,
    )

    # ---- Cover / title ----
    story.append(Paragraph("FTIAS Engineering Analysis Report", cover_title_style))
    story.append(Paragraph("Flight Test Interactive Analysis Suite", cover_subtitle_style))
    story.append(
        Paragraph(
            f"Flight Test #{flight_test.id}: {_sanitize_pdf_text(flight_test.test_name)}",
            cover_context_style,
        )
    )
    story.append(Paragraph(f"Report generated: {generated_at}", cover_context_style))
    if analysis_job:
        model_line = _sanitize_pdf_text(analysis_job.model_name or "—")
        if analysis_job.model_version:
            model_line += f" ({_sanitize_pdf_text(analysis_job.model_version)})"
        story.append(
            Paragraph(
                f"Analysis Job #{analysis_job.id} · Model {model_line}",
                cover_context_style,
            )
        )
    story.append(Spacer(1, 0.25 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f")))
    story.append(Spacer(1, 0.2 * cm))

    # ---- 1) Flight test metadata summary ----
    story.append(Paragraph("1. Flight Test Metadata Summary", section_title_style))
    test_date_str = (
        flight_test.test_date.strftime("%Y-%m-%d") if flight_test.test_date else "Not specified"
    )

    metadata_rows = [
        [Paragraph("Flight Test ID", meta_label_style), Paragraph(str(flight_test.id), meta_value_style)],
        [
            Paragraph("Flight Test Name", meta_label_style),
            Paragraph(_sanitize_pdf_text(flight_test.test_name), meta_value_style),
        ],
        [
            Paragraph("Aircraft Type", meta_label_style),
            Paragraph(_sanitize_pdf_text(flight_test.aircraft_type or "Not specified"), meta_value_style),
        ],
        [Paragraph("Test Date", meta_label_style), Paragraph(test_date_str, meta_value_style)],
        [
            Paragraph("Generated By", meta_label_style),
            Paragraph(_sanitize_pdf_text(generated_by or "FTIAS"), meta_value_style),
        ],
        [Paragraph("Generated At", meta_label_style), Paragraph(generated_at, meta_value_style)],
    ]
    if flight_test.description:
        metadata_rows.append(
            [
                Paragraph("Description", meta_label_style),
                Paragraph(_strip_markdown(flight_test.description), body_style),
            ]
        )

    metadata_table = Table(metadata_rows, colWidths=[4.0 * cm, 13.0 * cm])
    metadata_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1d2733")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(metadata_table)
    story.append(Spacer(1, 0.2 * cm))

    # ---- 2) Dataset provenance summary ----
    story.append(Paragraph("2. Dataset Provenance Summary", section_title_style))
    dataset_rows = [
        [Paragraph("Dataset Version ID", meta_label_style), Paragraph(dataset_summary["dataset_version_id"], meta_value_style)],
        [Paragraph("Dataset Label", meta_label_style), Paragraph(dataset_summary["dataset_label"], meta_value_style)],
        [Paragraph("Version Number", meta_label_style), Paragraph(dataset_summary["dataset_number"], meta_value_style)],
        [Paragraph("Status", meta_label_style), Paragraph(dataset_summary["dataset_status"], meta_value_style)],
        [Paragraph("Rows", meta_label_style), Paragraph(dataset_summary["dataset_row_count"], meta_value_style)],
        [Paragraph("Data Points", meta_label_style), Paragraph(dataset_summary["dataset_data_points"], meta_value_style)],
        [Paragraph("Source Session ID", meta_label_style), Paragraph(dataset_summary["source_session_id"], meta_value_style)],
    ]
    dataset_table = Table(dataset_rows, colWidths=[4.0 * cm, 13.0 * cm])
    dataset_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1d2733")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(dataset_table)
    story.append(Spacer(1, 0.2 * cm))

    # ---- 3) Analysis summary ----
    story.append(Paragraph("3. Analysis Summary", section_title_style))
    analysis_rows = [
        [Paragraph("Analysis Job ID", meta_label_style), Paragraph(analysis_summary["analysis_job_id"], meta_value_style)],
        [Paragraph("Analysis Created At", meta_label_style), Paragraph(analysis_summary["analysis_created_at"], meta_value_style)],
        [Paragraph("Model", meta_label_style), Paragraph(analysis_summary["model"], meta_value_style)],
        [Paragraph("Parameters Analysed", meta_label_style), Paragraph(analysis_summary["parameters_analysed"], meta_value_style)],
        [Paragraph("Retrieved Sources", meta_label_style), Paragraph(analysis_summary["retrieved_sources"], meta_value_style)],
        [Paragraph("Output Hash (SHA-256)", meta_label_style), Paragraph(_sanitize_pdf_text(analysis_summary["output_sha256"]), body_style)],
    ]
    analysis_table = Table(analysis_rows, colWidths=[4.0 * cm, 13.0 * cm])
    analysis_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1d2733")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(analysis_table)
    story.append(Spacer(1, 0.2 * cm))

    # ---- 4) Key charts / figures ----
    story.append(Paragraph("4. Key Charts / Figures", section_title_style))
    figure_blocks = _build_stats_figures(normalized_stats)
    if figure_blocks:
        for figure_title, drawing, caption in figure_blocks:
            story.append(Paragraph(figure_title, subsection_style))
            story.append(drawing)
            story.append(Paragraph(caption, caption_style))
    else:
        story.append(
            Paragraph(
                "No persisted parameter statistics were available to render engineering figures.",
                body_style,
            )
        )

    # ---- 5) Parameter statistics summary ----
    story.append(Paragraph("5. Parameter Statistics Summary", section_title_style))
    if normalized_stats:
        total_samples = sum(max(0, int(row.get("sample_count") or 0)) for row in normalized_stats)
        story.append(
            Paragraph(
                (
                    f"Snapshot includes {len(normalized_stats)} parameters with "
                    f"{total_samples} samples total."
                ),
                body_style,
            )
        )

        table_data = [["Parameter", "Unit", "Min", "Max", "Mean", "Std Dev", "Samples"]]
        for row in normalized_stats:
            table_data.append(
                [
                    _sanitize_pdf_text(str(row.get("name") or "—")),
                    _sanitize_pdf_text(str(row.get("unit") or "—")),
                    _format_float(row.get("min_val")),
                    _format_float(row.get("max_val")),
                    _format_float(row.get("avg_val")),
                    _format_float(row.get("std_val")),
                    _format_int(row.get("sample_count")),
                ]
            )

        para_style_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica",
            wordWrap="CJK",
        )
        para_style_hdr = ParagraphStyle(
            "TableHdr",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
            textColor=colors.white,
            wordWrap="CJK",
        )
        wrapped_data = []
        for i, row in enumerate(table_data):
            if i == 0:
                wrapped_data.append([Paragraph(_sanitize_pdf_text(str(c)), para_style_hdr) for c in row])
            else:
                wrapped_data.append(
                    [
                        Paragraph(_sanitize_pdf_text(str(row[0])), para_style_cell),
                        Paragraph(_sanitize_pdf_text(str(row[1])), para_style_cell),
                        Paragraph(_sanitize_pdf_text(str(row[2])), para_style_cell),
                        Paragraph(_sanitize_pdf_text(str(row[3])), para_style_cell),
                        Paragraph(_sanitize_pdf_text(str(row[4])), para_style_cell),
                        Paragraph(_sanitize_pdf_text(str(row[5])), para_style_cell),
                        Paragraph(_sanitize_pdf_text(str(row[6])), para_style_cell),
                    ]
                )

        col_widths = [5.5 * cm, 1.7 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 1.8 * cm]
        stats_table = Table(wrapped_data, colWidths=col_widths, repeatRows=1)
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8.5),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(stats_table)
    else:
        story.append(Paragraph("No parameter data available for this analysis job.", body_style))

    # ---- 6) Engineering assessment narrative ----
    story.append(Paragraph("6. Engineering Assessment Narrative", section_title_style))

    if analysis_text:
        analysis_text = _sanitize_pdf_text(analysis_text)
        parsed_blocks = _parse_markdown_blocks(analysis_text)
        buckets = _bucket_analysis_blocks(parsed_blocks)
        is_takeoff_context = _is_takeoff_groundroll_context(
            analysis_text=analysis_text,
            analysis_job=analysis_job,
        )

        def _render_blocks(blocks: List[dict]):
            for block in blocks:
                if block["type"] == "table":
                    tbl = _build_markdown_table(block["rows"], styles)
                    if tbl:
                        story.append(tbl)
                        story.append(Spacer(1, 0.25 * cm))
                    continue
                paragraph_text = _sanitize_pdf_text(block.get("text", ""))
                if not paragraph_text:
                    continue
                paragraph_kind = _classify_paragraph(paragraph_text)
                if paragraph_kind == "normal":
                    story.append(Paragraph(paragraph_text, body_style))
                else:
                    story.append(_build_callout_table(paragraph_text, paragraph_kind, styles))

        story.append(Paragraph("6.1 Deterministic Computed Result", subsection_style))
        if is_takeoff_context:
            story.append(
                _build_callout_table(
                    (
                        "Result type: Estimated takeoff ground roll to liftoff. "
                        "Classification: Deterministic data-derived estimate. "
                        "Certification-corrected takeoff distance was not computed in this report."
                    ),
                    "finding",
                    styles,
                )
            )
        if buckets["deterministic"]:
            _render_blocks(buckets["deterministic"])
        else:
            story.append(
                Paragraph(
                    "No deterministic subsection was explicitly provided in narrative text.",
                    body_style,
                )
            )

        story.append(Paragraph("6.2 Standards Cross-Check", subsection_style))
        if buckets["standards"]:
            _render_blocks(buckets["standards"])
        else:
            story.append(
                Paragraph(
                    "No explicit standards cross-check subsection was provided.",
                    body_style,
                )
            )

        story.append(Paragraph("6.3 Assumptions and Limitations", subsection_style))
        if buckets["assumptions"]:
            _render_blocks(buckets["assumptions"])
        if is_takeoff_context:
            for limitation in _default_takeoff_limitations():
                story.append(_build_callout_table(limitation, "warning", styles))
        elif not buckets["assumptions"]:
            story.append(
                Paragraph(
                    "No explicit assumptions/limitations subsection was provided.",
                    body_style,
                )
            )

        story.append(Paragraph("6.4 Recommendations", subsection_style))
        if buckets["recommendations"]:
            _render_blocks(buckets["recommendations"])
        else:
            story.append(
                Paragraph(
                    "No explicit recommendations subsection was provided.",
                    body_style,
                )
            )

        story.append(Paragraph("6.5 Applicability Boundaries", subsection_style))
        if buckets["applicability"]:
            _render_blocks(buckets["applicability"])
        if is_takeoff_context:
            for applicability_note in _default_takeoff_applicability():
                story.append(_build_callout_table(applicability_note, "warning", styles))
        elif not buckets["applicability"]:
            story.append(
                Paragraph(
                    "Applicability boundaries were not explicitly defined in narrative text.",
                    body_style,
                )
            )

        if buckets["summary"] or buckets["general"]:
            story.append(Paragraph("6.6 Additional Context", subsection_style))
            _render_blocks(buckets["summary"] + buckets["general"])
    else:
        story.append(
            Paragraph(
                "No analysis text is stored for this analysis job.",
                body_style,
            )
        )

    # ---- 7) Sources / provenance / references ----
    story.append(Paragraph("7. Sources / Provenance / References", section_title_style))
    if retrieved_sources_snapshot:
        sorted_sources = sorted(
            retrieved_sources_snapshot,
            key=lambda item: str(item.get("source_id") or ""),
        )
        source_rows = [["ID", "Document", "Location", "Similarity"]]
        for source in sorted_sources[:25]:
            document_label = _sanitize_pdf_text(
                str(source.get("title") or source.get("filename") or "—")
            )
            section = _sanitize_pdf_text(str(source.get("section_title") or ""))
            page_numbers = _sanitize_pdf_text(str(source.get("page_numbers") or ""))
            location = section or page_numbers or "—"
            source_rows.append(
                [
                    _sanitize_pdf_text(str(source.get("source_id") or "—")),
                    _truncate_text(document_label, 68),
                    _truncate_text(location, 40),
                    _format_float(source.get("similarity"), decimals=3),
                ]
            )

        source_hdr_style = ParagraphStyle(
            "SourceHdr",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
        source_cell_style = ParagraphStyle(
            "SourceCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica",
        )

        wrapped_source_rows = []
        for idx, row in enumerate(source_rows):
            style = source_hdr_style if idx == 0 else source_cell_style
            wrapped_source_rows.append([Paragraph(_sanitize_pdf_text(str(cell)), style) for cell in row])

        source_table = Table(
            wrapped_source_rows,
            colWidths=[1.8 * cm, 8.3 * cm, 4.9 * cm, 2.0 * cm],
            repeatRows=1,
        )
        source_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27496d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(source_table)
    else:
        story.append(
            Paragraph(
                "No retrieved source snapshot is stored for this analysis job.",
                body_style,
            )
        )

    immutable_statement = (
        "Provenance statement: This PDF reflects persisted analysis job artifacts. "
        f"Analysis Job #{analysis_summary['analysis_job_id']} was generated against "
        f"Dataset Version #{dataset_summary['dataset_version_id']} "
        f"({dataset_summary['dataset_label']}) and exported on {generated_at}. "
        "Narrative text and parameter statistics are loaded from immutable saved snapshots, "
        "not from current mutable flight-test data."
    )
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#c8d6e5")))
    story.append(Paragraph(_sanitize_pdf_text(immutable_statement), footer_style))
    story.append(
        Paragraph(
            "Engineering notice: AI-generated content is advisory. Final safety/performance conclusions "
            "must be validated by qualified flight-test engineering review.",
            footer_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _build_callout_table(text: str, kind: str, styles):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Table, TableStyle

    palette = {
        "warning": (colors.HexColor("#fff4e5"), colors.HexColor("#b45309")),
        "recommendation": (colors.HexColor("#ecfdf3"), colors.HexColor("#166534")),
        "finding": (colors.HexColor("#eff6ff"), colors.HexColor("#1d4ed8")),
    }
    bg_color, border_color = palette.get(kind, (colors.HexColor("#f8fafc"), colors.HexColor("#64748b")))
    text_style = ParagraphStyle(
        f"CalloutText{kind.title()}",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1f2937"),
        fontName="Helvetica",
    )
    table = Table([[Paragraph(_sanitize_pdf_text(text), text_style)]], colWidths=[17.0 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("BOX", (0, 0), (-1, -1), 0.8, border_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _build_stats_figures(stats_rows: List[Dict[str, Any]]) -> List[tuple]:
    if not stats_rows:
        return []
    try:
        from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
        from reportlab.graphics.charts.legends import Legend
        from reportlab.graphics.shapes import Drawing
        from reportlab.lib import colors
        from reportlab.lib.units import cm
    except Exception:
        return []

    figures: List[tuple] = []

    by_samples = sorted(
        stats_rows,
        key=lambda row: (-int(row.get("sample_count") or 0), str(row.get("name") or "")),
    )
    top_counts = [row for row in by_samples if int(row.get("sample_count") or 0) > 0][:8]
    if top_counts:
        labels = [_truncate_text(str(row.get("name") or "—"), 22) for row in top_counts][::-1]
        values = [int(row.get("sample_count") or 0) for row in top_counts][::-1]

        drawing = Drawing(16.5 * cm, 7.5 * cm)
        chart = HorizontalBarChart()
        chart.x = 3.6 * cm
        chart.y = 0.9 * cm
        chart.width = 11.8 * cm
        chart.height = 5.8 * cm
        chart.data = [values]
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.fontName = "Helvetica"
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.boxAnchor = "e"
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(max(values), 1) * 1.15
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.labels.fontName = "Helvetica"
        chart.barWidth = 8
        chart.groupSpacing = 4
        chart.bars[0].fillColor = colors.HexColor("#3b82f6")
        chart.bars[0].strokeColor = colors.HexColor("#1d4ed8")
        drawing.add(chart)

        figures.append(
            (
                "Figure 1. Sample Count by Parameter (Top 8)",
                drawing,
                "Persisted parameter statistics snapshot. Higher bars indicate higher data density per channel.",
            )
        )

    top_profile = [row for row in by_samples if row.get("avg_val") is not None][:6]
    if top_profile:
        labels = [_truncate_text(str(row.get("name") or "—"), 18) for row in top_profile]
        min_vals = [row.get("min_val") if row.get("min_val") is not None else 0.0 for row in top_profile]
        mean_vals = [row.get("avg_val") if row.get("avg_val") is not None else 0.0 for row in top_profile]
        max_vals = [row.get("max_val") if row.get("max_val") is not None else 0.0 for row in top_profile]

        min_value = min(min(min_vals), min(mean_vals), min(max_vals))
        max_value = max(max(min_vals), max(mean_vals), max(max_vals))
        if min_value == max_value:
            max_value = min_value + 1.0

        drawing = Drawing(16.5 * cm, 8.5 * cm)
        chart = VerticalBarChart()
        chart.x = 1.0 * cm
        chart.y = 1.5 * cm
        chart.width = 12.6 * cm
        chart.height = 5.8 * cm
        chart.data = [min_vals, mean_vals, max_vals]
        chart.categoryAxis.categoryNames = labels
        chart.categoryAxis.labels.fontName = "Helvetica"
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.labels.fontName = "Helvetica"
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = min_value * 0.98 if min_value < 0 else 0
        chart.valueAxis.valueMax = max_value * 1.05
        chart.groupSpacing = 8
        chart.barSpacing = 1
        chart.bars[0].fillColor = colors.HexColor("#93c5fd")
        chart.bars[1].fillColor = colors.HexColor("#3b82f6")
        chart.bars[2].fillColor = colors.HexColor("#1d4ed8")
        drawing.add(chart)

        legend = Legend()
        legend.x = 13.8 * cm
        legend.y = 4.8 * cm
        legend.colorNamePairs = [
            (colors.HexColor("#93c5fd"), "Min"),
            (colors.HexColor("#3b82f6"), "Mean"),
            (colors.HexColor("#1d4ed8"), "Max"),
        ]
        legend.fontName = "Helvetica"
        legend.fontSize = 7
        legend.dx = 7
        legend.dy = 7
        legend.deltay = 10
        drawing.add(legend)

        figures.append(
            (
                "Figure 2. Min / Mean / Max Profile (Top 6 by Sample Count)",
                drawing,
                "Statistical profile derived from persisted snapshots. Use with detailed table for exact values and units.",
            )
        )

    return figures


def _strip_markdown(text: str) -> str:
    """
    Very lightweight markdown stripper for PDF rendering.
    Removes common markdown syntax that would look odd in plain PDF text.
    """
    # Remove headers (## Title -> Title)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic (**text** -> text, *text* -> text)
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    # Remove inline code (`code` -> code)
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove bullet list markers (- item or * item)
    text = re.sub(r"^\s*[-*+]\s+", "- ", text, flags=re.MULTILINE)
    # Remove numbered list markers (1. item)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _sanitize_pdf_text(text)


def _parse_markdown_blocks(text: str) -> list:
    """
    Parse markdown text into a list of typed blocks:
      {"type": "heading", "level": 2, "text": "..."}  — ## headings
      {"type": "table",   "rows": [[...], ...]}  — GFM pipe tables
      {"type": "text",    "text": "..."}  — everything else (paragraphs)
    """
    blocks = []
    lines = text.split("\n")
    i = 0
    current_text_lines: list[str] = []

    def flush_text():
        chunk = "\n".join(current_text_lines).strip()
        if chunk:
            # Apply inline markdown stripping before adding
            chunk = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", chunk)
            chunk = re.sub(r"`(.+?)`", r"\1", chunk)
            chunk = re.sub(r"^\s*[-*+]\s+", "- ", chunk, flags=re.MULTILINE)
            chunk = re.sub(r"^\s*\d+\.\s+", "", chunk, flags=re.MULTILINE)
            for para in re.split(r"\n{2,}", chunk):
                para = _sanitize_pdf_text(para.strip())
                if para:
                    blocks.append({"type": "text", "text": para})
        current_text_lines.clear()

    while i < len(lines):
        line = lines[i]

        # Detect heading
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            flush_text()
            blocks.append(
                {
                    "type": "heading",
                    "level": len(heading_match.group(1)),
                    "text": _sanitize_pdf_text(heading_match.group(2).strip()),
                }
            )
            i += 1
            continue

        # Detect start of a pipe table (line contains | and next line is separator)
        if "|" in line and i + 1 < len(lines) and re.match(r"^[|\s:|-]+$", lines[i + 1]):
            flush_text()
            table_lines = [line]
            i += 1  # skip separator row
            i += 1
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            # Parse rows
            rows = []
            for tl in table_lines:
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            if rows:
                blocks.append({"type": "table", "rows": rows})
            continue

        current_text_lines.append(line)
        i += 1

    flush_text()
    return blocks


def _build_markdown_table(rows: list, styles) -> object | None:
    """
    Build a reportlab Table from parsed markdown table rows.
    The first row is treated as the header.
    Column widths are distributed evenly across the 17cm usable page width.
    """
    if not rows:
        return None
    try:
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, Table, TableStyle
    except ImportError:
        return None

    n_cols = max(len(r) for r in rows)
    usable_width = 17 * cm
    col_w = usable_width / n_cols

    cell_style = ParagraphStyle(
        "MdTableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica",
        wordWrap="CJK",
    )
    hdr_style = ParagraphStyle(
        "MdTableHdr",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        wordWrap="CJK",
    )

    table_data = []
    for r_idx, row in enumerate(rows):
        # Pad short rows
        padded = row + [""] * (n_cols - len(row))
        style = hdr_style if r_idx == 0 else cell_style
        table_data.append([Paragraph(_sanitize_pdf_text(str(c)), style) for c in padded])

    tbl = Table(table_data, colWidths=[col_w] * n_cols, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d6e5")),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
    ]))
    return tbl


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _user_to_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at.isoformat() if user.created_at else "",
        updated_at=user.updated_at.isoformat() if user.updated_at else None,
    )
