"""
FTIAS Backend - FRAT / Mission Risk Router
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analysis_controls import parse_analysis_controls
from app.analysis_modes import get_analysis_mode_definition
from app.auth import get_current_user
from app.database import get_db
from app.frat import (
    FRAT_ALLOWED_TRANSITIONS,
    FRAT_STATUS_APPROVED,
    FRAT_STATUS_DRAFT,
    FRAT_STATUS_FINALIZED,
    FRAT_STATUS_NEEDS_REVIEW,
    FRAT_STATUS_REJECTED,
    FRAT_STATUS_SCORED,
    compute_frat_score,
    normalize_frat_inputs,
)
from app.models import AnalysisJob, DatasetVersion, FlightTest, FratAssessment, User

router = APIRouter()

PROMPT_MODE_PATTERN = re.compile(
    r"^\[analysis_mode:(?P<mode>[a-z_]+)\]\s*(?P<prompt>.*)$",
    re.IGNORECASE | re.DOTALL,
)


class FratAssessmentOut(BaseModel):
    id: int
    flight_test_id: int
    dataset_version_id: Optional[int] = None
    assessment_name: Optional[str] = None
    status: str
    analysis_reference_ids: List[int] = Field(default_factory=list)
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    score_snapshot: Dict[str, Any] = Field(default_factory=dict)
    hard_stop_snapshot: List[Dict[str, Any]] = Field(default_factory=list)
    approval_notes: Optional[str] = None
    approved_by_id: Optional[int] = None
    approved_at: Optional[str] = None
    rejected_by_id: Optional[int] = None
    rejected_at: Optional[str] = None
    finalized_by_id: Optional[int] = None
    finalized_at: Optional[str] = None
    created_by_id: int
    created_at: str
    updated_at: Optional[str] = None


class FratAssessmentCreateRequest(BaseModel):
    flight_test_id: int
    dataset_version_id: Optional[int] = None
    assessment_name: Optional[str] = None
    analysis_job_ids: List[int] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)


class FratAssessmentUpdateRequest(BaseModel):
    dataset_version_id: Optional[int] = None
    assessment_name: Optional[str] = None
    analysis_job_ids: Optional[List[int]] = None
    inputs: Optional[Dict[str, Any]] = None


class FratTransitionRequest(BaseModel):
    notes: Optional[str] = None


class FratAnalysisJobReferenceOut(BaseModel):
    id: int
    analysis_mode: str
    capability_key: Optional[str] = None
    dataset_version_id: Optional[int] = None
    model_name: Optional[str] = None
    status: str
    created_at: str


def _safe_json_load(raw: Optional[str], default: Any):
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except Exception:
        return default
    return value


def _serialize_assessment(assessment: FratAssessment) -> FratAssessmentOut:
    analysis_reference_ids = _safe_json_load(assessment.analysis_reference_ids_json, [])
    if not isinstance(analysis_reference_ids, list):
        analysis_reference_ids = []
    input_snapshot = _safe_json_load(assessment.input_snapshot_json, {})
    if not isinstance(input_snapshot, dict):
        input_snapshot = {}
    score_snapshot = _safe_json_load(assessment.score_snapshot_json, {})
    if not isinstance(score_snapshot, dict):
        score_snapshot = {}
    hard_stop_snapshot = _safe_json_load(assessment.hard_stop_snapshot_json, [])
    if not isinstance(hard_stop_snapshot, list):
        hard_stop_snapshot = []

    return FratAssessmentOut(
        id=assessment.id,
        flight_test_id=assessment.flight_test_id,
        dataset_version_id=assessment.dataset_version_id,
        assessment_name=assessment.assessment_name,
        status=assessment.status,
        analysis_reference_ids=[int(item) for item in analysis_reference_ids if str(item).isdigit()],
        input_snapshot=input_snapshot,
        score_snapshot=score_snapshot,
        hard_stop_snapshot=[item for item in hard_stop_snapshot if isinstance(item, dict)],
        approval_notes=assessment.approval_notes,
        approved_by_id=assessment.approved_by_id,
        approved_at=assessment.approved_at.isoformat() if assessment.approved_at else None,
        rejected_by_id=assessment.rejected_by_id,
        rejected_at=assessment.rejected_at.isoformat() if assessment.rejected_at else None,
        finalized_by_id=assessment.finalized_by_id,
        finalized_at=assessment.finalized_at.isoformat() if assessment.finalized_at else None,
        created_by_id=assessment.created_by_id,
        created_at=assessment.created_at.isoformat() if assessment.created_at else "",
        updated_at=assessment.updated_at.isoformat() if assessment.updated_at else None,
    )


def _decode_prompt_mode(prompt_text: str) -> str:
    raw = (prompt_text or "").strip()
    if not raw:
        return "takeoff"
    match = PROMPT_MODE_PATTERN.match(raw)
    if not match:
        return "takeoff"
    return (match.group("mode") or "takeoff").strip().lower()


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
        raise HTTPException(status_code=404, detail="Flight test not found")
    return flight_test


def _get_accessible_assessment(
    *,
    db: Session,
    assessment_id: int,
    current_user: User,
) -> FratAssessment:
    query = db.query(FratAssessment).join(FlightTest, FlightTest.id == FratAssessment.flight_test_id)
    query = query.filter(FratAssessment.id == assessment_id)
    if not current_user.is_superuser:
        query = query.filter(FlightTest.created_by_id == current_user.id)
    assessment = query.first()
    if not assessment:
        raise HTTPException(status_code=404, detail="FRAT assessment not found")
    return assessment


def _assert_assessment_mutable(assessment: FratAssessment):
    if assessment.status == FRAT_STATUS_FINALIZED:
        raise HTTPException(
            status_code=400,
            detail="Finalized FRAT assessments are immutable.",
        )


def _validate_dataset_version_link(
    *,
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int],
) -> Optional[int]:
    if dataset_version_id is None:
        return None
    version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.id == dataset_version_id,
            DatasetVersion.flight_test_id == flight_test_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found for this flight test")
    return version.id


def _load_analysis_controls_for_assessment(
    *,
    db: Session,
    flight_test_id: int,
    analysis_job_ids: List[int],
) -> List[dict]:
    if not analysis_job_ids:
        return []
    rows = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.flight_test_id == flight_test_id,
            AnalysisJob.id.in_(analysis_job_ids),
        )
        .all()
    )
    controls: List[dict] = []
    for job in rows:
        payload = _safe_json_load(getattr(job, "analysis_controls_json", "{}"), {})
        if not isinstance(payload, dict):
            payload = {}
        controls.append(parse_analysis_controls(payload).model_dump())
    return controls


def _score_and_persist(
    *,
    db: Session,
    assessment: FratAssessment,
):
    analysis_reference_ids = _safe_json_load(assessment.analysis_reference_ids_json, [])
    if not isinstance(analysis_reference_ids, list):
        analysis_reference_ids = []
    parsed_ids = [int(item) for item in analysis_reference_ids if str(item).isdigit()]
    inputs = normalize_frat_inputs(_safe_json_load(assessment.input_snapshot_json, {}))
    analysis_controls = _load_analysis_controls_for_assessment(
        db=db,
        flight_test_id=assessment.flight_test_id,
        analysis_job_ids=parsed_ids,
    )
    score = compute_frat_score(
        inputs=inputs,
        analysis_controls=analysis_controls,
    )
    assessment.score_snapshot_json = json.dumps(score)
    assessment.hard_stop_snapshot_json = json.dumps(score.get("hard_stops") or [])
    if score.get("hard_stop_triggered") or score.get("recommendation") != "go":
        assessment.status = FRAT_STATUS_NEEDS_REVIEW
    else:
        assessment.status = FRAT_STATUS_SCORED
    db.add(assessment)
    db.commit()
    db.refresh(assessment)


def _assert_transition_allowed(current_status: str, target_status: str):
    allowed = FRAT_ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid FRAT transition from '{current_status}' to '{target_status}'.",
        )


def _build_frat_pdf(
    *,
    finalized_snapshot: dict,
    generated_by: str,
) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "reportlab is not installed. Add 'reportlab>=4.0' to requirements.txt "
                "to enable FRAT PDF export."
            ),
        ) from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("FTIAS FRAT / Mission Risk Assessment", styles["Title"]))
    story.append(Paragraph(f"Generated by: {generated_by}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * cm))

    summary = finalized_snapshot.get("summary") or {}
    summary_rows = [
        ["Assessment ID", str(summary.get("assessment_id") or "—")],
        ["Status", str(summary.get("status") or "—")],
        ["Flight Test ID", str(summary.get("flight_test_id") or "—")],
        ["Dataset Version ID", str(summary.get("dataset_version_id") or "—")],
        ["Total Score", str(summary.get("total_score") or "—")],
        ["Risk Band", str(summary.get("risk_band") or "—")],
        ["Recommendation", str(summary.get("recommendation") or "—")],
        ["Hard-Stop Triggered", str(bool(summary.get("hard_stop_triggered")))],
        ["Finalized At", str(summary.get("finalized_at") or "—")],
    ]
    summary_table = Table(summary_rows, colWidths=[5.2 * cm, 10.5 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.2 * cm))

    category_scores = (finalized_snapshot.get("score_snapshot") or {}).get("category_scores") or {}
    if category_scores:
        story.append(Paragraph("Category Scores", styles["Heading2"]))
        score_rows = [["Category", "Score"]]
        for key, value in category_scores.items():
            score_rows.append([str(key), str(value)])
        score_table = Table(score_rows, colWidths=[10 * cm, 5.7 * cm])
        score_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0f7")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(score_table)
        story.append(Spacer(1, 0.2 * cm))

    hard_stops = finalized_snapshot.get("hard_stop_snapshot") or []
    story.append(Paragraph("Hard-Stops", styles["Heading2"]))
    if hard_stops:
        for item in hard_stops:
            story.append(
                Paragraph(
                    f"- [{item.get('severity', 'info')}] {item.get('code', 'unknown')}: {item.get('message', '')}",
                    styles["Normal"],
                )
            )
    else:
        story.append(Paragraph("- None", styles["Normal"]))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("Engineering Notice", styles["Heading2"]))
    story.append(
        Paragraph(
            (
                "This FRAT artifact is a deterministic mission-risk workflow aid. "
                "It does not replace formal certification, release authority, or operational command judgement."
            ),
            styles["Normal"],
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


@router.post("/assessments", response_model=FratAssessmentOut, status_code=status.HTTP_201_CREATED)
def create_frat_assessment(
    body: FratAssessmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    flight_test = _get_accessible_flight_test(
        db=db,
        flight_test_id=body.flight_test_id,
        current_user=current_user,
    )
    dataset_version_id = _validate_dataset_version_link(
        db=db,
        flight_test_id=flight_test.id,
        dataset_version_id=body.dataset_version_id,
    )
    inputs = normalize_frat_inputs(body.inputs)
    analysis_ids = sorted({int(item) for item in body.analysis_job_ids if int(item) > 0})

    assessment = FratAssessment(
        flight_test_id=flight_test.id,
        dataset_version_id=dataset_version_id,
        created_by_id=current_user.id,
        status=FRAT_STATUS_DRAFT,
        assessment_name=(body.assessment_name or "").strip()[:255] or None,
        analysis_reference_ids_json=json.dumps(analysis_ids),
        input_snapshot_json=json.dumps(inputs),
        score_snapshot_json=json.dumps({}),
        hard_stop_snapshot_json=json.dumps([]),
        finalized_snapshot_json=json.dumps({}),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment)


@router.get("/flight-tests/{flight_test_id}/assessments", response_model=List[FratAssessmentOut])
def list_frat_assessments(
    flight_test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_accessible_flight_test(
        db=db,
        flight_test_id=flight_test_id,
        current_user=current_user,
    )
    query = db.query(FratAssessment).filter(FratAssessment.flight_test_id == flight_test_id)
    if not current_user.is_superuser:
        query = query.filter(FratAssessment.created_by_id == current_user.id)
    rows = query.order_by(FratAssessment.created_at.desc(), FratAssessment.id.desc()).all()
    return [_serialize_assessment(item) for item in rows]


@router.get(
    "/flight-tests/{flight_test_id}/analysis-jobs",
    response_model=List[FratAnalysisJobReferenceOut],
)
def list_flight_test_analysis_jobs(
    flight_test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_accessible_flight_test(
        db=db,
        flight_test_id=flight_test_id,
        current_user=current_user,
    )
    query = db.query(AnalysisJob).filter(AnalysisJob.flight_test_id == flight_test_id)
    if not current_user.is_superuser:
        query = query.filter(AnalysisJob.created_by_id == current_user.id)
    rows = (
        query.order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .limit(50)
        .all()
    )
    response_items: List[FratAnalysisJobReferenceOut] = []
    for row in rows:
        mode_key = _decode_prompt_mode(row.prompt_text or "")
        mode_def = get_analysis_mode_definition(mode_key)
        response_items.append(
            FratAnalysisJobReferenceOut(
                id=row.id,
                analysis_mode=mode_key,
                capability_key=mode_def.capability_key if mode_def else None,
                dataset_version_id=row.dataset_version_id,
                model_name=row.model_name,
                status=row.status,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
        )
    return response_items


@router.get("/assessments/{assessment_id}", response_model=FratAssessmentOut)
def get_frat_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    return _serialize_assessment(assessment)


@router.put("/assessments/{assessment_id}", response_model=FratAssessmentOut)
def update_frat_assessment(
    assessment_id: int,
    body: FratAssessmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    _assert_assessment_mutable(assessment)

    if body.dataset_version_id is not None:
        assessment.dataset_version_id = _validate_dataset_version_link(
            db=db,
            flight_test_id=assessment.flight_test_id,
            dataset_version_id=body.dataset_version_id,
        )
    if body.assessment_name is not None:
        assessment.assessment_name = body.assessment_name.strip()[:255] or None
    if body.analysis_job_ids is not None:
        analysis_ids = sorted({int(item) for item in body.analysis_job_ids if int(item) > 0})
        assessment.analysis_reference_ids_json = json.dumps(analysis_ids)
    if body.inputs is not None:
        assessment.input_snapshot_json = json.dumps(normalize_frat_inputs(body.inputs))

    if assessment.status in {
        FRAT_STATUS_SCORED,
        FRAT_STATUS_NEEDS_REVIEW,
        FRAT_STATUS_REJECTED,
        FRAT_STATUS_APPROVED,
    }:
        assessment.status = FRAT_STATUS_DRAFT
        assessment.score_snapshot_json = json.dumps({})
        assessment.hard_stop_snapshot_json = json.dumps([])
        assessment.approved_by_id = None
        assessment.approved_at = None
        assessment.rejected_by_id = None
        assessment.rejected_at = None
        assessment.approval_notes = None

    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment)


@router.post("/assessments/{assessment_id}/score", response_model=FratAssessmentOut)
def score_frat_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    _assert_assessment_mutable(assessment)
    if assessment.status == FRAT_STATUS_APPROVED:
        raise HTTPException(status_code=400, detail="Approved assessments must be rejected or finalized before rescoring.")
    _score_and_persist(
        db=db,
        assessment=assessment,
    )
    return _serialize_assessment(assessment)


@router.post("/assessments/{assessment_id}/approve", response_model=FratAssessmentOut)
def approve_frat_assessment(
    assessment_id: int,
    body: Optional[FratTransitionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    _assert_assessment_mutable(assessment)
    _assert_transition_allowed(assessment.status, FRAT_STATUS_APPROVED)

    score = _safe_json_load(assessment.score_snapshot_json, {})
    if not isinstance(score, dict) or not score:
        raise HTTPException(status_code=400, detail="Assessment must be scored before approval.")
    if bool(score.get("hard_stop_triggered")):
        raise HTTPException(status_code=400, detail="Assessment has hard-stops and cannot be approved.")
    if str(score.get("recommendation")) != "go":
        raise HTTPException(status_code=400, detail="Only go-recommended assessments can be approved.")

    assessment.status = FRAT_STATUS_APPROVED
    assessment.approved_by_id = current_user.id
    assessment.approved_at = datetime.utcnow()
    notes = (body.notes if body else "") or ""
    assessment.approval_notes = notes.strip()[:2000] or None
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment)


@router.post("/assessments/{assessment_id}/reject", response_model=FratAssessmentOut)
def reject_frat_assessment(
    assessment_id: int,
    body: Optional[FratTransitionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    _assert_assessment_mutable(assessment)
    _assert_transition_allowed(assessment.status, FRAT_STATUS_REJECTED)

    assessment.status = FRAT_STATUS_REJECTED
    assessment.rejected_by_id = current_user.id
    assessment.rejected_at = datetime.utcnow()
    notes = (body.notes if body else "") or ""
    assessment.approval_notes = notes.strip()[:2000] or assessment.approval_notes
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment)


@router.post("/assessments/{assessment_id}/finalize", response_model=FratAssessmentOut)
def finalize_frat_assessment(
    assessment_id: int,
    body: Optional[FratTransitionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    _assert_assessment_mutable(assessment)
    _assert_transition_allowed(assessment.status, FRAT_STATUS_FINALIZED)

    score = _safe_json_load(assessment.score_snapshot_json, {})
    hard_stops = _safe_json_load(assessment.hard_stop_snapshot_json, [])
    if not isinstance(score, dict) or not score:
        raise HTTPException(status_code=400, detail="Assessment must be scored before finalization.")
    if bool(score.get("hard_stop_triggered")):
        raise HTTPException(status_code=400, detail="Assessment has hard-stops and cannot be finalized.")
    if str(score.get("recommendation")) != "go":
        raise HTTPException(status_code=400, detail="Only go-recommended assessments can be finalized.")
    if assessment.approved_by_id is None:
        raise HTTPException(status_code=400, detail="Assessment must be approved before finalization.")

    now = datetime.utcnow()
    assessment.status = FRAT_STATUS_FINALIZED
    assessment.finalized_by_id = current_user.id
    assessment.finalized_at = now
    notes = (body.notes if body else "") or ""
    if notes.strip():
        assessment.approval_notes = notes.strip()[:2000]

    finalized_snapshot = {
        "summary": {
            "assessment_id": assessment.id,
            "status": assessment.status,
            "flight_test_id": assessment.flight_test_id,
            "dataset_version_id": assessment.dataset_version_id,
            "total_score": score.get("total_score"),
            "risk_band": score.get("risk_band"),
            "recommendation": score.get("recommendation"),
            "hard_stop_triggered": bool(score.get("hard_stop_triggered")),
            "approved_by_id": assessment.approved_by_id,
            "finalized_by_id": assessment.finalized_by_id,
            "finalized_at": now.isoformat(),
        },
        "analysis_reference_ids": _safe_json_load(assessment.analysis_reference_ids_json, []),
        "input_snapshot": _safe_json_load(assessment.input_snapshot_json, {}),
        "score_snapshot": score,
        "hard_stop_snapshot": hard_stops if isinstance(hard_stops, list) else [],
        "approval_notes": assessment.approval_notes,
    }
    assessment.finalized_snapshot_json = json.dumps(finalized_snapshot)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment)


@router.get("/assessments/{assessment_id}/report.pdf")
def export_frat_assessment_pdf(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = _get_accessible_assessment(
        db=db,
        assessment_id=assessment_id,
        current_user=current_user,
    )
    if assessment.status != FRAT_STATUS_FINALIZED:
        raise HTTPException(status_code=400, detail="Only finalized FRAT assessments can be exported.")

    finalized_snapshot = _safe_json_load(assessment.finalized_snapshot_json, {})
    if not isinstance(finalized_snapshot, dict) or not finalized_snapshot:
        raise HTTPException(status_code=500, detail="Finalized snapshot is missing.")

    pdf_bytes = _build_frat_pdf(
        finalized_snapshot=finalized_snapshot,
        generated_by=current_user.username,
    )
    filename = f"FRAT_{assessment.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
