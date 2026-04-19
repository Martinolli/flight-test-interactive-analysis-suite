"""
Deterministic calculator modules for analysis_mode routing.

P2.2 scope:
- keep takeoff as deterministic reference implementation
- add bounded deterministic calculators for landing, performance, buffet/vibration
- keep capability-catalog guardrails as source-of-truth for applicability/limitations
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.capabilities import CapabilityEvaluation, evaluate_capability_request
from app.models import DataPoint, TestParameter


def _apply_capability_evaluation_to_metrics(metrics: dict, evaluation: CapabilityEvaluation) -> dict:
    enriched = dict(metrics)
    enriched["capability_key"] = evaluation.capability_key
    enriched["capability_authority"] = evaluation.authority.value
    enriched["capability_status"] = evaluation.status.value
    enriched["capability_outcome"] = evaluation.outcome.value
    enriched["capability_reason_key"] = evaluation.reason_key
    enriched["capability_user_message"] = evaluation.user_message
    enriched["capability_missing_signals"] = list(evaluation.missing_required_signals)
    enriched["capability_applicability_boundaries"] = list(evaluation.applicability_boundaries)
    enriched["capability_limitations"] = list(evaluation.limitations)
    return enriched


def _choose_param_id(params: List[dict], scorer) -> Optional[int]:
    best_id = None
    best_score = float("-inf")
    for p in params:
        score = scorer(p["name"], p.get("unit"))
        if score > best_score:
            best_score = score
            best_id = p["id"]
    return best_id if best_score > 0 else None


def _load_parameter_catalog(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int],
) -> List[dict]:
    param_query = (
        db.query(TestParameter.id, TestParameter.name, TestParameter.unit)
        .join(DataPoint, DataPoint.parameter_id == TestParameter.id)
        .filter(DataPoint.flight_test_id == flight_test_id)
    )
    if dataset_version_id is not None:
        param_query = param_query.filter(DataPoint.dataset_version_id == dataset_version_id)
    param_rows = param_query.distinct().all()
    return [{"id": r.id, "name": r.name, "unit": r.unit} for r in param_rows]


def _load_timeseries_rows(
    db: Session,
    *,
    flight_test_id: int,
    dataset_version_id: Optional[int],
    parameter_ids: Iterable[int],
):
    rows_query = (
        db.query(DataPoint.timestamp, DataPoint.parameter_id, DataPoint.value)
        .filter(
            DataPoint.flight_test_id == flight_test_id,
            DataPoint.parameter_id.in_(list(parameter_ids)),
        )
    )
    if dataset_version_id is not None:
        rows_query = rows_query.filter(DataPoint.dataset_version_id == dataset_version_id)
    return rows_query.order_by(DataPoint.timestamp.asc()).all()


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
    del unit
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


def _score_altitude(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "pressure altitude" in n:
        score += 8
    if "altitude" in n or "alt" in n:
        score += 4
    if "ft" in u:
        score += 2
    if "m" == u or "meter" in u:
        score += 1
    return score


def _score_vertical_speed(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "vertical speed" in n:
        score += 8
    if "rate of climb" in n or "rate-of-climb" in n:
        score += 6
    if re.search(r"\bvs\b", n) or re.search(r"\bvz\b", n):
        score += 4
    if "fpm" in u:
        score += 2
    if "m/s" in u:
        score += 1
    return score


def _score_vibration_channel(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "vibration" in n or "vib" in n:
        score += 6
    if "buffet" in n:
        score += 5
    if "accel" in n:
        score += 4
    if "rate" in n:
        score += 1
    if u in {"g", "m/s2", "m/s^2", "deg/s", "rad/s"}:
        score += 2
    return score


def _is_ground(speed_kt: float, wow_value: Optional[float], threshold: float = 0.5) -> bool:
    if wow_value is None:
        return speed_kt < 25.0
    return wow_value >= threshold


def _knot_to_fts(value_kt: float) -> float:
    return value_kt * 1.687809857


def _percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = max(0.0, min(1.0, p)) * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    weight = pos - lo
    return sorted_vals[lo] + ((sorted_vals[hi] - sorted_vals[lo]) * weight)


def _unavailable_metrics(
    *,
    capability_key: str,
    reason: str,
    available_signals: Iterable[str],
    has_dataset: bool,
    has_time_series_continuity: Optional[bool] = None,
    data_coverage_ok: Optional[bool] = None,
    event_detection_ok: Optional[bool] = None,
    request_certification_result: bool = False,
    has_standards_context: bool = True,
) -> dict:
    evaluation = evaluate_capability_request(
        capability_key,
        available_signals=available_signals,
        has_dataset=has_dataset,
        has_time_series_continuity=has_time_series_continuity,
        data_coverage_ok=data_coverage_ok,
        event_detection_ok=event_detection_ok,
        request_certification_result=request_certification_result,
        correction_inputs_available=False,
        has_standards_context=has_standards_context,
    )
    return _apply_capability_evaluation_to_metrics(
        {
            "available": False,
            "reason": reason,
        },
        evaluation,
    )


def compute_takeoff_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    """Compute takeoff run metrics from time-series data (deterministic)."""
    params = _load_parameter_catalog(db, flight_test_id, dataset_version_id)
    if not params:
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="No parameters found for flight test.",
            available_signals=[],
            has_dataset=False,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

    ground_speed_id = _choose_param_id(params, _score_ground_speed)
    wow_ids = [p["id"] for p in params if _score_wow(p["name"], p.get("unit")) > 0]
    accel_id = _choose_param_id(params, _score_longitudinal_accel)
    available_signals = set()
    if ground_speed_id is not None:
        available_signals.add("ground_speed")
    if wow_ids:
        available_signals.add("weight_on_wheels")
    if accel_id is not None:
        available_signals.add("longitudinal_acceleration")

    if ground_speed_id is None:
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="Ground speed parameter not found.",
            available_signals=available_signals,
            has_dataset=True,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )
    if not wow_ids:
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="Weight-on-wheels parameter not found.",
            available_signals=available_signals,
            has_dataset=True,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

    selected_ids = set([ground_speed_id, *wow_ids])
    if accel_id is not None:
        selected_ids.add(accel_id)

    rows = _load_timeseries_rows(
        db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        parameter_ids=selected_ids,
    )
    if not rows:
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="No datapoints found for required parameters.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

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
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="Insufficient timeseries points for takeoff calculation.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

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
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="Could not detect liftoff transition from WOW signals.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=True,
            event_detection_ok=False,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

    start_idx = None
    for i in range(liftoff_idx, -1, -1):
        pt = points[i]
        if (pt["wow"] is None or pt["wow"] >= 0.5) and pt["gs_kt"] <= 5:
            start_idx = i
            break
    if start_idx is None:
        candidates = [
            i for i in range(0, liftoff_idx + 1) if points[i]["wow"] is None or points[i]["wow"] >= 0.5
        ]
        start_idx = candidates[0] if candidates else 0

    if start_idx >= liftoff_idx:
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="Invalid takeoff segment boundaries.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=True,
            event_detection_ok=False,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

    distance_ft = 0.0
    valid_intervals = 0
    for i in range(start_idx + 1, liftoff_idx + 1):
        p0 = points[i - 1]
        p1 = points[i]
        dt = (p1["ts"] - p0["ts"]).total_seconds()
        if dt <= 0 or dt > 10:
            continue
        v0 = _knot_to_fts(max(p0["gs_kt"], 0.0))
        v1 = _knot_to_fts(max(p1["gs_kt"], 0.0))
        distance_ft += ((v0 + v1) / 2.0) * dt
        valid_intervals += 1

    if valid_intervals == 0:
        return _unavailable_metrics(
            capability_key="takeoff",
            reason="No valid time intervals for distance integration.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=False,
            event_detection_ok=False,
            request_certification_result=request_certification_result,
            has_standards_context=False,
        )

    start_pt = points[start_idx]
    liftoff_pt = points[liftoff_idx]
    duration_s = (liftoff_pt["ts"] - start_pt["ts"]).total_seconds()
    mean_accel_fts2 = None
    if duration_s > 0:
        mean_accel_fts2 = (_knot_to_fts(liftoff_pt["gs_kt"] - start_pt["gs_kt"])) / duration_s

    accel_samples = [pt["accel"] for pt in points[start_idx : liftoff_idx + 1] if pt["accel"] is not None]
    accel_mean_g = (sum(accel_samples) / len(accel_samples)) if accel_samples else None
    accel_sensor_fts2 = (accel_mean_g * 32.174) if accel_mean_g is not None else None

    evaluation = evaluate_capability_request(
        "takeoff",
        available_signals=available_signals,
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
        event_detection_ok=True,
        request_certification_result=request_certification_result,
        correction_inputs_available=False,
    )
    return _apply_capability_evaluation_to_metrics(
        {
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
        },
        evaluation,
    )


def compute_landing_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    """Compute bounded landing rollout metrics from WOW and ground-speed traces."""
    params = _load_parameter_catalog(db, flight_test_id, dataset_version_id)
    if not params:
        return _unavailable_metrics(
            capability_key="landing",
            reason="No parameters found for flight test.",
            available_signals=[],
            has_dataset=False,
            request_certification_result=request_certification_result,
        )

    ground_speed_id = _choose_param_id(params, _score_ground_speed)
    wow_ids = [p["id"] for p in params if _score_wow(p["name"], p.get("unit")) > 0]
    available_signals = set()
    if ground_speed_id is not None:
        available_signals.add("ground_speed")
    if wow_ids:
        available_signals.add("weight_on_wheels")

    if ground_speed_id is None:
        return _unavailable_metrics(
            capability_key="landing",
            reason="Ground speed parameter not found.",
            available_signals=available_signals,
            has_dataset=True,
            request_certification_result=request_certification_result,
        )
    if not wow_ids:
        return _unavailable_metrics(
            capability_key="landing",
            reason="Weight-on-wheels parameter not found.",
            available_signals=available_signals,
            has_dataset=True,
            request_certification_result=request_certification_result,
        )

    rows = _load_timeseries_rows(
        db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        parameter_ids=[ground_speed_id, *wow_ids],
    )
    if not rows:
        return _unavailable_metrics(
            capability_key="landing",
            reason="No datapoints found for required parameters.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
            request_certification_result=request_certification_result,
        )

    timeline: Dict[Any, Dict[int, float]] = {}
    for r in rows:
        timeline.setdefault(r.timestamp, {})[r.parameter_id] = float(r.value)

    points = []
    for ts in sorted(timeline.keys()):
        values = timeline[ts]
        gs = values.get(ground_speed_id)
        if gs is None:
            continue
        wow_values = [values[w_id] for w_id in wow_ids if w_id in values]
        wow_mean = (sum(wow_values) / len(wow_values)) if wow_values else None
        points.append({"ts": ts, "gs_kt": gs, "wow": wow_mean})

    if len(points) < 2:
        return _unavailable_metrics(
            capability_key="landing",
            reason="Insufficient timeseries points for landing rollout calculation.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
            request_certification_result=request_certification_result,
        )

    touchdown_idx = None
    for i in range(1, len(points)):
        prev_pt = points[i - 1]
        cur_pt = points[i]
        if prev_pt["wow"] is None or cur_pt["wow"] is None:
            continue
        if prev_pt["wow"] < 0.5 and cur_pt["wow"] >= 0.5 and cur_pt["gs_kt"] >= 20:
            touchdown_idx = i
            break
    if touchdown_idx is None:
        for i, pt in enumerate(points):
            if (pt["wow"] is not None and pt["wow"] >= 0.5) and pt["gs_kt"] >= 20:
                touchdown_idx = i
                break
    if touchdown_idx is None:
        return _unavailable_metrics(
            capability_key="landing",
            reason="Could not detect touchdown transition from WOW signals.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=True,
            event_detection_ok=False,
            request_certification_result=request_certification_result,
        )

    rollout_end_idx = None
    for i in range(touchdown_idx + 1, len(points)):
        pt = points[i]
        if _is_ground(pt["gs_kt"], pt["wow"]) and pt["gs_kt"] <= 8.0:
            rollout_end_idx = i
            break
    if rollout_end_idx is None:
        ground_candidates = [
            idx for idx in range(touchdown_idx + 1, len(points)) if _is_ground(points[idx]["gs_kt"], points[idx]["wow"])
        ]
        rollout_end_idx = ground_candidates[-1] if ground_candidates else (len(points) - 1)

    if rollout_end_idx <= touchdown_idx:
        return _unavailable_metrics(
            capability_key="landing",
            reason="Invalid landing segment boundaries.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=True,
            event_detection_ok=False,
            request_certification_result=request_certification_result,
        )

    distance_ft = 0.0
    valid_intervals = 0
    for i in range(touchdown_idx + 1, rollout_end_idx + 1):
        p0 = points[i - 1]
        p1 = points[i]
        dt = (p1["ts"] - p0["ts"]).total_seconds()
        if dt <= 0 or dt > 10:
            continue
        v0 = _knot_to_fts(max(p0["gs_kt"], 0.0))
        v1 = _knot_to_fts(max(p1["gs_kt"], 0.0))
        distance_ft += ((v0 + v1) / 2.0) * dt
        valid_intervals += 1

    if valid_intervals == 0:
        return _unavailable_metrics(
            capability_key="landing",
            reason="No valid time intervals for landing rollout integration.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=False,
            event_detection_ok=False,
            request_certification_result=request_certification_result,
        )

    touchdown_pt = points[touchdown_idx]
    end_pt = points[rollout_end_idx]
    rollout_time_s = (end_pt["ts"] - touchdown_pt["ts"]).total_seconds()
    mean_decel_fts2 = None
    if rollout_time_s > 0:
        mean_decel_fts2 = (_knot_to_fts(end_pt["gs_kt"] - touchdown_pt["gs_kt"])) / rollout_time_s

    evaluation = evaluate_capability_request(
        "landing",
        available_signals=available_signals,
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
        event_detection_ok=True,
        request_certification_result=request_certification_result,
        correction_inputs_available=False,
    )
    return _apply_capability_evaluation_to_metrics(
        {
            "available": True,
            "distance_ft": round(distance_ft, 1),
            "distance_m": round(distance_ft * 0.3048, 1),
            "touchdown_timestamp": touchdown_pt["ts"].isoformat(),
            "rollout_end_timestamp": end_pt["ts"].isoformat(),
            "touchdown_speed_kt": round(touchdown_pt["gs_kt"], 2),
            "rollout_end_speed_kt": round(end_pt["gs_kt"], 2),
            "rollout_time_s": round(rollout_time_s, 2),
            "mean_decel_fts2": round(mean_decel_fts2, 3) if mean_decel_fts2 is not None else None,
            "sample_intervals_used": valid_intervals,
            "wow_channels_used": len(wow_ids),
            "wow_ground_threshold": 0.5,
        },
        evaluation,
    )


def _convert_altitude_to_ft(value: float, unit: Optional[str]) -> float:
    u = (unit or "").strip().lower()
    if "m" == u or "meter" in u:
        return value * 3.280839895
    return value


def _convert_vertical_speed_to_fpm(value: float, unit: Optional[str]) -> float:
    u = (unit or "").strip().lower()
    if "m/s" in u:
        return value * 196.8503937
    if "ft/s" in u:
        return value * 60.0
    return value


def compute_performance_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    """Compute bounded general-performance deterministic metrics."""
    del request_certification_result
    params = _load_parameter_catalog(db, flight_test_id, dataset_version_id)
    if not params:
        return _unavailable_metrics(
            capability_key="performance_general",
            reason="No parameters found for flight test.",
            available_signals=[],
            has_dataset=False,
        )

    altitude_id = _choose_param_id(params, _score_altitude)
    vertical_speed_id = _choose_param_id(params, _score_vertical_speed)
    ground_speed_id = _choose_param_id(params, _score_ground_speed)
    accel_id = _choose_param_id(params, _score_longitudinal_accel)
    param_map = {p["id"]: p for p in params}

    selected_ids = [pid for pid in [altitude_id, vertical_speed_id, ground_speed_id, accel_id] if pid is not None]
    available_signals = set()
    if altitude_id is not None:
        available_signals.add("altitude")
    if vertical_speed_id is not None:
        available_signals.add("vertical_speed")
    if ground_speed_id is not None:
        available_signals.add("ground_speed")
    if accel_id is not None:
        available_signals.add("longitudinal_acceleration")

    if not selected_ids:
        return _unavailable_metrics(
            capability_key="performance_general",
            reason="No altitude, vertical-speed, ground-speed, or acceleration channels were detected.",
            available_signals=[],
            has_dataset=False,
        )

    rows = _load_timeseries_rows(
        db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        parameter_ids=selected_ids,
    )
    if not rows:
        return _unavailable_metrics(
            capability_key="performance_general",
            reason="No datapoints found for detected performance channels.",
            available_signals=available_signals,
            has_dataset=False,
        )

    timeline: Dict[Any, Dict[int, float]] = {}
    for r in rows:
        timeline.setdefault(r.timestamp, {})[r.parameter_id] = float(r.value)

    points = []
    for ts in sorted(timeline.keys()):
        values = timeline[ts]
        points.append(
            {
                "ts": ts,
                "altitude": values.get(altitude_id) if altitude_id is not None else None,
                "vertical_speed": values.get(vertical_speed_id) if vertical_speed_id is not None else None,
                "ground_speed": values.get(ground_speed_id) if ground_speed_id is not None else None,
                "accel": values.get(accel_id) if accel_id is not None else None,
            }
        )

    if len(points) < 2:
        return _unavailable_metrics(
            capability_key="performance_general",
            reason="Insufficient timeseries coverage for performance trend metrics.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
        )

    start_ts = points[0]["ts"]
    end_ts = points[-1]["ts"]
    duration_s = (end_ts - start_ts).total_seconds()
    if duration_s <= 0:
        return _unavailable_metrics(
            capability_key="performance_general",
            reason="Invalid analysis window; non-positive time span.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
        )

    altitude_change_ft = None
    if altitude_id is not None:
        altitude_values = [pt["altitude"] for pt in points if pt["altitude"] is not None]
        if len(altitude_values) >= 2:
            altitude_unit = param_map.get(altitude_id, {}).get("unit")
            altitude_change_ft = _convert_altitude_to_ft(altitude_values[-1], altitude_unit) - _convert_altitude_to_ft(
                altitude_values[0], altitude_unit
            )

    mean_climb_rate_fpm = None
    if vertical_speed_id is not None:
        vs_values = [pt["vertical_speed"] for pt in points if pt["vertical_speed"] is not None]
        if vs_values:
            vs_unit = param_map.get(vertical_speed_id, {}).get("unit")
            mean_climb_rate_fpm = sum(_convert_vertical_speed_to_fpm(v, vs_unit) for v in vs_values) / len(vs_values)
    elif altitude_change_ft is not None and duration_s > 0:
        mean_climb_rate_fpm = (altitude_change_ft / duration_s) * 60.0

    gs_values = [pt["ground_speed"] for pt in points if pt["ground_speed"] is not None]
    speed_delta_kt = None
    max_speed_kt = None
    min_speed_kt = None
    if len(gs_values) >= 2:
        speed_delta_kt = gs_values[-1] - gs_values[0]
        max_speed_kt = max(gs_values)
        min_speed_kt = min(gs_values)

    accel_values = [pt["accel"] for pt in points if pt["accel"] is not None]
    accel_mean_g = (sum(accel_values) / len(accel_values)) if accel_values else None
    accel_mean_fts2 = (accel_mean_g * 32.174) if accel_mean_g is not None else None

    evaluation = evaluate_capability_request(
        "performance_general",
        available_signals=available_signals,
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    return _apply_capability_evaluation_to_metrics(
        {
            "available": True,
            "analysis_window_s": round(duration_s, 2),
            "samples_used": len(points),
            "altitude_change_ft": round(altitude_change_ft, 2) if altitude_change_ft is not None else None,
            "mean_climb_rate_fpm": round(mean_climb_rate_fpm, 2) if mean_climb_rate_fpm is not None else None,
            "speed_delta_kt": round(speed_delta_kt, 2) if speed_delta_kt is not None else None,
            "max_speed_kt": round(max_speed_kt, 2) if max_speed_kt is not None else None,
            "min_speed_kt": round(min_speed_kt, 2) if min_speed_kt is not None else None,
            "accel_mean_g": round(accel_mean_g, 4) if accel_mean_g is not None else None,
            "accel_mean_fts2": round(accel_mean_fts2, 3) if accel_mean_fts2 is not None else None,
        },
        evaluation,
    )


def compute_buffet_vibration_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    """Compute bounded vibration/buffet screening metrics from available channels."""
    del request_certification_result
    params = _load_parameter_catalog(db, flight_test_id, dataset_version_id)
    if not params:
        return _unavailable_metrics(
            capability_key="buffet_vibration",
            reason="No parameters found for flight test.",
            available_signals=[],
            has_dataset=False,
        )

    scored = []
    for p in params:
        score = _score_vibration_channel(p["name"], p.get("unit"))
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [item[1] for item in scored[:12]]
    if not selected:
        return _unavailable_metrics(
            capability_key="buffet_vibration",
            reason="No vibration or acceleration channels were detected.",
            available_signals=[],
            has_dataset=False,
        )

    rows = _load_timeseries_rows(
        db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        parameter_ids=[p["id"] for p in selected],
    )
    if not rows:
        return _unavailable_metrics(
            capability_key="buffet_vibration",
            reason="No datapoints found for vibration screening channels.",
            available_signals=["accelerometers"],
            has_dataset=False,
        )

    channel_values: Dict[int, List[float]] = {}
    for row in rows:
        channel_values.setdefault(int(row.parameter_id), []).append(float(row.value))

    channel_summaries = []
    for p in selected:
        values = channel_values.get(p["id"], [])
        if len(values) < 5:
            continue
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_val = math.sqrt(max(variance, 0.0))
        rms = math.sqrt(sum(v * v for v in values) / len(values))
        abs_values = [abs(v) for v in values]
        p95_abs = _percentile(abs_values, 0.95)
        exceedance_count = sum(1 for v in values if std_val > 0 and abs(v - mean_val) >= (3.0 * std_val))
        channel_summaries.append(
            {
                "name": p["name"],
                "unit": p.get("unit"),
                "samples": len(values),
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "rms": round(rms, 4),
                "peak_abs": round(max(abs_values), 4),
                "p95_abs": round(p95_abs, 4) if p95_abs is not None else None,
                "exceedance_count": exceedance_count,
            }
        )

    if not channel_summaries:
        return _unavailable_metrics(
            capability_key="buffet_vibration",
            reason="Detected screening channels did not have enough samples.",
            available_signals=["accelerometers"],
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
        )

    channel_summaries.sort(key=lambda item: item["peak_abs"], reverse=True)
    dominant = channel_summaries[0]
    evaluation = evaluate_capability_request(
        "buffet_vibration",
        available_signals=["accelerometers"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    return _apply_capability_evaluation_to_metrics(
        {
            "available": True,
            "channels_screened": len(channel_summaries),
            "dominant_channel": dominant["name"],
            "dominant_peak_abs": dominant["peak_abs"],
            "dominant_unit": dominant["unit"],
            "channels_with_exceedances": sum(1 for c in channel_summaries if c["exceedance_count"] > 0),
            "channel_summaries": channel_summaries[:6],
        },
        evaluation,
    )


def _build_unavailable_section(title: str, metrics: dict) -> str:
    lines = [
        title,
        "Deterministic metrics are unavailable for this dataset/mode scope.",
        "",
        f"- Reason: {metrics.get('reason', 'Unknown')}",
    ]
    if metrics.get("capability_reason_key"):
        lines.append(f"- Capability rule key: {metrics.get('capability_reason_key')}")
    if metrics.get("capability_outcome"):
        lines.append(f"- Capability outcome: {metrics.get('capability_outcome')}")
    applicability = metrics.get("capability_applicability_boundaries") or []
    if applicability:
        lines.extend(["", "### Applicability Boundaries"])
        for item in applicability:
            lines.append(f"- {item}")
    limitations = metrics.get("capability_limitations") or []
    if limitations:
        lines.extend(["", "### Limitations"])
        for item in limitations:
            lines.append(f"- {item}")
    return "\n".join(lines)


def build_deterministic_takeoff_section(metrics: dict) -> str:
    """Render deterministic takeoff section directly from computed data."""
    outcome = metrics.get("capability_outcome")
    capability_limitations = metrics.get("capability_limitations") or []
    capability_applicability = metrics.get("capability_applicability_boundaries") or []
    capability_reason_key = metrics.get("capability_reason_key")

    if not metrics.get("available"):
        return _build_unavailable_section("## Deterministic Calculation (Flight Data) [DATA]", metrics) + "\n"

    lines = [
        "## Deterministic Calculation (Flight Data) [DATA]",
        "",
        "### Result Classification",
        "- Result type: **Estimated takeoff ground roll to liftoff**",
        "- Classification: **Deterministic data-derived estimate**",
        (
            "- Corrections not applied: **wind, runway slope, non-standard atmosphere, "
            "and certification screen-height corrections**"
        ),
    ]
    if outcome == "partial_estimate":
        lines.append(
            "- Capability outcome: **Partial estimate** due to unavailable correction inputs for certification-style request."
        )
    else:
        lines.append("- Capability outcome: **Allow with explicit limitations**")
    lines.append(
        (
            "- Applicability boundary: valid for the detected WOW/ground-speed takeoff segment only; "
            "not a certification-corrected takeoff distance."
        )
    )
    lines.extend(["", "### Computed Metrics"])
    vi_kt = float(metrics["start_speed_kt"])
    vf_kt = float(metrics["liftoff_speed_kt"])
    t_s = float(metrics["run_time_s"])
    vi_fts = _knot_to_fts(vi_kt)
    vf_fts = _knot_to_fts(vf_kt)
    accel_fts2 = metrics.get("mean_accel_fts2")
    accel_for_eq = float(accel_fts2) if accel_fts2 is not None else None
    distance_integrated = float(metrics["distance_ft"])

    distance_kinematic = None
    if accel_for_eq is not None:
        distance_kinematic = (vi_fts * t_s) + (0.5 * accel_for_eq * (t_s**2))

    lines.extend(
        [
            (
                "- Estimated takeoff ground roll to liftoff "
                f"(integrated speed trace): **{metrics['distance_ft']} ft ({metrics['distance_m']} m)**"
            ),
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
    )
    if accel_for_eq is not None:
        lines.append(f"- a = ({vf_fts:.3f} - {vi_fts:.3f}) / {t_s:.2f} = {accel_for_eq:.3f} ft/s^2")
    if distance_kinematic is not None:
        lines.append(f"- Kinematic distance check: d ≈ {distance_kinematic:.1f} ft (integrated result: {distance_integrated:.1f} ft)")
    lines.extend(
        [
            "",
            (
                "Use the integrated speed-trace distance as the primary deterministic estimate for "
                "ground roll to liftoff [DATA]."
            ),
            "Do not interpret this value as a corrected certification takeoff distance unless corrections are explicitly applied.",
        ]
    )
    if capability_applicability:
        lines.extend(["", "### Applicability Boundaries"])
        for item in capability_applicability:
            lines.append(f"- {item}")
    if capability_limitations:
        lines.extend(["", "### Limitations"])
        for item in capability_limitations:
            lines.append(f"- {item}")
    if capability_reason_key and outcome != "partial_estimate":
        lines.append("")
        lines.append(f"- Capability rule key: {capability_reason_key}")
    return "\n".join(lines)


def build_deterministic_landing_section(metrics: dict) -> str:
    if not metrics.get("available"):
        return _build_unavailable_section("## Deterministic Calculation (Landing Data) [DATA]", metrics)

    lines = [
        "## Deterministic Calculation (Landing Data) [DATA]",
        "",
        "### Result Classification",
        "- Result type: **Estimated landing rollout distance (touchdown to rollout end)**",
        "- Classification: **Deterministic data-derived estimate**",
        "- Corrections not applied: **wind, runway slope, braking efficiency normalization, and certification screen-height corrections**",
        "- Applicability boundary: valid for touchdown-to-rollout estimate from available WOW and ground-speed signals only.",
        "",
        "### Computed Metrics",
        f"- Estimated landing rollout distance: **{metrics.get('distance_ft')} ft ({metrics.get('distance_m')} m)**",
        f"- Touchdown speed: **{metrics.get('touchdown_speed_kt')} kt**",
        f"- Rollout end speed: **{metrics.get('rollout_end_speed_kt')} kt**",
        f"- Rollout time: **{metrics.get('rollout_time_s')} s**",
        f"- Mean deceleration (speed-trace): **{metrics.get('mean_decel_fts2', 'n/a')} ft/s^2**",
        f"- Integration intervals used: **{metrics.get('sample_intervals_used', 0)}**",
        "",
        "### Segment Definition",
        f"- Touchdown sample: **{metrics.get('touchdown_timestamp', 'n/a')}**",
        f"- Rollout end sample: **{metrics.get('rollout_end_timestamp', 'n/a')}**",
        f"- WOW channels used: **{metrics.get('wow_channels_used', 'n/a')}** (ground threshold {metrics.get('wow_ground_threshold', 0.5)})",
    ]
    applicability = metrics.get("capability_applicability_boundaries") or []
    limitations = metrics.get("capability_limitations") or []
    if applicability:
        lines.extend(["", "### Applicability Boundaries"])
        for item in applicability:
            lines.append(f"- {item}")
    if limitations:
        lines.extend(["", "### Limitations"])
        for item in limitations:
            lines.append(f"- {item}")
    return "\n".join(lines)


def build_deterministic_performance_section(metrics: dict) -> str:
    if not metrics.get("available"):
        return _build_unavailable_section("## Deterministic Calculation (Performance Trends) [DATA]", metrics)

    lines = [
        "## Deterministic Calculation (Performance Trends) [DATA]",
        "",
        "### Result Classification",
        "- Result type: **General deterministic performance trend summary**",
        "- Classification: **Deterministic bounded engineering metrics**",
        "- Applicability boundary: this section summarizes available trends and does not claim full certification performance determination.",
        "",
        "### Computed Metrics",
        f"- Analysis window: **{metrics.get('analysis_window_s')} s**",
        f"- Samples used: **{metrics.get('samples_used')}**",
    ]
    if metrics.get("altitude_change_ft") is not None:
        lines.append(f"- Altitude delta: **{metrics.get('altitude_change_ft')} ft**")
    if metrics.get("mean_climb_rate_fpm") is not None:
        lines.append(f"- Mean climb rate: **{metrics.get('mean_climb_rate_fpm')} fpm**")
    if metrics.get("speed_delta_kt") is not None:
        lines.append(f"- Ground-speed delta: **{metrics.get('speed_delta_kt')} kt**")
    if metrics.get("max_speed_kt") is not None and metrics.get("min_speed_kt") is not None:
        lines.append(
            f"- Ground-speed range: **{metrics.get('min_speed_kt')} to {metrics.get('max_speed_kt')} kt**"
        )
    if metrics.get("accel_mean_g") is not None:
        lines.append(
            f"- Mean longitudinal acceleration: **{metrics.get('accel_mean_g')} g ({metrics.get('accel_mean_fts2')} ft/s^2)**"
        )

    applicability = metrics.get("capability_applicability_boundaries") or []
    limitations = metrics.get("capability_limitations") or []
    if applicability:
        lines.extend(["", "### Applicability Boundaries"])
        for item in applicability:
            lines.append(f"- {item}")
    if limitations:
        lines.extend(["", "### Limitations"])
        for item in limitations:
            lines.append(f"- {item}")
    return "\n".join(lines)


def build_deterministic_buffet_vibration_section(metrics: dict) -> str:
    if not metrics.get("available"):
        return _build_unavailable_section(
            "## Deterministic Calculation (Buffet/Vibration Screening) [DATA]",
            metrics,
        )

    lines = [
        "## Deterministic Calculation (Buffet/Vibration Screening) [DATA]",
        "",
        "### Result Classification",
        "- Result type: **Deterministic screening summary for buffet/vibration behavior**",
        "- Classification: **Screening/support output (not formal clearance determination)**",
        "- Applicability boundary: suitable for pre-screening and anomaly flagging only.",
        "",
        "### Screening Summary",
        f"- Channels screened: **{metrics.get('channels_screened')}**",
        (
            f"- Dominant channel: **{metrics.get('dominant_channel')}** "
            f"(peak abs {metrics.get('dominant_peak_abs')} {metrics.get('dominant_unit') or ''})"
        ),
        f"- Channels with exceedance events: **{metrics.get('channels_with_exceedances')}**",
        "",
        "### Channel Highlights",
    ]

    for channel in metrics.get("channel_summaries", []):
        lines.append(
            (
                f"- {channel.get('name')} ({channel.get('unit') or '-'}) -> "
                f"samples={channel.get('samples')}, rms={channel.get('rms')}, "
                f"peak_abs={channel.get('peak_abs')}, p95_abs={channel.get('p95_abs')}, "
                f"exceedances={channel.get('exceedance_count')}"
            )
        )

    applicability = metrics.get("capability_applicability_boundaries") or []
    limitations = metrics.get("capability_limitations") or []
    if applicability:
        lines.extend(["", "### Applicability Boundaries"])
        for item in applicability:
            lines.append(f"- {item}")
    if limitations:
        lines.extend(["", "### Limitations"])
        for item in limitations:
            lines.append(f"- {item}")
    return "\n".join(lines)

