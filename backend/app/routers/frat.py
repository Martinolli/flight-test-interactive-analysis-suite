"""
FTIAS Backend - FRAT / Mission Risk Router
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from html import escape
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
    CATEGORY_KEYS,
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

CATEGORY_LABELS = {
    "mission_profile": "Mission/Test Profile",
    "weather_environment": "Weather/Environment",
    "runway_operational": "Runway/Operational",
    "aircraft_system_status": "Aircraft System Status",
    "crew_readiness": "Crew Readiness",
}

NO_LINKED_ANALYSIS_STATEMENT = (
    "No linked analysis job is available. This FRAT result is based on category scoring, "
    "manual adjustment, and hard-stop flags only. Technical analysis evidence was not included."
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
    decision_explanation: Dict[str, Any] = Field(default_factory=dict)
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


def _clean_digits(raw_items: Any) -> List[int]:
    if not isinstance(raw_items, list):
        return []
    return [int(item) for item in raw_items if str(item).isdigit()]


def _category_breakdown(score_snapshot: dict) -> List[Dict[str, Any]]:
    category_scores = score_snapshot.get("category_scores") or {}
    if not isinstance(category_scores, dict):
        category_scores = {}
    return [
        {
            "key": key,
            "label": CATEGORY_LABELS.get(key, key),
            "base_score": int(category_scores.get(key) or 0),
        }
        for key in CATEGORY_KEYS
    ]


def _risk_band_requires_review(risk_band: str) -> bool:
    return risk_band in {"moderate", "high", "unacceptable"}


def _load_analysis_jobs_for_assessment(
    *,
    db: Session,
    flight_test_id: int,
    analysis_job_ids: List[int],
) -> List[AnalysisJob]:
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
    by_id = {row.id: row for row in rows}
    return [by_id[item] for item in analysis_job_ids if item in by_id]


def _analysis_controls_summary(analysis_jobs: List[AnalysisJob]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for job in analysis_jobs:
        payload = _safe_json_load(getattr(job, "analysis_controls_json", "{}"), {})
        if not isinstance(payload, dict):
            payload = {}
        controls = parse_analysis_controls(payload).model_dump()
        summary.append(
            {
                "analysis_job_id": job.id,
                "analysis_mode": _decode_prompt_mode(job.prompt_text or ""),
                "dataset_version_id": job.dataset_version_id,
                "status": job.status,
                "result_strength": controls.get("result_strength"),
                "warning_level": controls.get("warning_level"),
                "applicability_status": controls.get("applicability_status"),
                "retrieval_coverage": controls.get("retrieval_coverage"),
                "deterministic_confidence": controls.get("deterministic_confidence"),
                "blocking_or_downgrade_reason": controls.get("blocking_or_downgrade_reason"),
                "warning_messages": controls.get("warning_messages") or [],
            }
        )
    return summary


def _dominant_risk_drivers(
    *,
    score_snapshot: dict,
    hard_stops: List[dict],
    has_linked_analysis: bool,
) -> List[Dict[str, Any]]:
    drivers: List[Dict[str, Any]] = []
    for item in hard_stops:
        drivers.append(
            {
                "type": "hard_stop",
                "label": str(item.get("code") or "hard_stop"),
                "score": None,
                "reason": str(item.get("message") or "Hard-stop condition is active."),
            }
        )

    for item in sorted(
        _category_breakdown(score_snapshot),
        key=lambda row: int(row.get("base_score") or 0),
        reverse=True,
    )[:3]:
        if int(item.get("base_score") or 0) <= 0:
            continue
        drivers.append(
            {
                "type": "category",
                "label": item["label"],
                "score": item["base_score"],
                "reason": f"{item['label']} contributes {item['base_score']} category points.",
            }
        )

    analysis_indicator_score = int(score_snapshot.get("analysis_indicator_score") or 0)
    if analysis_indicator_score > 0:
        drivers.append(
            {
                "type": "linked_analysis_penalty",
                "label": "Linked Analysis Controls",
                "score": analysis_indicator_score,
                "reason": (
                    f"Linked-analysis controls add {analysis_indicator_score} points "
                    "to the FRAT score composition."
                ),
            }
        )

    risk_band = str(score_snapshot.get("risk_band") or "")
    if not has_linked_analysis and _risk_band_requires_review(risk_band):
        drivers.append(
            {
                "type": "missing_analysis_evidence",
                "label": "No Linked Analysis Evidence",
                "score": None,
                "reason": "Moderate or higher score has no linked technical analysis evidence attached.",
            }
        )

    return drivers


def _decision_driver_types(
    *,
    score_snapshot: dict,
    hard_stops: List[dict],
    has_linked_analysis: bool,
) -> List[str]:
    drivers: List[str] = []
    if hard_stops or bool(score_snapshot.get("hard_stop_triggered")):
        drivers.append("hard_stop")
    if (
        str(score_snapshot.get("recommendation") or "") != "go"
        or str(score_snapshot.get("risk_band") or "") != "low"
    ):
        drivers.append("score_band")
    if int(score_snapshot.get("analysis_indicator_score") or 0) > 0:
        drivers.append("linked_analysis_penalty")
    if not has_linked_analysis and _risk_band_requires_review(
        str(score_snapshot.get("risk_band") or "")
    ):
        drivers.append("missing_analysis_evidence")
    return drivers


def _recommended_next_actions(driver_types: List[str]) -> List[str]:
    actions: List[str] = []
    if "score_band" in driver_types or "linked_analysis_penalty" in driver_types:
        actions.append("Mitigate and rescore.")
    if "missing_analysis_evidence" in driver_types:
        actions.append("Attach supporting analysis.")
    if "hard_stop" in driver_types:
        actions.append("Resolve hard-stop.")
    if driver_types:
        actions.append("Document formal acceptance if organizational authority allows it.")
    return actions or ["Proceed under the approved organizational FRAT workflow."]


def _build_decision_explanation(
    *,
    db: Optional[Session],
    assessment: FratAssessment,
    score_snapshot: dict,
    hard_stop_snapshot: List[dict],
) -> Dict[str, Any]:
    analysis_reference_ids = _clean_digits(
        _safe_json_load(assessment.analysis_reference_ids_json, [])
    )
    analysis_jobs = (
        _load_analysis_jobs_for_assessment(
            db=db,
            flight_test_id=assessment.flight_test_id,
            analysis_job_ids=analysis_reference_ids,
        )
        if db is not None
        else []
    )
    has_linked_analysis = (
        len(analysis_jobs) > 0 if db is not None else len(analysis_reference_ids) > 0
    )

    dataset_version_label = None
    if db is not None and assessment.dataset_version_id is not None:
        dataset = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.id == assessment.dataset_version_id)
            .first()
        )
        if dataset:
            dataset_version_label = dataset.label

    inputs = normalize_frat_inputs(_safe_json_load(assessment.input_snapshot_json, {}))
    risk_band = str(score_snapshot.get("risk_band") or "")
    recommendation = str(score_snapshot.get("recommendation") or "")
    driver_types = _decision_driver_types(
        score_snapshot=score_snapshot,
        hard_stops=hard_stop_snapshot,
        has_linked_analysis=has_linked_analysis,
    )
    no_linked_analysis_warning = (
        "Review required: score is moderate or higher and no linked analysis evidence is attached."
        if not has_linked_analysis and _risk_band_requires_review(risk_band)
        else None
    )

    why_not_acceptable: List[str] = []
    if assessment.status in {FRAT_STATUS_REJECTED, FRAT_STATUS_NEEDS_REVIEW}:
        why_not_acceptable.append(f"Lifecycle state is {assessment.status}.")
    if recommendation == "no_go" or risk_band == "unacceptable":
        why_not_acceptable.append("Decision outcome is no-go/unacceptable.")
    elif recommendation == "review" or risk_band in {"moderate", "high"}:
        why_not_acceptable.append("Decision outcome requires review before acceptance.")
    if hard_stop_snapshot:
        why_not_acceptable.append("One or more hard-stops are active.")
    if no_linked_analysis_warning:
        why_not_acceptable.append(no_linked_analysis_warning)

    return {
        "assessment": {
            "id": assessment.id,
            "name": assessment.assessment_name,
            "flight_test_id": assessment.flight_test_id,
        },
        "lifecycle_state": assessment.status,
        "dataset_version": {
            "id": assessment.dataset_version_id,
            "label": dataset_version_label,
        },
        "linked_analysis_job_ids": analysis_reference_ids,
        "linked_analysis_job_id": analysis_reference_ids[0] if analysis_reference_ids else None,
        "score_composition": {
            "categories": _category_breakdown(score_snapshot),
            "base_score": int(score_snapshot.get("base_score") or 0),
            "manual_adjustment": int(score_snapshot.get("manual_adjustment") or 0),
            "analysis_indicator_score": int(score_snapshot.get("analysis_indicator_score") or 0),
            "final_total_score": score_snapshot.get("total_score"),
            "risk_band": risk_band or None,
            "recommendation": recommendation or None,
        },
        "hard_stops": {
            "triggered": bool(score_snapshot.get("hard_stop_triggered"))
            or bool(hard_stop_snapshot),
            "flags": [str(item.get("code") or "hard_stop") for item in hard_stop_snapshot],
            "reasons": [
                str(item.get("message") or "") for item in hard_stop_snapshot if item.get("message")
            ],
            "items": hard_stop_snapshot,
        },
        "linked_analysis": {
            "available": has_linked_analysis,
            "controls_summary": _analysis_controls_summary(analysis_jobs),
            "no_linked_analysis_statement": (
                None if has_linked_analysis else NO_LINKED_ANALYSIS_STATEMENT
            ),
            "warning": no_linked_analysis_warning,
        },
        "dominant_risk_drivers": _dominant_risk_drivers(
            score_snapshot=score_snapshot,
            hard_stops=hard_stop_snapshot,
            has_linked_analysis=has_linked_analysis,
        ),
        "decision": {
            "outcome": recommendation or None,
            "risk_band": risk_band or None,
            "is_acceptable": (
                assessment.status in {FRAT_STATUS_APPROVED, FRAT_STATUS_FINALIZED}
                and recommendation == "go"
                and not hard_stop_snapshot
            ),
            "why_not_acceptable": why_not_acceptable,
            "driver_types": driver_types,
            "recommended_next_actions": _recommended_next_actions(driver_types),
        },
        "notes": {
            "review_notes": inputs.get("reviewer_notes") or None,
            "override_rationale_notes": inputs.get("override_note") or None,
            "transition_notes": assessment.approval_notes,
        },
        "provenance_statement": (
            "This FRAT explanation is generated from the persisted assessment input snapshot, "
            "score snapshot, hard-stop snapshot, linked analysis-control snapshots when present, "
            "and lifecycle transition metadata."
        ),
    }


def _serialize_assessment(
    assessment: FratAssessment, db: Optional[Session] = None
) -> FratAssessmentOut:
    analysis_reference_ids = _safe_json_load(assessment.analysis_reference_ids_json, [])
    input_snapshot = _safe_json_load(assessment.input_snapshot_json, {})
    if not isinstance(input_snapshot, dict):
        input_snapshot = {}
    score_snapshot = _safe_json_load(assessment.score_snapshot_json, {})
    if not isinstance(score_snapshot, dict):
        score_snapshot = {}
    hard_stop_snapshot = _safe_json_load(assessment.hard_stop_snapshot_json, [])
    if not isinstance(hard_stop_snapshot, list):
        hard_stop_snapshot = []
    clean_hard_stops = [item for item in hard_stop_snapshot if isinstance(item, dict)]
    decision_explanation = (
        _build_decision_explanation(
            db=db,
            assessment=assessment,
            score_snapshot=score_snapshot,
            hard_stop_snapshot=clean_hard_stops,
        )
        if score_snapshot
        else {}
    )

    return FratAssessmentOut(
        id=assessment.id,
        flight_test_id=assessment.flight_test_id,
        dataset_version_id=assessment.dataset_version_id,
        assessment_name=assessment.assessment_name,
        status=assessment.status,
        analysis_reference_ids=_clean_digits(analysis_reference_ids),
        input_snapshot=input_snapshot,
        score_snapshot=score_snapshot,
        hard_stop_snapshot=clean_hard_stops,
        decision_explanation=decision_explanation,
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
    query = db.query(FratAssessment).join(
        FlightTest, FlightTest.id == FratAssessment.flight_test_id
    )
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
        raise HTTPException(
            status_code=404, detail="Dataset version not found for this flight test"
        )
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


def _assert_scored_for_export(score_snapshot: dict):
    if not isinstance(score_snapshot, dict) or not score_snapshot:
        raise HTTPException(
            status_code=400,
            detail=(
                "FRAT assessment must be scored before export. "
                "Unscored draft assessments do not have a report artifact yet."
            ),
        )


def _build_report_snapshot(
    *,
    db: Session,
    assessment: FratAssessment,
) -> Dict[str, Any]:
    score = _safe_json_load(assessment.score_snapshot_json, {})
    hard_stops = _safe_json_load(assessment.hard_stop_snapshot_json, [])
    if not isinstance(score, dict):
        score = {}
    if not isinstance(hard_stops, list):
        hard_stops = []
    clean_hard_stops = [item for item in hard_stops if isinstance(item, dict)]
    _assert_scored_for_export(score)

    explanation = _build_decision_explanation(
        db=db,
        assessment=assessment,
        score_snapshot=score,
        hard_stop_snapshot=clean_hard_stops,
    )
    return {
        "summary": {
            "assessment_id": assessment.id,
            "assessment_name": assessment.assessment_name,
            "status": assessment.status,
            "flight_test_id": assessment.flight_test_id,
            "dataset_version_id": assessment.dataset_version_id,
            "total_score": score.get("total_score"),
            "risk_band": score.get("risk_band"),
            "recommendation": score.get("recommendation"),
            "hard_stop_triggered": bool(score.get("hard_stop_triggered")),
            "approved_by_id": assessment.approved_by_id,
            "rejected_by_id": assessment.rejected_by_id,
            "finalized_by_id": assessment.finalized_by_id,
            "finalized_at": (
                assessment.finalized_at.isoformat() if assessment.finalized_at else None
            ),
            "generated_at": datetime.utcnow().isoformat(),
        },
        "analysis_reference_ids": _clean_digits(
            _safe_json_load(assessment.analysis_reference_ids_json, [])
        ),
        "input_snapshot": _safe_json_load(assessment.input_snapshot_json, {}),
        "score_snapshot": score,
        "hard_stop_snapshot": clean_hard_stops,
        "approval_notes": assessment.approval_notes,
        "decision_explanation": explanation,
    }


def _assert_transition_allowed(current_status: str, target_status: str):
    allowed = FRAT_ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid FRAT transition from '{current_status}' to '{target_status}'.",
        )


def _build_frat_pdf(
    *,
    report_snapshot: dict,
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

    summary = report_snapshot.get("summary") or {}
    explanation = report_snapshot.get("decision_explanation") or {}
    decision = explanation.get("decision") or {}
    summary_rows = [
        ["Assessment ID", str(summary.get("assessment_id") or "—")],
        ["Assessment Name", str(summary.get("assessment_name") or "—")],
        ["Status", str(summary.get("status") or "—")],
        ["Flight Test ID", str(summary.get("flight_test_id") or "—")],
        ["Dataset Version ID", str(summary.get("dataset_version_id") or "—")],
        ["Total Score", str(summary.get("total_score") or "—")],
        ["Risk Band", str(summary.get("risk_band") or "—")],
        ["Recommendation", str(summary.get("recommendation") or "—")],
        ["Acceptable", str(bool(decision.get("is_acceptable")))],
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

    score_composition = explanation.get("score_composition") or {}
    story.append(Paragraph("Decision Summary", styles["Heading2"]))
    why_not_acceptable = decision.get("why_not_acceptable") or []
    if why_not_acceptable:
        for item in why_not_acceptable:
            story.append(Paragraph(f"- {escape(str(item))}", styles["Normal"]))
    else:
        story.append(
            Paragraph(
                "- Assessment is acceptable under the recorded FRAT decision state.",
                styles["Normal"],
            )
        )
    actions = decision.get("recommended_next_actions") or []
    if actions:
        story.append(Paragraph("Recommended Next Action", styles["Heading3"]))
        for item in actions:
            story.append(Paragraph(f"- {escape(str(item))}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("Score Composition", styles["Heading2"]))
    composition_rows = [
        ["Category Base Score", str(score_composition.get("base_score") or 0)],
        ["Manual Adjustment", str(score_composition.get("manual_adjustment") or 0)],
        ["Analysis Indicator Score", str(score_composition.get("analysis_indicator_score") or 0)],
        ["Final Total Score", str(score_composition.get("final_total_score") or "—")],
        ["Risk Band", str(score_composition.get("risk_band") or "—")],
        ["Recommendation", str(score_composition.get("recommendation") or "—")],
    ]
    composition_table = Table(composition_rows, colWidths=[7 * cm, 8.7 * cm])
    composition_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(composition_table)
    story.append(Spacer(1, 0.2 * cm))

    category_breakdown = score_composition.get("categories") or []
    if category_breakdown:
        story.append(Paragraph("Category Breakdown", styles["Heading2"]))
        score_rows = [["Category", "Base Score"]]
        for item in category_breakdown:
            score_rows.append(
                [
                    escape(str(item.get("label") or item.get("key") or "Category")),
                    str(item.get("base_score") or 0),
                ]
            )
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

    hard_stops = report_snapshot.get("hard_stop_snapshot") or []
    story.append(Paragraph("Hard-Stops", styles["Heading2"]))
    if hard_stops:
        for item in hard_stops:
            story.append(
                Paragraph(
                    (
                        f"- [{escape(str(item.get('severity', 'info')))}] "
                        f"{escape(str(item.get('code', 'unknown')))}: "
                        f"{escape(str(item.get('message', '')))}"
                    ),
                    styles["Normal"],
                )
            )
    else:
        story.append(Paragraph("- None", styles["Normal"]))
    story.append(Spacer(1, 0.2 * cm))

    linked_analysis = explanation.get("linked_analysis") or {}
    story.append(Paragraph("Linked Analysis Evidence", styles["Heading2"]))
    if linked_analysis.get("available"):
        controls_rows = [["Job ID", "Mode", "Strength", "Warning", "Applicability"]]
        for item in linked_analysis.get("controls_summary") or []:
            controls_rows.append(
                [
                    str(item.get("analysis_job_id") or "—"),
                    str(item.get("analysis_mode") or "—"),
                    str(item.get("result_strength") or "—"),
                    str(item.get("warning_level") or "—"),
                    str(item.get("applicability_status") or "—"),
                ]
            )
        controls_table = Table(
            controls_rows, colWidths=[2 * cm, 3 * cm, 3.4 * cm, 3 * cm, 4.3 * cm]
        )
        controls_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0f7")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(controls_table)
    else:
        story.append(
            Paragraph(
                escape(
                    str(
                        linked_analysis.get("no_linked_analysis_statement")
                        or NO_LINKED_ANALYSIS_STATEMENT
                    )
                ),
                styles["Normal"],
            )
        )
    if linked_analysis.get("warning"):
        story.append(Paragraph(escape(str(linked_analysis.get("warning"))), styles["Normal"]))
    story.append(Spacer(1, 0.2 * cm))

    drivers = explanation.get("dominant_risk_drivers") or []
    story.append(Paragraph("Dominant Risk Drivers", styles["Heading2"]))
    if drivers:
        for item in drivers:
            score_text = f" ({item.get('score')} pts)" if item.get("score") is not None else ""
            story.append(
                Paragraph(
                    f"- {escape(str(item.get('label') or item.get('type') or 'Driver'))}{score_text}: {escape(str(item.get('reason') or ''))}",
                    styles["Normal"],
                )
            )
    else:
        story.append(
            Paragraph(
                "- No dominant risk drivers identified in the scored snapshot.", styles["Normal"]
            )
        )
    story.append(Spacer(1, 0.2 * cm))

    notes = explanation.get("notes") or {}
    story.append(Paragraph("Reviewer / Transition Notes", styles["Heading2"]))
    story.append(
        Paragraph(
            f"Review notes: {escape(str(notes.get('review_notes') or '—'))}", styles["Normal"]
        )
    )
    story.append(
        Paragraph(
            f"Override/rationale notes: {escape(str(notes.get('override_rationale_notes') or '—'))}",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            f"Transition notes: {escape(str(notes.get('transition_notes') or '—'))}",
            styles["Normal"],
        )
    )
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
    story.append(
        Paragraph(escape(str(explanation.get("provenance_statement") or "")), styles["Normal"])
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
    return _serialize_assessment(assessment, db=db)


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
    return [_serialize_assessment(item, db=db) for item in rows]


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
    rows = query.order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc()).limit(50).all()
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
    return _serialize_assessment(assessment, db=db)


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
    return _serialize_assessment(assessment, db=db)


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
        raise HTTPException(
            status_code=400,
            detail="Approved assessments must be rejected or finalized before rescoring.",
        )
    _score_and_persist(
        db=db,
        assessment=assessment,
    )
    return _serialize_assessment(assessment, db=db)


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
        raise HTTPException(
            status_code=400, detail="Assessment has hard-stops and cannot be approved."
        )
    if str(score.get("recommendation")) != "go":
        raise HTTPException(
            status_code=400, detail="Only go-recommended assessments can be approved."
        )

    assessment.status = FRAT_STATUS_APPROVED
    assessment.approved_by_id = current_user.id
    assessment.approved_at = datetime.utcnow()
    notes = (body.notes if body else "") or ""
    assessment.approval_notes = notes.strip()[:2000] or None
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment, db=db)


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
    return _serialize_assessment(assessment, db=db)


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
        raise HTTPException(
            status_code=400, detail="Assessment must be scored before finalization."
        )
    if bool(score.get("hard_stop_triggered")):
        raise HTTPException(
            status_code=400, detail="Assessment has hard-stops and cannot be finalized."
        )
    if str(score.get("recommendation")) != "go":
        raise HTTPException(
            status_code=400, detail="Only go-recommended assessments can be finalized."
        )
    if assessment.approved_by_id is None:
        raise HTTPException(
            status_code=400, detail="Assessment must be approved before finalization."
        )

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
        "decision_explanation": _build_decision_explanation(
            db=db,
            assessment=assessment,
            score_snapshot=score,
            hard_stop_snapshot=(
                [item for item in hard_stops if isinstance(item, dict)]
                if isinstance(hard_stops, list)
                else []
            ),
        ),
    }
    assessment.finalized_snapshot_json = json.dumps(finalized_snapshot)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment, db=db)


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
    report_snapshot = _build_report_snapshot(db=db, assessment=assessment)

    pdf_bytes = _build_frat_pdf(
        report_snapshot=report_snapshot,
        generated_by=current_user.username,
    )
    filename = f"FRAT_{assessment.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
