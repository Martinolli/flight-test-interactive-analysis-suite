"""
FTIAS Backend - Admin Router
Superuser-only endpoints:
  - User management (list, update role/password, delete)
  - PDF report export for AI Analysis results
"""

import io
import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_superuser, get_password_hash
from app.database import get_db
from app.models import DataPoint, Document, FlightTest, TestParameter, User

logger = logging.getLogger(__name__)

router = APIRouter()


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
    analysis_text: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Generate and stream a PDF report for a flight test AI analysis.
    The `analysis_text` query parameter carries the AI-generated analysis
    (URL-encoded) so the frontend can pass it without a separate DB store.
    """
    ft = db.query(FlightTest).filter(FlightTest.id == flight_test_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Flight test not found.")

    # Compute parameter statistics
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

    pdf_bytes = _build_pdf(
        flight_test=ft,
        stats_rows=stats_rows,
        analysis_text=analysis_text,
        generated_by=current_user.full_name or current_user.username,
    )

    filename = f"FTIAS_Report_{ft.test_name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
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
    analysis_text: str = ""


@router.post("/flight-tests/{flight_test_id}/report.pdf")
def export_ai_analysis_pdf_post(
    flight_test_id: int,
    body: PDFReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    POST variant of the PDF export endpoint.
    Accepts the AI analysis text in the request body to avoid URL length limits.
    """
    ft = db.query(FlightTest).filter(FlightTest.id == flight_test_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Flight test not found.")

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

    pdf_bytes = _build_pdf(
        flight_test=ft,
        stats_rows=stats_rows,
        analysis_text=body.analysis_text,
        generated_by=current_user.full_name or current_user.username,
    )

    filename = f"FTIAS_Report_{ft.test_name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
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
    stats_rows,
    analysis_text: str,
    generated_by: str,
) -> bytes:
    """
    Build a formatted PDF report using reportlab.
    Structure:
      - Header: FTIAS logo text + report title
      - Metadata block: Flight ID, aircraft, date, generated by, timestamp
      - Section 1: AI Analysis (markdown-stripped plain text)
      - Annex A: Parameter Statistics table
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
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
        title=f"FTIAS Report — {flight_test.test_name}",
        author="FTIAS",
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        "FTIASHeader",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#1e3a5f"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    sub_header_style = ParagraphStyle(
        "FTIASSubHeader",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#4a6fa5"),
        spaceAfter=12,
        fontName="Helvetica",
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1e3a5f"),
        spaceBefore=16,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        fontName="Helvetica",
    )
    meta_value_style = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1a1a1a"),
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
    annex_title_style = ParagraphStyle(
        "AnnexTitle",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1e3a5f"),
        spaceBefore=24,
        spaceAfter=8,
        fontName="Helvetica-Bold",
    )

    story = []

    # ---- Header ----
    story.append(Paragraph("FTIAS", header_style))
    story.append(Paragraph("Flight Test Interactive Analysis Suite", sub_header_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f")))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("AI Analysis Report", section_title_style))
    story.append(Spacer(1, 0.2 * cm))

    # ---- Metadata block ----
    test_date_str = (
        flight_test.test_date.strftime("%Y-%m-%d") if flight_test.test_date else "Not specified"
    )
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    meta_data = [
        ["Flight Test ID", str(flight_test.id), "Test Name", flight_test.test_name],
        ["Aircraft Type", flight_test.aircraft_type or "Not specified", "Test Date", test_date_str],
        ["Generated By", generated_by, "Generated At", generated_at],
    ]

    meta_table = Table(meta_data, colWidths=[3 * cm, 7 * cm, 3 * cm, 4 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#666666")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#666666")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (3, 0), (3, -1), colors.HexColor("#1a1a1a")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d6e5")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0f4f8"), colors.HexColor("#e8eef5")]),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))

    # ---- Description ----
    if flight_test.description:
        story.append(Paragraph("Description", section_title_style))
        story.append(Paragraph(_strip_markdown(flight_test.description), body_style))

    # ---- Section 1: AI Analysis ----
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c8d6e5")))
    story.append(Paragraph("AI Analysis", section_title_style))

    if analysis_text:
        # Split into paragraphs and render each
        for para in _strip_markdown(analysis_text).split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para, body_style))
    else:
        story.append(Paragraph(
            "No analysis text provided. Generate an AI Analysis from the Flight Test Detail page first.",
            body_style,
        ))

    # ---- Annex A: Parameter Statistics ----
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c8d6e5")))
    story.append(Paragraph("Annex A — Parameter Statistics", annex_title_style))

    if stats_rows:
        table_data = [["Parameter", "Unit", "Min", "Max", "Mean", "Std Dev", "Samples"]]
        for row in stats_rows:
            table_data.append([
                row.name,
                row.unit or "—",
                f"{row.min_val:.3f}",
                f"{row.max_val:.3f}",
                f"{row.avg_val:.3f}",
                f"{(row.std_val or 0):.3f}",
                str(row.sample_count),
            ])

        col_widths = [5.5 * cm, 2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 1.7 * cm]
        stats_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        stats_table.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            # Data rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d6e5")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ]))
        story.append(stats_table)
    else:
        story.append(Paragraph("No parameter data available for this flight test.", body_style))

    # ---- Footer note ----
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c8d6e5")))
    story.append(Paragraph(
        f"This report was automatically generated by FTIAS on {generated_at}. "
        "AI-generated analysis is for reference purposes only and should be reviewed "
        "by a qualified flight test engineer.",
        ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            spaceBefore=4,
            fontName="Helvetica-Oblique",
        ),
    ))

    doc.build(story)
    return buffer.getvalue()


def _strip_markdown(text: str) -> str:
    """
    Very lightweight markdown stripper for PDF rendering.
    Removes common markdown syntax that would look odd in plain PDF text.
    """
    import re
    # Remove headers (## Title -> Title)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic (**text** -> text, *text* -> text)
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    # Remove inline code (`code` -> code)
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove bullet list markers (- item or * item)
    text = re.sub(r"^\s*[-*+]\s+", "• ", text, flags=re.MULTILINE)
    # Remove numbered list markers (1. item)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
