"""
Deterministic FRAT / mission-risk scoring model (P2.5).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

FRAT_STATUS_DRAFT = "draft"
FRAT_STATUS_SCORED = "scored"
FRAT_STATUS_NEEDS_REVIEW = "needs_review"
FRAT_STATUS_APPROVED = "approved"
FRAT_STATUS_REJECTED = "rejected"
FRAT_STATUS_FINALIZED = "finalized"

FRAT_ALLOWED_TRANSITIONS = {
    FRAT_STATUS_DRAFT: {FRAT_STATUS_SCORED, FRAT_STATUS_REJECTED},
    FRAT_STATUS_SCORED: {FRAT_STATUS_NEEDS_REVIEW, FRAT_STATUS_APPROVED, FRAT_STATUS_REJECTED},
    FRAT_STATUS_NEEDS_REVIEW: {FRAT_STATUS_SCORED, FRAT_STATUS_APPROVED, FRAT_STATUS_REJECTED},
    FRAT_STATUS_APPROVED: {FRAT_STATUS_FINALIZED, FRAT_STATUS_REJECTED},
    FRAT_STATUS_REJECTED: {FRAT_STATUS_DRAFT},
    FRAT_STATUS_FINALIZED: set(),
}

CATEGORY_KEYS = [
    "mission_profile",
    "weather_environment",
    "runway_operational",
    "aircraft_system_status",
    "crew_readiness",
]


def default_frat_inputs() -> Dict[str, Any]:
    return {
        "categories": {key: {"score": 0, "notes": ""} for key in CATEGORY_KEYS},
        "manual_adjustment": 0,
        "critical_flags": {
            "critical_system_unavailable": False,
            "mandatory_data_missing": False,
            "crew_unfit": False,
        },
        "requested_decision_authority": "authoritative",
        "reviewer_notes": "",
        "override_note": "",
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def normalize_frat_inputs(raw: Any) -> Dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    merged = default_frat_inputs()

    categories = payload.get("categories")
    if isinstance(categories, dict):
        for key in CATEGORY_KEYS:
            item = categories.get(key, {})
            if not isinstance(item, dict):
                item = {}
            merged["categories"][key]["score"] = _clamp(
                _safe_int(item.get("score"), 0),
                0,
                20,
            )
            merged["categories"][key]["notes"] = str(item.get("notes") or "")[:600]

    merged["manual_adjustment"] = _clamp(
        _safe_int(payload.get("manual_adjustment"), 0),
        -10,
        10,
    )
    flags = payload.get("critical_flags")
    if isinstance(flags, dict):
        for key in merged["critical_flags"].keys():
            merged["critical_flags"][key] = bool(flags.get(key, False))

    authority = str(payload.get("requested_decision_authority") or "authoritative").strip().lower()
    if authority not in {"authoritative", "advisory"}:
        authority = "authoritative"
    merged["requested_decision_authority"] = authority
    merged["reviewer_notes"] = str(payload.get("reviewer_notes") or "")[:2000]
    merged["override_note"] = str(payload.get("override_note") or "")[:1000]
    return merged


def _risk_band_for_score(total_score: int) -> str:
    if total_score <= 25:
        return "low"
    if total_score <= 45:
        return "moderate"
    if total_score <= 65:
        return "high"
    return "unacceptable"


def _analysis_penalty_from_controls(control: dict) -> int:
    warning_level = str(control.get("warning_level") or "none")
    result_strength = str(control.get("result_strength") or "advisory")
    applicability = str(control.get("applicability_status") or "advisory_only")
    retrieval = str(control.get("retrieval_coverage") or "none")
    deterministic_confidence = str(control.get("deterministic_confidence") or "unavailable")

    warning_penalty = {"none": 0, "info": 2, "caution": 7, "high": 12}.get(warning_level, 4)
    strength_penalty = {"authoritative": 0, "bounded": 4, "advisory": 8, "blocked": 12}.get(
        result_strength,
        6,
    )
    applicability_penalty = {
        "fully_applicable": 0,
        "partially_applicable": 3,
        "advisory_only": 6,
        "not_applicable": 8,
    }.get(applicability, 4)
    retrieval_penalty = {"strong": 0, "moderate": 1, "weak": 3, "none": 4}.get(retrieval, 2)
    confidence_penalty = {"high": 0, "medium": 1, "low": 3, "unavailable": 5}.get(
        deterministic_confidence,
        3,
    )
    return (
        warning_penalty
        + strength_penalty
        + applicability_penalty
        + retrieval_penalty
        + confidence_penalty
    )


def _build_hard_stops(
    *,
    inputs: dict,
    analysis_controls: Iterable[dict],
) -> List[dict]:
    stops: List[dict] = []
    flags = inputs.get("critical_flags") or {}
    requested_authority = inputs.get("requested_decision_authority", "authoritative")
    controls = list(analysis_controls)

    if bool(flags.get("critical_system_unavailable")):
        stops.append(
            {
                "code": "critical_system_unavailable",
                "severity": "high",
                "message": "Critical aircraft/system availability flag is active.",
                "source": "manual_flag",
            }
        )
    if bool(flags.get("mandatory_data_missing")):
        stops.append(
            {
                "code": "mandatory_data_missing",
                "severity": "high",
                "message": "Mandatory mission/analysis data is marked missing.",
                "source": "manual_flag",
            }
        )
    if bool(flags.get("crew_unfit")):
        stops.append(
            {
                "code": "crew_unfit",
                "severity": "high",
                "message": "Crew readiness indicates unfit status.",
                "source": "manual_flag",
            }
        )

    if requested_authority == "authoritative" and not controls:
        stops.append(
            {
                "code": "insufficient_authoritative_evidence",
                "severity": "high",
                "message": "Authoritative mission decision requested without analysis evidence.",
                "source": "analysis_controls",
            }
        )

    for control in controls:
        if (
            str(control.get("result_strength")) == "blocked"
            or str(control.get("applicability_status")) == "not_applicable"
        ):
            stops.append(
                {
                    "code": "analysis_not_applicable",
                    "severity": "high",
                    "message": "At least one linked analysis is blocked/not applicable.",
                    "source": "analysis_controls",
                }
            )
            break

    for control in controls:
        if str(control.get("warning_level")) == "high":
            stops.append(
                {
                    "code": "analysis_high_warning",
                    "severity": "high",
                    "message": "Linked analysis contains high-severity warning level.",
                    "source": "analysis_controls",
                }
            )
            break

    if requested_authority == "authoritative":
        for control in controls:
            if str(control.get("applicability_status")) in {"advisory_only", "not_applicable"}:
                stops.append(
                    {
                        "code": "advisory_evidence_only",
                        "severity": "high",
                        "message": "Authoritative decision requested but evidence is advisory-only/not-applicable.",
                        "source": "analysis_controls",
                    }
                )
                break

    # deduplicate by code
    dedup: Dict[str, dict] = {}
    for stop in stops:
        dedup[stop["code"]] = stop
    return list(dedup.values())


def compute_frat_score(
    *,
    inputs: dict,
    analysis_controls: Iterable[dict],
) -> Dict[str, Any]:
    normalized_inputs = normalize_frat_inputs(inputs)
    controls = list(analysis_controls or [])

    category_scores = {
        key: _clamp(_safe_int(normalized_inputs["categories"][key]["score"], 0), 0, 20)
        for key in CATEGORY_KEYS
    }
    base_score = sum(category_scores.values())
    manual_adjustment = _clamp(_safe_int(normalized_inputs.get("manual_adjustment"), 0), -10, 10)
    analysis_indicator_score = min(30, sum(_analysis_penalty_from_controls(c) for c in controls))

    hard_stops = _build_hard_stops(
        inputs=normalized_inputs,
        analysis_controls=controls,
    )
    total_score = base_score + manual_adjustment + analysis_indicator_score
    risk_band = _risk_band_for_score(total_score)

    if hard_stops:
        recommendation = "no_go"
        risk_band = "unacceptable"
    elif risk_band == "low":
        recommendation = "go"
    elif risk_band == "moderate":
        recommendation = "review"
    else:
        recommendation = "no_go"

    return {
        "category_scores": category_scores,
        "base_score": base_score,
        "manual_adjustment": manual_adjustment,
        "analysis_indicator_score": analysis_indicator_score,
        "total_score": total_score,
        "risk_band": risk_band,
        "recommendation": recommendation,
        "hard_stop_triggered": bool(hard_stops),
        "hard_stops": hard_stops,
        "analysis_controls_used": len(controls),
        "model_notes": [
            "Deterministic FRAT score combines category scores, manual adjustment, and analysis-derived penalties.",
            "Hard-stop conditions override numeric recommendation and force no-go behavior.",
        ],
    }
