"""
Deterministic calculator modules for analysis_mode routing.

P2.2 scope:
- keep takeoff as deterministic reference implementation
- add bounded deterministic calculators for landing, performance, buffet/vibration
- keep capability-catalog guardrails as source-of-truth for applicability/limitations

P3.2 scope:
- add bounded deterministic handling/control-response workflow
- keep handling-qualities outputs explicit and non-certification
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.analysis.air_data import (
    density_altitude_estimate_ft,
    estimate_mach_from_tas_knots_and_temperature_c,
    estimate_tas_from_cas_and_sigma_knots,
    isa_atmosphere_from_pressure_altitude_ft,
    summarize_series as summarize_air_data_series,
)
from app.capabilities import CapabilityEvaluation, evaluate_capability_request
from app.models import DataPoint, TestParameter


@dataclass(frozen=True)
class DeterministicCalculatorResult:
    """Shared deterministic result structure for all calculator modules."""

    available: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "available": self.available,
            "deterministic_metrics": dict(self.metrics),
            "deterministic_assumptions": list(self.assumptions),
        }
        if self.reason:
            payload["reason"] = self.reason
        payload.update(self.metrics)
        return payload


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


def _result_with_capability(result: DeterministicCalculatorResult, evaluation: CapabilityEvaluation) -> dict:
    return _apply_capability_evaluation_to_metrics(result.to_dict(), evaluation)


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


def _score_pressure_altitude(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "pressure altitude" in n:
        score += 10
    if re.search(r"\bpa\b", n):
        score += 2
    if score > 0 and "ft" in u:
        score += 2
    return score


def _score_oat(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "outside air temperature" in n or re.search(r"\boat\b", n):
        score += 8
    if "temperature" in n and ("outside" in n or "ambient" in n):
        score += 4
    if score > 0 and ("c" in u or "f" in u or "k" in u):
        score += 1
    return score


def _score_sat(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "static air temperature" in n:
        score += 10
    if re.search(r"\bsat\b", n):
        score += 8
    if score > 0 and ("c" in u or "f" in u or "k" in u):
        score += 1
    return score


def _score_tat(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "total air temperature" in n:
        score += 10
    if re.search(r"\btat\b", n):
        score += 8
    if score > 0 and ("c" in u or "f" in u or "k" in u):
        score += 1
    return score


def _score_cas(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "calibrated airspeed" in n:
        score += 10
    if re.search(r"\bcas\b", n):
        score += 8
    if "airspeed" in n and "calibrated" in n:
        score += 5
    if score > 0 and ("kt" in u or "knot" in u):
        score += 1
    return score


def _score_tas(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "true airspeed" in n:
        score += 10
    if re.search(r"\btas\b", n):
        score += 8
    if "airspeed" in n and "true" in n:
        score += 5
    if score > 0 and ("kt" in u or "knot" in u):
        score += 1
    return score


def _score_mach(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "mach" in n:
        score += 10
    if n.strip() in {"m", "mach_number"}:
        score += 2
    if "mach" in u:
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


def _score_aileron(name: str, unit: Optional[str]) -> float:
    del unit
    n = (name or "").lower()
    score = 0.0
    if "aileron" in n:
        score += 8
    if "deflection" in n or "position" in n or "command" in n:
        score += 2
    return score


def _score_elevator(name: str, unit: Optional[str]) -> float:
    del unit
    n = (name or "").lower()
    score = 0.0
    if "elevator" in n:
        score += 8
    if "deflection" in n or "position" in n or "command" in n:
        score += 2
    return score


def _score_rudder(name: str, unit: Optional[str]) -> float:
    del unit
    n = (name or "").lower()
    score = 0.0
    if "rudder" in n:
        score += 8
    if "deflection" in n or "position" in n or "command" in n:
        score += 2
    return score


def _score_stick_lateral(name: str, unit: Optional[str]) -> float:
    del unit
    n = (name or "").lower()
    score = 0.0
    if "stick" in n:
        score += 3
    if "lateral" in n or "roll" in n:
        score += 5
    if "position" in n or "input" in n:
        score += 1
    return score


def _score_stick_longitudinal(name: str, unit: Optional[str]) -> float:
    del unit
    n = (name or "").lower()
    score = 0.0
    if "stick" in n:
        score += 3
    if "longitudinal" in n or "pitch" in n:
        score += 5
    if "position" in n or "input" in n:
        score += 1
    return score


def _score_roll_rate(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "roll rate" in n:
        score += 8
    if re.search(r"\broll\b", n) and ("rate" in n or "/s" in n):
        score += 4
    if re.search(r"\bp\b", n) and ("rate" in n or "deg/s" in u):
        score += 2
    if score > 0 and ("deg/s" in u or "rad/s" in u):
        score += 1
    return score


def _score_pitch_rate(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "pitch rate" in n:
        score += 8
    if re.search(r"\bpitch\b", n) and ("rate" in n or "/s" in n):
        score += 4
    if re.search(r"\bq\b", n) and ("rate" in n or "deg/s" in u):
        score += 2
    if score > 0 and ("deg/s" in u or "rad/s" in u):
        score += 1
    return score


def _score_yaw_rate(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "yaw rate" in n:
        score += 8
    if re.search(r"\byaw\b", n) and ("rate" in n or "/s" in n):
        score += 4
    if re.search(r"\br\b", n) and ("rate" in n or "deg/s" in u):
        score += 2
    if score > 0 and ("deg/s" in u or "rad/s" in u):
        score += 1
    return score


def _score_roll_angle(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "roll angle" in n or "bank angle" in n:
        score += 8
    if "roll" in n and "angle" in n:
        score += 4
    if score > 0 and "deg" in u:
        score += 1
    return score


def _score_pitch_angle(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "pitch angle" in n:
        score += 8
    if "pitch" in n and "angle" in n:
        score += 4
    if score > 0 and "deg" in u:
        score += 1
    return score


def _score_heading(name: str, unit: Optional[str]) -> float:
    n = (name or "").lower()
    u = (unit or "").lower()
    score = 0.0
    if "heading" in n:
        score += 8
    if "yaw angle" in n:
        score += 6
    if "yaw" in n and "angle" in n:
        score += 4
    if score > 0 and "deg" in u:
        score += 1
    return score


def _basic_stats(values: List[float]) -> Optional[dict]:
    if not values:
        return None
    mean_val = sum(values) / len(values)
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std_val = math.sqrt(max(variance, 0.0))
    return {
        "min": min(values),
        "max": max(values),
        "mean": mean_val,
        "std": std_val,
    }


def _pearson_corr(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    var_x = sum((x - x_mean) ** 2 for x in xs)
    var_y = sum((y - y_mean) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    if denom <= 0:
        return None
    return cov / denom


def _best_sample_lag(xs: List[float], ys: List[float], max_lag: int = 3) -> Tuple[Optional[int], Optional[float]]:
    best_lag: Optional[int] = None
    best_corr: Optional[float] = None
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            x_slice = xs[: len(xs) - lag] if lag > 0 else xs
            y_slice = ys[lag:]
        else:
            x_slice = xs[-lag:]
            y_slice = ys[: len(ys) + lag]
        if len(x_slice) < 5 or len(y_slice) < 5:
            continue
        corr = _pearson_corr(x_slice, y_slice)
        if corr is None:
            continue
        if best_corr is None or abs(corr) > abs(best_corr):
            best_lag = lag
            best_corr = corr
    return best_lag, best_corr


def _count_abrupt_steps(values: List[float]) -> int:
    if len(values) < 4:
        return 0
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    stats = _basic_stats(deltas)
    if not stats or stats["std"] <= 0:
        return 0
    threshold = 3.0 * stats["std"]
    return sum(1 for delta in deltas if abs(delta - stats["mean"]) >= threshold)


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
    assumptions: Optional[List[str]] = None,
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
    return _result_with_capability(
        DeterministicCalculatorResult(
            available=False,
            reason=reason,
            assumptions=assumptions or [],
        ),
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
    return _result_with_capability(
        DeterministicCalculatorResult(
            available=True,
            metrics={
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
            assumptions=[
                "WOW mean threshold 0.5 is used to separate on-ground vs airborne states.",
                "Ground-roll distance is integrated from available ground-speed samples with a trapezoidal method.",
                "Time gaps > 10s are ignored during distance integration to avoid sparse-interval distortion.",
                "No certification correction inputs (wind/runway slope/atmosphere/screen-height) are applied.",
            ],
        ),
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
    return _result_with_capability(
        DeterministicCalculatorResult(
            available=True,
            metrics={
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
            assumptions=[
                "Touchdown is detected from WOW airborne-to-ground transition with speed sanity threshold.",
                "Rollout distance is integrated from touchdown to low-speed rollout end using ground-speed samples.",
                "Low-speed rollout end threshold defaults to approximately 8 kt when stop is not directly observed.",
                "No certification correction inputs (wind/runway/braking normalization/screen-height) are applied.",
            ],
        ),
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


def _convert_temperature_to_c(value: float, unit: Optional[str]) -> float:
    u = (unit or "").strip().lower().replace("°", "")
    if "f" in u:
        return (value - 32.0) * (5.0 / 9.0)
    if "k" in u and "kt" not in u:
        return value - 273.15
    return value


def _convert_speed_to_knots(value: float, unit: Optional[str]) -> float:
    u = (unit or "").strip().lower()
    if "m/s" in u:
        return value * 1.9438444924406
    if "km/h" in u or "kph" in u:
        return value * 0.53995680345572
    if "mph" in u:
        return value * 0.86897624190065
    return value


def _round_summary(summary: Optional[dict], digits: int = 3) -> Optional[dict]:
    if not summary:
        return None
    rounded: Dict[str, Any] = {}
    for key, value in summary.items():
        if key == "samples":
            rounded[key] = int(round(float(value)))
            continue
        rounded[key] = round(float(value), digits)
    return rounded


def _compute_air_data_support(
    *,
    points: List[Dict[str, Any]],
    param_map: Dict[int, dict],
    pressure_altitude_id: Optional[int],
    altitude_id: Optional[int],
    oat_id: Optional[int],
    sat_id: Optional[int],
    tat_id: Optional[int],
    cas_id: Optional[int],
    tas_id: Optional[int],
    mach_id: Optional[int],
) -> dict:
    channels_used: List[str] = []
    skipped: List[str] = []

    def _channel_name(param_id: Optional[int]) -> Optional[str]:
        if param_id is None:
            return None
        return str(param_map.get(param_id, {}).get("name") or "")

    for pid in [pressure_altitude_id, altitude_id, oat_id, sat_id, tat_id, cas_id, tas_id, mach_id]:
        name = _channel_name(pid)
        if name and name not in channels_used:
            channels_used.append(name)

    pa_values_ft: List[float] = []
    oat_values_c: List[float] = []
    sat_values_c: List[float] = []
    tat_values_c: List[float] = []
    cas_values_kt: List[float] = []
    tas_values_kt: List[float] = []
    mach_values: List[float] = []
    isa_sigma_values: List[float] = []
    isa_theta_values: List[float] = []
    isa_delta_values: List[float] = []
    density_alt_values_ft: List[float] = []
    tas_est_values_kt: List[float] = []
    mach_est_values: List[float] = []
    tas_abs_diff_values_kt: List[float] = []
    mach_abs_diff_values: List[float] = []
    pa_alt_abs_diff_values_ft: List[float] = []
    mach_temp_source_counts: Dict[str, int] = {"sat": 0, "oat": 0, "tat": 0}

    for point in points:
        pa_ft = None
        if pressure_altitude_id is not None and point.get("pressure_altitude") is not None:
            pa_unit = param_map.get(pressure_altitude_id, {}).get("unit")
            pa_ft = _convert_altitude_to_ft(float(point["pressure_altitude"]), pa_unit)
            pa_values_ft.append(pa_ft)

        altitude_ft = None
        if altitude_id is not None and point.get("altitude") is not None:
            altitude_unit = param_map.get(altitude_id, {}).get("unit")
            altitude_ft = _convert_altitude_to_ft(float(point["altitude"]), altitude_unit)

        if pa_ft is not None and altitude_ft is not None and pressure_altitude_id != altitude_id:
            pa_alt_abs_diff_values_ft.append(abs(pa_ft - altitude_ft))

        oat_c = None
        if oat_id is not None and point.get("oat") is not None:
            oat_unit = param_map.get(oat_id, {}).get("unit")
            oat_c = _convert_temperature_to_c(float(point["oat"]), oat_unit)
            oat_values_c.append(oat_c)

        sat_c = None
        if sat_id is not None and point.get("sat") is not None:
            sat_unit = param_map.get(sat_id, {}).get("unit")
            sat_c = _convert_temperature_to_c(float(point["sat"]), sat_unit)
            sat_values_c.append(sat_c)

        tat_c = None
        if tat_id is not None and point.get("tat") is not None:
            tat_unit = param_map.get(tat_id, {}).get("unit")
            tat_c = _convert_temperature_to_c(float(point["tat"]), tat_unit)
            tat_values_c.append(tat_c)

        cas_kt = None
        if cas_id is not None and point.get("cas") is not None:
            cas_unit = param_map.get(cas_id, {}).get("unit")
            cas_kt = _convert_speed_to_knots(float(point["cas"]), cas_unit)
            cas_values_kt.append(cas_kt)

        tas_kt_measured = None
        if tas_id is not None and point.get("tas") is not None:
            tas_unit = param_map.get(tas_id, {}).get("unit")
            tas_kt_measured = _convert_speed_to_knots(float(point["tas"]), tas_unit)
            tas_values_kt.append(tas_kt_measured)

        mach_measured = None
        if mach_id is not None and point.get("mach") is not None:
            mach_measured = float(point["mach"])
            mach_values.append(mach_measured)

        isa_snapshot = isa_atmosphere_from_pressure_altitude_ft(pa_ft) if pa_ft is not None else None
        if isa_snapshot is not None:
            isa_sigma_values.append(float(isa_snapshot["sigma"]))
            isa_theta_values.append(float(isa_snapshot["theta"]))
            isa_delta_values.append(float(isa_snapshot["delta"]))

        if pa_ft is not None and oat_c is not None:
            density_alt = density_altitude_estimate_ft(pa_ft, oat_c)
            if density_alt is not None:
                density_alt_values_ft.append(float(density_alt))

        tas_kt_for_mach = tas_kt_measured
        if cas_kt is not None and isa_snapshot is not None:
            tas_est = estimate_tas_from_cas_and_sigma_knots(cas_kt, float(isa_snapshot["sigma"]))
            if tas_est is not None:
                tas_est_values_kt.append(float(tas_est))
                if tas_kt_measured is not None:
                    tas_abs_diff_values_kt.append(abs(float(tas_est) - tas_kt_measured))
                if tas_kt_for_mach is None:
                    tas_kt_for_mach = float(tas_est)

        temp_for_mach = None
        if sat_c is not None:
            temp_for_mach = sat_c
            mach_temp_source_counts["sat"] += 1
        elif oat_c is not None:
            temp_for_mach = oat_c
            mach_temp_source_counts["oat"] += 1
        elif tat_c is not None:
            temp_for_mach = tat_c
            mach_temp_source_counts["tat"] += 1

        if tas_kt_for_mach is not None and temp_for_mach is not None:
            mach_est = estimate_mach_from_tas_knots_and_temperature_c(
                tas_knots=float(tas_kt_for_mach),
                temperature_c=float(temp_for_mach),
            )
            if mach_est is not None:
                mach_est_values.append(float(mach_est))
                if mach_measured is not None:
                    mach_abs_diff_values.append(abs(float(mach_est) - mach_measured))

    if not pa_values_ft:
        skipped.append("ISA snapshot skipped: pressure-altitude channel unavailable.")
    if not oat_values_c:
        skipped.append("Density-altitude estimate skipped: OAT channel unavailable.")
    if not cas_values_kt:
        skipped.append("CAS-driven TAS estimate skipped: CAS channel unavailable.")
    if not tas_values_kt:
        skipped.append("Measured TAS summary unavailable: TAS channel unavailable.")
    if not mach_values:
        skipped.append("Measured Mach summary unavailable: Mach channel unavailable.")
    if not (sat_values_c or oat_values_c or tat_values_c):
        skipped.append("Mach estimate from TAS+temperature skipped: no SAT/OAT/TAT channel available.")

    dominant_mach_temp_source = max(
        mach_temp_source_counts.keys(),
        key=lambda key: mach_temp_source_counts[key],
    )
    if mach_temp_source_counts[dominant_mach_temp_source] <= 0:
        dominant_mach_temp_source = "none"

    return {
        "available": bool(
            pa_values_ft
            or oat_values_c
            or sat_values_c
            or tat_values_c
            or cas_values_kt
            or tas_values_kt
            or mach_values
        ),
        "channels_used": channels_used,
        "skipped_calculations": skipped,
        "mach_temperature_source": dominant_mach_temp_source,
        "pressure_altitude_ft": _round_summary(summarize_air_data_series(pa_values_ft), digits=2),
        "oat_c": _round_summary(summarize_air_data_series(oat_values_c), digits=2),
        "sat_c": _round_summary(summarize_air_data_series(sat_values_c), digits=2),
        "tat_c": _round_summary(summarize_air_data_series(tat_values_c), digits=2),
        "cas_kt": _round_summary(summarize_air_data_series(cas_values_kt), digits=2),
        "tas_kt": _round_summary(summarize_air_data_series(tas_values_kt), digits=2),
        "mach": _round_summary(summarize_air_data_series(mach_values), digits=4),
        "isa_sigma": _round_summary(summarize_air_data_series(isa_sigma_values), digits=4),
        "isa_theta": _round_summary(summarize_air_data_series(isa_theta_values), digits=4),
        "isa_delta": _round_summary(summarize_air_data_series(isa_delta_values), digits=4),
        "density_altitude_ft": _round_summary(summarize_air_data_series(density_alt_values_ft), digits=1),
        "tas_est_from_cas_sigma_kt": _round_summary(
            summarize_air_data_series(tas_est_values_kt), digits=2
        ),
        "mach_est_from_tas_temp": _round_summary(
            summarize_air_data_series(mach_est_values), digits=4
        ),
        "tas_est_vs_measured_abs_diff_kt": _round_summary(
            summarize_air_data_series(tas_abs_diff_values_kt), digits=2
        ),
        "mach_est_vs_measured_abs_diff": _round_summary(
            summarize_air_data_series(mach_abs_diff_values), digits=4
        ),
        "pressure_vs_altitude_abs_diff_ft": _round_summary(
            summarize_air_data_series(pa_alt_abs_diff_values_ft), digits=2
        ),
    }


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

    pressure_altitude_id = _choose_param_id(params, _score_pressure_altitude)
    altitude_id = _choose_param_id(params, _score_altitude)
    if pressure_altitude_id is None:
        pressure_altitude_id = altitude_id
    vertical_speed_id = _choose_param_id(params, _score_vertical_speed)
    ground_speed_id = _choose_param_id(params, _score_ground_speed)
    accel_id = _choose_param_id(params, _score_longitudinal_accel)
    oat_id = _choose_param_id(params, _score_oat)
    sat_id = _choose_param_id(params, _score_sat)
    tat_id = _choose_param_id(params, _score_tat)
    cas_id = _choose_param_id(params, _score_cas)
    tas_id = _choose_param_id(params, _score_tas)
    mach_id = _choose_param_id(params, _score_mach)
    param_map = {p["id"]: p for p in params}

    selected_ids = sorted(
        {
            pid
            for pid in [
                pressure_altitude_id,
                altitude_id,
                vertical_speed_id,
                ground_speed_id,
                accel_id,
                oat_id,
                sat_id,
                tat_id,
                cas_id,
                tas_id,
                mach_id,
            ]
            if pid is not None
        }
    )
    available_signals = set()
    if altitude_id is not None:
        available_signals.add("altitude")
    if pressure_altitude_id is not None:
        available_signals.add("pressure_altitude")
    if vertical_speed_id is not None:
        available_signals.add("vertical_speed")
    if ground_speed_id is not None:
        available_signals.add("ground_speed")
    if accel_id is not None:
        available_signals.add("longitudinal_acceleration")
    if any(pid is not None for pid in [oat_id, sat_id, tat_id]):
        available_signals.add("temperature")
    if any(pid is not None for pid in [cas_id, tas_id, mach_id]):
        available_signals.add("air_data_speed")
    if any(
        pid is not None
        for pid in [pressure_altitude_id, oat_id, sat_id, tat_id, cas_id, tas_id, mach_id]
    ):
        available_signals.add("atmosphere_air_data")

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
                "pressure_altitude": (
                    values.get(pressure_altitude_id) if pressure_altitude_id is not None else None
                ),
                "altitude": values.get(altitude_id) if altitude_id is not None else None,
                "vertical_speed": values.get(vertical_speed_id) if vertical_speed_id is not None else None,
                "ground_speed": values.get(ground_speed_id) if ground_speed_id is not None else None,
                "accel": values.get(accel_id) if accel_id is not None else None,
                "oat": values.get(oat_id) if oat_id is not None else None,
                "sat": values.get(sat_id) if sat_id is not None else None,
                "tat": values.get(tat_id) if tat_id is not None else None,
                "cas": values.get(cas_id) if cas_id is not None else None,
                "tas": values.get(tas_id) if tas_id is not None else None,
                "mach": values.get(mach_id) if mach_id is not None else None,
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

    air_data_support = _compute_air_data_support(
        points=points,
        param_map=param_map,
        pressure_altitude_id=pressure_altitude_id,
        altitude_id=altitude_id,
        oat_id=oat_id,
        sat_id=sat_id,
        tat_id=tat_id,
        cas_id=cas_id,
        tas_id=tas_id,
        mach_id=mach_id,
    )

    evaluation = evaluate_capability_request(
        "performance_general",
        available_signals=available_signals,
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    return _result_with_capability(
        DeterministicCalculatorResult(
            available=True,
            metrics={
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
            "air_data_support": air_data_support,
            },
            assumptions=[
                "Metrics are computed only from available channels in the selected dataset version.",
                "Mean climb rate is derived from vertical-speed channel when present, otherwise altitude/time fallback.",
                "Atmosphere/air-data outputs use ISA and low-compressibility engineering approximations from available telemetry.",
                "No formal pitot-static calibration, full air-data correction campaign, thrust model, or certification correction model is applied in this bounded mode.",
            ],
        ),
        evaluation,
    )


def _classify_buffet_channel_group(name: str, unit: Optional[str]) -> str:
    n = (name or "").lower()
    u = (unit or "").lower()
    if "vibration" in n or "buffet" in n or re.search(r"\bvib\b", n):
        return "structural_vibration"
    if "accel" in n or u in {"g", "m/s2", "m/s^2"}:
        return "accelerations"
    if any(token in n for token in ["roll rate", "pitch rate", "yaw rate"]) or u in {"deg/s", "rad/s"}:
        return "angular_rates"
    if any(token in n for token in ["speed", "mach", "dynamic pressure", "qbar", "tas", "cas"]):
        return "airspeed_response"
    return "other_response"


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _series_time_steps_seconds(series: List[Tuple[Any, float]]) -> List[float]:
    steps: List[float] = []
    for idx in range(1, len(series)):
        dt = (series[idx][0] - series[idx - 1][0]).total_seconds()
        if dt > 0:
            steps.append(dt)
    return steps


def _estimate_frequency_screening(
    series: List[Tuple[Any, float]],
) -> Dict[str, Any]:
    if len(series) < 32:
        return {"available": False, "reason": "insufficient_samples"}

    dts = _series_time_steps_seconds(series)
    if len(dts) < 16:
        return {"available": False, "reason": "insufficient_timestamp_resolution"}
    median_dt = _median(dts)
    if median_dt is None or median_dt <= 0:
        return {"available": False, "reason": "invalid_sample_interval"}

    cadence_jitter = max(abs(dt - median_dt) / median_dt for dt in dts)
    if cadence_jitter > 0.25:
        return {"available": False, "reason": "irregular_sample_cadence"}

    values = [float(v) for _, v in series]
    mean_val = sum(values) / len(values)
    centered = [v - mean_val for v in values]
    if max(abs(v) for v in centered) <= 1e-9:
        return {"available": False, "reason": "low_signal_variability"}

    downsample_step = max(1, math.ceil(len(centered) / 512))
    if downsample_step > 1:
        centered = centered[::downsample_step]
    n = len(centered)
    if n < 32:
        return {"available": False, "reason": "insufficient_samples_after_downsample"}

    effective_dt = median_dt * downsample_step
    sample_rate_hz = 1.0 / effective_dt
    max_k = min(n // 2, 128)
    if max_k < 2:
        return {"available": False, "reason": "insufficient_frequency_bins"}

    powers: List[Tuple[float, float]] = []
    two_pi_over_n = 2.0 * math.pi / n
    for k in range(1, max_k + 1):
        re_sum = 0.0
        im_sum = 0.0
        for idx, value in enumerate(centered):
            angle = two_pi_over_n * k * idx
            re_sum += value * math.cos(angle)
            im_sum -= value * math.sin(angle)
        power = (re_sum * re_sum + im_sum * im_sum) / (n * n)
        freq_hz = (k * sample_rate_hz) / n
        powers.append((freq_hz, power))

    if not powers:
        return {"available": False, "reason": "no_frequency_energy"}
    dominant_freq_hz, dominant_power = max(powers, key=lambda item: item[1])
    if dominant_power <= 1e-12:
        return {"available": False, "reason": "low_spectral_energy"}

    total_power = sum(power for _, power in powers)
    low_power = sum(power for freq, power in powers if freq <= 2.0)
    mid_power = sum(power for freq, power in powers if 2.0 < freq <= 8.0)
    high_power = sum(power for freq, power in powers if freq > 8.0)
    band_distribution = {
        "low_0_2hz": round((low_power / total_power), 4) if total_power > 0 else 0.0,
        "mid_2_8hz": round((mid_power / total_power), 4) if total_power > 0 else 0.0,
        "high_gt8hz": round((high_power / total_power), 4) if total_power > 0 else 0.0,
    }
    dominant_amplitude = math.sqrt(max(dominant_power, 0.0))

    return {
        "available": True,
        "sample_rate_hz": round(sample_rate_hz, 4),
        "nyquist_hz": round(sample_rate_hz / 2.0, 4),
        "cadence_jitter_ratio": round(cadence_jitter, 4),
        "samples_used": n,
        "dominant_frequency_hz": round(dominant_freq_hz, 4),
        "dominant_amplitude": round(dominant_amplitude, 6),
        "band_energy_distribution": band_distribution,
    }


def _build_channel_anomaly_windows(
    *,
    series: List[Tuple[Any, float]],
    mean_val: float,
    std_val: float,
    p95_abs: Optional[float],
    channel_name: str,
    channel_group: str,
    channel_unit: Optional[str],
) -> List[Dict[str, Any]]:
    if len(series) < 5:
        return []
    threshold = max(
        (3.0 * std_val) if std_val > 0 else 0.0,
        (0.6 * float(p95_abs)) if p95_abs is not None else 0.0,
    )
    if threshold <= 0:
        return []

    exceedance_indices: List[int] = []
    for idx, (_, value) in enumerate(series):
        if abs(value - mean_val) >= threshold:
            exceedance_indices.append(idx)
    if not exceedance_indices:
        return []

    steps = _series_time_steps_seconds(series)
    median_dt = _median(steps) or 0.0
    merge_gap_s = max(2.0 * median_dt, 0.25) if median_dt > 0 else 0.5

    windows: List[Tuple[int, int]] = []
    current_start = exceedance_indices[0]
    current_end = exceedance_indices[0]
    for idx in exceedance_indices[1:]:
        prev_ts = series[current_end][0]
        current_ts = series[idx][0]
        gap = (current_ts - prev_ts).total_seconds()
        if gap <= merge_gap_s:
            current_end = idx
        else:
            windows.append((current_start, current_end))
            current_start = idx
            current_end = idx
    windows.append((current_start, current_end))

    out: List[Dict[str, Any]] = []
    for start_idx, end_idx in windows:
        win_series = series[start_idx : end_idx + 1]
        win_values = [value for _, value in win_series]
        win_deltas = [abs(v - mean_val) for v in win_values]
        midpoint_idx = start_idx + ((end_idx - start_idx) // 2)
        out.append(
            {
                "channel_name": channel_name,
                "channel_group": channel_group,
                "channel_unit": channel_unit,
                "start_timestamp": win_series[0][0].isoformat(),
                "end_timestamp": win_series[-1][0].isoformat(),
                "midpoint_timestamp": series[midpoint_idx][0].isoformat(),
                "samples": len(win_series),
                "peak_abs": round(max(abs(v) for v in win_values), 4),
                "peak_deviation": round(max(win_deltas), 4),
                "mean_deviation": round(sum(win_deltas) / len(win_deltas), 4),
            }
        )
    return out


def _speed_band(speed_kt: Optional[float], low_cut: Optional[float], high_cut: Optional[float]) -> str:
    if speed_kt is None or low_cut is None or high_cut is None:
        return "unspecified"
    if speed_kt <= low_cut:
        return "low_speed"
    if speed_kt <= high_cut:
        return "mid_speed"
    return "high_speed"


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

    ground_speed_id = _choose_param_id(params, _score_ground_speed)
    wow_ids = [p["id"] for p in params if _score_wow(p["name"], p.get("unit")) > 0]
    support_ids = [pid for pid in [ground_speed_id, *wow_ids] if pid is not None]

    rows = _load_timeseries_rows(
        db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        parameter_ids=sorted({*([p["id"] for p in selected]), *support_ids}),
    )
    if not rows:
        return _unavailable_metrics(
            capability_key="buffet_vibration",
            reason="No datapoints found for vibration screening channels.",
            available_signals=["accelerometers"],
            has_dataset=False,
        )

    selected_ids = {p["id"] for p in selected}
    param_map = {p["id"]: p for p in params}
    channel_series: Dict[int, List[Tuple[Any, float]]] = defaultdict(list)
    timeline: Dict[Any, Dict[int, float]] = defaultdict(dict)

    for row in rows:
        pid = int(row.parameter_id)
        value = float(row.value)
        ts = row.timestamp
        timeline[ts][pid] = value
        if pid in selected_ids:
            channel_series[pid].append((ts, value))

    channel_summaries = []
    anomaly_windows: List[Dict[str, Any]] = []
    for p in selected:
        series = sorted(channel_series.get(p["id"], []), key=lambda item: item[0])
        values = [value for _, value in series]
        if len(values) < 5:
            continue
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_val = math.sqrt(max(variance, 0.0))
        rms = math.sqrt(sum(v * v for v in values) / len(values))
        abs_values = [abs(v) for v in values]
        p95_abs = _percentile(abs_values, 0.95)
        threshold = max((3.0 * std_val) if std_val > 0 else 0.0, (0.6 * p95_abs) if p95_abs is not None else 0.0)
        exceedance_count = sum(1 for v in values if threshold > 0 and abs(v - mean_val) >= threshold)
        group = _classify_buffet_channel_group(p["name"], p.get("unit"))
        dominance_score = (
            (max(abs_values) * 0.45)
            + (rms * 0.35)
            + ((p95_abs or 0.0) * 0.15)
            + (float(exceedance_count) * 0.05)
        )
        steps = _series_time_steps_seconds(series)
        median_dt = _median(steps)

        channel_windows = _build_channel_anomaly_windows(
            series=series,
            mean_val=mean_val,
            std_val=std_val,
            p95_abs=p95_abs,
            channel_name=p["name"],
            channel_group=group,
            channel_unit=p.get("unit"),
        )
        anomaly_windows.extend(channel_windows)
        channel_summaries.append(
            {
                "parameter_id": p["id"],
                "name": p["name"],
                "group": group,
                "unit": p.get("unit"),
                "samples": len(values),
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "rms": round(rms, 4),
                "peak_abs": round(max(abs_values), 4),
                "p95_abs": round(p95_abs, 4) if p95_abs is not None else None,
                "exceedance_count": exceedance_count,
                "dominance_score": round(dominance_score, 4),
                "median_dt_s": round(median_dt, 4) if median_dt is not None else None,
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

    channel_summaries.sort(key=lambda item: item["dominance_score"], reverse=True)
    dominant = channel_summaries[0]

    grouped_items: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in channel_summaries:
        grouped_items[str(item["group"])].append(item)

    grouped_channel_summaries: List[Dict[str, Any]] = []
    for group_key, items in grouped_items.items():
        ranked = sorted(items, key=lambda entry: entry["dominance_score"], reverse=True)
        grouped_channel_summaries.append(
            {
                "group": group_key,
                "channels": len(ranked),
                "dominant_channel": ranked[0]["name"],
                "dominant_peak_abs": ranked[0]["peak_abs"],
                "total_exceedances": sum(int(entry["exceedance_count"]) for entry in ranked),
                "mean_rms": round(sum(float(entry["rms"]) for entry in ranked) / len(ranked), 4),
            }
        )
    grouped_channel_summaries.sort(key=lambda item: item["dominant_peak_abs"], reverse=True)

    dominant_channels_ranked: List[Dict[str, Any]] = []
    for rank, summary in enumerate(channel_summaries[:6], start=1):
        dominant_channels_ranked.append(
            {
                "rank": rank,
                "name": summary["name"],
                "group": summary["group"],
                "unit": summary["unit"],
                "dominance_score": summary["dominance_score"],
                "peak_abs": summary["peak_abs"],
                "rms": summary["rms"],
                "p95_abs": summary["p95_abs"],
                "exceedance_count": summary["exceedance_count"],
            }
        )

    ordered_timestamps = sorted(timeline.keys())
    speed_values = [
        timeline[ts].get(ground_speed_id)
        for ts in ordered_timestamps
        if ground_speed_id is not None and timeline[ts].get(ground_speed_id) is not None
    ]
    speed_low_cut = _percentile([float(v) for v in speed_values], 0.33) if speed_values else None
    speed_high_cut = _percentile([float(v) for v in speed_values], 0.67) if speed_values else None

    regime_by_timestamp: Dict[Any, str] = {}
    regime_by_iso_timestamp: Dict[str, str] = {}
    regime_accumulator: Dict[str, Dict[str, Any]] = {}
    for ts in ordered_timestamps:
        row_values = timeline[ts]
        speed = row_values.get(ground_speed_id) if ground_speed_id is not None else None
        wow_values = [row_values[wow_id] for wow_id in wow_ids if wow_id in row_values]
        wow_mean = (sum(wow_values) / len(wow_values)) if wow_values else None
        phase = "unknown_phase"
        if wow_mean is not None:
            phase = "ground" if _is_ground(float(speed or 0.0), wow_mean) else "airborne"
        speed_band = _speed_band(float(speed), speed_low_cut, speed_high_cut) if speed is not None else "unspecified"
        regime_key = f"{phase}_{speed_band}" if speed_band != "unspecified" else phase
        regime_by_timestamp[ts] = regime_key
        regime_by_iso_timestamp[ts.isoformat()] = regime_key

        regime = regime_accumulator.setdefault(
            regime_key,
            {
                "samples": 0,
                "speed_values": [],
                "wow_values": [],
                "channel_peak_abs": defaultdict(float),
            },
        )
        regime["samples"] += 1
        if speed is not None:
            regime["speed_values"].append(float(speed))
        if wow_mean is not None:
            regime["wow_values"].append(float(wow_mean))
        for summary in channel_summaries:
            pid = summary.get("parameter_id")
            if pid is None:
                continue
            if pid in row_values:
                abs_val = abs(float(row_values[pid]))
                if abs_val > regime["channel_peak_abs"][summary["name"]]:
                    regime["channel_peak_abs"][summary["name"]] = abs_val

    event_counts_by_regime: Dict[str, int] = defaultdict(int)
    for window in anomaly_windows:
        midpoint_raw = window.get("midpoint_timestamp")
        regime_key = regime_by_iso_timestamp.get(str(midpoint_raw), "unknown_phase")
        window["regime"] = regime_key
        event_counts_by_regime[regime_key] += 1

    anomaly_windows.sort(key=lambda item: item["peak_deviation"], reverse=True)
    anomaly_windows = anomaly_windows[:8]

    regime_segmentation_summary: List[Dict[str, Any]] = []
    for regime_key, data in regime_accumulator.items():
        peak_map: Dict[str, float] = data["channel_peak_abs"]
        dominant_channel_name = None
        dominant_peak_abs = None
        if peak_map:
            dominant_channel_name, dominant_peak_abs = max(peak_map.items(), key=lambda item: item[1])
        speed_summary = summarize_air_data_series(data["speed_values"]) if data["speed_values"] else None
        wow_summary = summarize_air_data_series(data["wow_values"]) if data["wow_values"] else None
        regime_segmentation_summary.append(
            {
                "regime": regime_key,
                "samples": int(data["samples"]),
                "events_detected": int(event_counts_by_regime.get(regime_key, 0)),
                "dominant_channel": dominant_channel_name,
                "dominant_peak_abs": round(float(dominant_peak_abs), 4)
                if dominant_peak_abs is not None
                else None,
                "mean_speed_kt": round(float(speed_summary["mean"]), 3) if speed_summary else None,
                "mean_wow": round(float(wow_summary["mean"]), 3) if wow_summary else None,
            }
        )
    regime_segmentation_summary.sort(key=lambda item: item["samples"], reverse=True)

    frequency_channel_summaries: List[Dict[str, Any]] = []
    frequency_skips: List[Dict[str, str]] = []
    top_frequency_candidates = channel_summaries[:3]
    for summary in top_frequency_candidates:
        channel_pid = summary.get("parameter_id")
        if channel_pid is None:
            continue
        series = sorted(channel_series.get(channel_pid, []), key=lambda item: item[0])
        result = _estimate_frequency_screening(series)
        if result.get("available"):
            frequency_channel_summaries.append(
                {
                    "channel": summary["name"],
                    "group": summary["group"],
                    "unit": summary.get("unit"),
                    **result,
                }
            )
        else:
            frequency_skips.append(
                {
                    "channel": summary["name"],
                    "reason": str(result.get("reason", "unknown")),
                }
            )

    frequency_screening = {
        "available": bool(frequency_channel_summaries),
        "channels_attempted": len(top_frequency_candidates),
        "channels_analyzed": len(frequency_channel_summaries),
        "channels_skipped": len(frequency_skips),
        "channel_summaries": frequency_channel_summaries,
        "skipped_channels": frequency_skips,
    }

    evaluation = evaluate_capability_request(
        "buffet_vibration",
        available_signals=["accelerometers", "angular_rate"],
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    return _result_with_capability(
        DeterministicCalculatorResult(
            available=True,
            metrics={
            "available": True,
            "channels_screened": len(channel_summaries),
            "dominant_channel": dominant["name"],
            "dominant_peak_abs": dominant["peak_abs"],
            "dominant_unit": dominant["unit"],
            "channels_with_exceedances": sum(1 for c in channel_summaries if c["exceedance_count"] > 0),
            "samples_used": sum(int(c.get("samples", 0)) for c in channel_summaries),
            "channel_summaries": channel_summaries[:6],
            "grouped_channel_summaries": grouped_channel_summaries,
            "dominant_channels_ranked": dominant_channels_ranked,
            "regime_segmentation_summary": regime_segmentation_summary,
            "anomaly_windows": anomaly_windows,
            "frequency_screening": frequency_screening,
            "regime_logic": (
                "Phase uses WOW threshold (>=0.5 ground / <0.5 airborne) when available; "
                "speed bands use dataset terciles when ground speed is available."
            ),
            },
            assumptions=[
                "This mode performs descriptive screening (RMS/peaks/spread/exceedance) on available vibration-like channels.",
                "Anomaly windows are built from bounded threshold exceedances and merged by short cadence-aware gaps.",
                "Regime segmentation is a bounded heuristic based on WOW and speed-band cues when available.",
                "Frequency-domain summaries are produced only when cadence regularity and sample coverage are adequate.",
                "Output is screening support only and does not represent formal loads substantiation or flutter clearance.",
            ],
        ),
        evaluation,
    )


def compute_handling_qualities_metrics(
    db: Session,
    flight_test_id: int,
    dataset_version_id: Optional[int] = None,
    request_certification_result: bool = False,
) -> dict:
    """Compute bounded deterministic handling/control-response metrics."""
    del request_certification_result
    params = _load_parameter_catalog(db, flight_test_id, dataset_version_id)
    if not params:
        return _unavailable_metrics(
            capability_key="handling_qualities",
            reason="No parameters found for flight test.",
            available_signals=[],
            has_dataset=False,
        )

    controls: Dict[str, Optional[int]] = {
        "aileron": _choose_param_id(params, _score_aileron),
        "elevator": _choose_param_id(params, _score_elevator),
        "rudder": _choose_param_id(params, _score_rudder),
        "stick_lateral": _choose_param_id(params, _score_stick_lateral),
        "stick_longitudinal": _choose_param_id(params, _score_stick_longitudinal),
    }
    responses: Dict[str, Optional[int]] = {
        "roll_rate": _choose_param_id(params, _score_roll_rate),
        "pitch_rate": _choose_param_id(params, _score_pitch_rate),
        "yaw_rate": _choose_param_id(params, _score_yaw_rate),
        "roll_angle": _choose_param_id(params, _score_roll_angle),
        "pitch_angle": _choose_param_id(params, _score_pitch_angle),
        "heading": _choose_param_id(params, _score_heading),
    }

    selected_ids = {
        pid
        for pid in [*controls.values(), *responses.values()]
        if pid is not None
    }
    available_signals = set()
    if any(controls.values()):
        available_signals.add("control_input")
    if any(responses.values()):
        available_signals.add("attitude_response")
    if any(responses.get(key) is not None for key in ["roll_rate", "pitch_rate", "yaw_rate"]):
        available_signals.add("angular_rate")

    if not any(controls.values()):
        return _unavailable_metrics(
            capability_key="handling_qualities",
            reason="No control-input channels were detected (aileron/elevator/rudder/stick).",
            available_signals=available_signals,
            has_dataset=True,
        )
    if not any(responses.values()):
        return _unavailable_metrics(
            capability_key="handling_qualities",
            reason="No response channels were detected (rates/angles/heading).",
            available_signals=available_signals,
            has_dataset=True,
        )

    rows = _load_timeseries_rows(
        db,
        flight_test_id=flight_test_id,
        dataset_version_id=dataset_version_id,
        parameter_ids=selected_ids,
    )
    if not rows:
        return _unavailable_metrics(
            capability_key="handling_qualities",
            reason="No datapoints found for detected handling/control-response channels.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=False,
            data_coverage_ok=False,
        )

    param_map = {p["id"]: p for p in params}
    timeline: Dict[Any, Dict[int, float]] = {}
    for row in rows:
        timeline.setdefault(row.timestamp, {})[int(row.parameter_id)] = float(row.value)
    ordered_timestamps = sorted(timeline.keys())

    control_channel_summaries = []
    for key, pid in controls.items():
        if pid is None:
            continue
        values = [timeline[ts][pid] for ts in ordered_timestamps if pid in timeline[ts]]
        stats = _basic_stats(values)
        if not stats:
            continue
        control_channel_summaries.append(
            {
                "key": key,
                "name": param_map.get(pid, {}).get("name"),
                "unit": param_map.get(pid, {}).get("unit"),
                "samples": len(values),
                "min": round(stats["min"], 4),
                "max": round(stats["max"], 4),
                "mean": round(stats["mean"], 4),
                "std": round(stats["std"], 4),
            }
        )

    response_channel_summaries = []
    for key, pid in responses.items():
        if pid is None:
            continue
        values = [timeline[ts][pid] for ts in ordered_timestamps if pid in timeline[ts]]
        stats = _basic_stats(values)
        if not stats:
            continue
        response_channel_summaries.append(
            {
                "key": key,
                "name": param_map.get(pid, {}).get("name"),
                "unit": param_map.get(pid, {}).get("unit"),
                "samples": len(values),
                "min": round(stats["min"], 4),
                "max": round(stats["max"], 4),
                "mean": round(stats["mean"], 4),
                "std": round(stats["std"], 4),
            }
        )

    pairing_specs: List[Tuple[str, str]] = [
        ("aileron", "roll_rate"),
        ("aileron", "roll_angle"),
        ("stick_lateral", "roll_rate"),
        ("stick_lateral", "roll_angle"),
        ("elevator", "pitch_rate"),
        ("elevator", "pitch_angle"),
        ("stick_longitudinal", "pitch_rate"),
        ("stick_longitudinal", "pitch_angle"),
        ("rudder", "yaw_rate"),
        ("rudder", "heading"),
    ]

    pairing_results = []
    for control_key, response_key in pairing_specs:
        control_id = controls.get(control_key)
        response_id = responses.get(response_key)
        if control_id is None or response_id is None:
            continue
        control_samples: List[float] = []
        response_samples: List[float] = []
        for ts in ordered_timestamps:
            values = timeline.get(ts, {})
            if control_id in values and response_id in values:
                control_samples.append(values[control_id])
                response_samples.append(values[response_id])
        if len(control_samples) < 8:
            continue

        control_stats = _basic_stats(control_samples)
        response_stats = _basic_stats(response_samples)
        if not control_stats or not response_stats:
            continue

        corr = _pearson_corr(control_samples, response_samples)
        lag_samples, lag_corr = _best_sample_lag(control_samples, response_samples, max_lag=3)

        directionality = "undetermined"
        if corr is not None:
            if corr >= 0.35:
                directionality = "positive_coupling"
            elif corr <= -0.35:
                directionality = "inverse_coupling"
            else:
                directionality = "weak_coupling"

        ctrl_centered = [value - control_stats["mean"] for value in control_samples]
        rsp_centered = [value - response_stats["mean"] for value in response_samples]
        alignment_hits = sum(
            1
            for ctrl_value, rsp_value in zip(ctrl_centered, rsp_centered)
            if (ctrl_value * rsp_value) >= 0
        )
        sign_alignment_ratio = alignment_hits / len(control_samples) if control_samples else 0.0

        anomaly_flags: List[str] = []
        response_outlier_count = 0
        if response_stats["std"] > 0:
            response_outlier_count = sum(
                1
                for value in response_samples
                if abs(value - response_stats["mean"]) >= (3.0 * response_stats["std"])
            )
        if response_outlier_count > 0:
            anomaly_flags.append(
                f"response_outliers={response_outlier_count}"
            )
        abrupt_control_steps = _count_abrupt_steps(control_samples)
        abrupt_response_steps = _count_abrupt_steps(response_samples)
        if abrupt_control_steps > 0:
            anomaly_flags.append(f"abrupt_control_steps={abrupt_control_steps}")
        if abrupt_response_steps > 0:
            anomaly_flags.append(f"abrupt_response_steps={abrupt_response_steps}")
        if corr is not None and abs(corr) < 0.2:
            anomaly_flags.append("low_correlation")

        pairing_results.append(
            {
                "pairing_key": f"{control_key}->{response_key}",
                "control_channel_name": param_map.get(control_id, {}).get("name"),
                "response_channel_name": param_map.get(response_id, {}).get("name"),
                "control_unit": param_map.get(control_id, {}).get("unit"),
                "response_unit": param_map.get(response_id, {}).get("unit"),
                "samples": len(control_samples),
                "control_min": round(control_stats["min"], 4),
                "control_max": round(control_stats["max"], 4),
                "control_mean": round(control_stats["mean"], 4),
                "control_std": round(control_stats["std"], 4),
                "response_min": round(response_stats["min"], 4),
                "response_max": round(response_stats["max"], 4),
                "response_mean": round(response_stats["mean"], 4),
                "response_std": round(response_stats["std"], 4),
                "pearson_correlation": round(corr, 4) if corr is not None else None,
                "directionality": directionality,
                "best_lag_samples": lag_samples,
                "best_lag_correlation": round(lag_corr, 4) if lag_corr is not None else None,
                "sign_alignment_ratio": round(sign_alignment_ratio, 3),
                "anomaly_flags": anomaly_flags,
            }
        )

    if not pairing_results:
        return _unavailable_metrics(
            capability_key="handling_qualities",
            reason="No valid control-response pairing had enough synchronized samples.",
            available_signals=available_signals,
            has_dataset=True,
            has_time_series_continuity=True,
            data_coverage_ok=False,
        )

    pairing_results.sort(
        key=lambda item: abs(item.get("pearson_correlation") or 0.0),
        reverse=True,
    )
    strongest_pairing = pairing_results[0]
    aggregated_anomalies = sorted(
        {
            flag
            for pairing in pairing_results
            for flag in (pairing.get("anomaly_flags") or [])
        }
    )

    evaluation = evaluate_capability_request(
        "handling_qualities",
        available_signals=available_signals,
        has_dataset=True,
        has_time_series_continuity=True,
        data_coverage_ok=True,
    )
    return _result_with_capability(
        DeterministicCalculatorResult(
            available=True,
            metrics={
                "available": True,
                "pairings_analyzed": len(pairing_results),
                "pairing_results": pairing_results[:8],
                "control_channels_used": [item["name"] for item in control_channel_summaries if item.get("name")],
                "response_channels_used": [item["name"] for item in response_channel_summaries if item.get("name")],
                "control_channel_summaries": control_channel_summaries[:8],
                "response_channel_summaries": response_channel_summaries[:8],
                "strongest_pairing": strongest_pairing.get("pairing_key"),
                "strongest_abs_correlation": round(
                    abs(strongest_pairing.get("pearson_correlation") or 0.0), 4
                ),
                "total_pairing_samples": sum(int(item.get("samples", 0)) for item in pairing_results),
                "anomaly_flags": aggregated_anomalies[:10],
            },
            assumptions=[
                "Control-response pairing uses deterministic channel-name heuristics and synchronized timestamp overlap.",
                "Correlation and lag indicators are bounded trend metrics and do not represent full system-identification dynamics.",
                "Anomaly flags use simple statistical thresholds (3-sigma and abrupt-step heuristics).",
                "Output is a bounded engineering handling/control-response assessment, not a formal handling-qualities certification rating.",
            ],
        ),
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
    assumptions = metrics.get("deterministic_assumptions") or []
    if assumptions:
        lines.extend(["", "### Assumptions"])
        for item in assumptions:
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
    assumptions = metrics.get("deterministic_assumptions") or []
    if assumptions:
        lines.extend(["", "### Assumptions"])
        for item in assumptions:
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
    assumptions = metrics.get("deterministic_assumptions") or []
    if assumptions:
        lines.extend(["", "### Assumptions"])
        for item in assumptions:
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

    air_data = metrics.get("air_data_support") or {}
    lines.extend(["", "### Atmosphere / Air-Data Support"])
    if air_data.get("available"):
        lines.append("- Result type: **Bounded atmosphere/air-data engineering support summary**")
        channels_used = air_data.get("channels_used") or []
        if channels_used:
            lines.append("- Channels used: " + ", ".join(channels_used))

        def _fmt_summary(label: str, key: str, unit: str = "") -> None:
            summary = air_data.get(key)
            if not summary:
                return
            unit_suffix = f" {unit}" if unit else ""
            lines.append(
                f"- {label}: mean **{summary.get('mean')}**{unit_suffix}, "
                f"min **{summary.get('min')}**, max **{summary.get('max')}** "
                f"(samples={summary.get('samples')})"
            )

        _fmt_summary("Pressure altitude", "pressure_altitude_ft", "ft")
        _fmt_summary("OAT", "oat_c", "°C")
        _fmt_summary("SAT", "sat_c", "°C")
        _fmt_summary("TAT", "tat_c", "°C")
        _fmt_summary("CAS", "cas_kt", "kt")
        _fmt_summary("TAS", "tas_kt", "kt")
        _fmt_summary("Mach (measured)", "mach", "")
        _fmt_summary("ISA sigma", "isa_sigma", "")
        _fmt_summary("Density altitude estimate", "density_altitude_ft", "ft")
        _fmt_summary("TAS estimate from CAS+sigma", "tas_est_from_cas_sigma_kt", "kt")
        _fmt_summary("Mach estimate from TAS+temperature", "mach_est_from_tas_temp", "")
        _fmt_summary("TAS estimate vs measured |Δ|", "tas_est_vs_measured_abs_diff_kt", "kt")
        _fmt_summary("Mach estimate vs measured |Δ|", "mach_est_vs_measured_abs_diff", "")
        _fmt_summary("Pressure-altitude vs altitude |Δ|", "pressure_vs_altitude_abs_diff_ft", "ft")

        mach_temp_source = air_data.get("mach_temperature_source")
        if mach_temp_source and mach_temp_source != "none":
            lines.append(
                f"- Mach estimate temperature source priority used: **{str(mach_temp_source).upper()}**"
            )
    else:
        lines.append("- Atmosphere/air-data support is unavailable for this dataset (missing relevant channels).")

    skipped = air_data.get("skipped_calculations") or []
    if skipped:
        lines.append("")
        lines.append("#### Skipped Calculations")
        for item in skipped:
            lines.append(f"- {item}")

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
    assumptions = metrics.get("deterministic_assumptions") or []
    if assumptions:
        lines.extend(["", "### Assumptions"])
        for item in assumptions:
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
        "- Classification: **Screening/support output (not loads substantiation or flutter-clearance determination)**",
        "- Applicability boundary: suitable for pre-screening and anomaly flagging only.",
        "",
        "### Screening Summary",
        f"- Channels screened: **{metrics.get('channels_screened')}**",
        (
            f"- Dominant channel: **{metrics.get('dominant_channel')}** "
            f"(peak abs {metrics.get('dominant_peak_abs')} {metrics.get('dominant_unit') or ''})"
        ),
        f"- Channels with exceedance events: **{metrics.get('channels_with_exceedances')}**",
        f"- Significant anomaly windows captured: **{len(metrics.get('anomaly_windows') or [])}**",
        "",
        "### Channel Highlights",
    ]

    for channel in metrics.get("channel_summaries", []):
        lines.append(
            (
                f"- {channel.get('name')} ({channel.get('unit') or '-'}) -> "
                f"samples={channel.get('samples')}, rms={channel.get('rms')}, "
                f"peak_abs={channel.get('peak_abs')}, p95_abs={channel.get('p95_abs')}, "
                f"exceedances={channel.get('exceedance_count')}, group={channel.get('group')}"
            )
        )

    grouped = metrics.get("grouped_channel_summaries") or []
    if grouped:
        lines.extend(["", "### Grouped Screening Summary"])
        for group in grouped:
            lines.append(
                (
                    f"- {group.get('group')}: channels={group.get('channels')}, "
                    f"dominant={group.get('dominant_channel')} (peak_abs={group.get('dominant_peak_abs')}), "
                    f"total_exceedances={group.get('total_exceedances')}, mean_rms={group.get('mean_rms')}"
                )
            )

    ranked = metrics.get("dominant_channels_ranked") or []
    if ranked:
        lines.extend(["", "### Dominant Channels (Ranked)"])
        for item in ranked:
            lines.append(
                (
                    f"- #{item.get('rank')} {item.get('name')} [{item.get('group')}] -> "
                    f"score={item.get('dominance_score')}, peak_abs={item.get('peak_abs')}, "
                    f"rms={item.get('rms')}, exceedances={item.get('exceedance_count')}"
                )
            )

    regime_logic = metrics.get("regime_logic")
    regimes = metrics.get("regime_segmentation_summary") or []
    if regimes:
        lines.extend(["", "### Regime Segmentation"])
        if regime_logic:
            lines.append(f"- Regime logic: {regime_logic}")
        for regime in regimes:
            lines.append(
                (
                    f"- {regime.get('regime')}: samples={regime.get('samples')}, "
                    f"events={regime.get('events_detected')}, dominant={regime.get('dominant_channel')}, "
                    f"dominant_peak_abs={regime.get('dominant_peak_abs')}, "
                    f"mean_speed_kt={regime.get('mean_speed_kt')}, mean_wow={regime.get('mean_wow')}"
                )
            )

    windows = metrics.get("anomaly_windows") or []
    if windows:
        lines.extend(["", "### Significant Event Windows"])
        for event in windows:
            lines.append(
                (
                    f"- {event.get('start_timestamp')} -> {event.get('end_timestamp')}: "
                    f"{event.get('channel_name')} [{event.get('channel_group')}], "
                    f"peak_abs={event.get('peak_abs')} {event.get('channel_unit') or ''}, "
                    f"peak_deviation={event.get('peak_deviation')}, samples={event.get('samples')}, "
                    f"regime={event.get('regime')}"
                )
            )

    frequency = metrics.get("frequency_screening") or {}
    lines.extend(["", "### Frequency-Domain Screening (Bounded)"])
    if frequency.get("available"):
        lines.append(
            f"- Frequency screening available for **{frequency.get('channels_analyzed')}** channel(s) "
            f"(attempted {frequency.get('channels_attempted')})."
        )
        for item in frequency.get("channel_summaries", []):
            lines.append(
                (
                    f"- {item.get('channel')} [{item.get('group')}]: "
                    f"dominant_frequency={item.get('dominant_frequency_hz')} Hz, "
                    f"dominant_amplitude={item.get('dominant_amplitude')}, "
                    f"sample_rate={item.get('sample_rate_hz')} Hz, "
                    f"cadence_jitter={item.get('cadence_jitter_ratio')}, "
                    f"bands={item.get('band_energy_distribution')}"
                )
            )
    else:
        lines.append(
            f"- Frequency screening unavailable (attempted {frequency.get('channels_attempted', 0)}, "
            f"analyzed {frequency.get('channels_analyzed', 0)})."
        )
    skipped_freq = frequency.get("skipped_channels") or []
    if skipped_freq:
        lines.append("- Skipped channels:")
        for item in skipped_freq:
            lines.append(f"  - {item.get('channel')}: {item.get('reason')}")

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
    assumptions = metrics.get("deterministic_assumptions") or []
    if assumptions:
        lines.extend(["", "### Assumptions"])
        for item in assumptions:
            lines.append(f"- {item}")
    return "\n".join(lines)


def build_deterministic_handling_qualities_section(metrics: dict) -> str:
    if not metrics.get("available"):
        return _build_unavailable_section(
            "## Deterministic Calculation (Handling / Control-Response) [DATA]",
            metrics,
        )

    lines = [
        "## Deterministic Calculation (Handling / Control-Response) [DATA]",
        "",
        "### Result Classification",
        "- Result type: **Bounded control-response deterministic assessment**",
        "- Classification: **Engineering trend/interaction summary (not formal handling-qualities certification substantiation)**",
        "- Applicability boundary: valid for available synchronized control-input and response channels only.",
        "",
        "### Coverage Summary",
        f"- Pairings analyzed: **{metrics.get('pairings_analyzed', 0)}**",
        f"- Total pairing samples: **{metrics.get('total_pairing_samples', 0)}**",
        f"- Strongest pairing (by absolute correlation): **{metrics.get('strongest_pairing', 'n/a')}**",
        f"- Strongest absolute correlation: **{metrics.get('strongest_abs_correlation', 'n/a')}**",
        "",
        "### Channels Used",
        "- Control channels: "
        + (", ".join(metrics.get("control_channels_used") or []) or "none"),
        "- Response channels: "
        + (", ".join(metrics.get("response_channels_used") or []) or "none"),
        "",
        "### Pairing Highlights",
    ]

    for pairing in metrics.get("pairing_results", []):
        lines.append(
            (
                f"- {pairing.get('pairing_key')} "
                f"({pairing.get('control_channel_name')} -> {pairing.get('response_channel_name')}): "
                f"samples={pairing.get('samples')}, corr={pairing.get('pearson_correlation')}, "
                f"directionality={pairing.get('directionality')}, lag_samples={pairing.get('best_lag_samples')}, "
                f"lag_corr={pairing.get('best_lag_correlation')}, "
                f"sign_alignment={pairing.get('sign_alignment_ratio')}, "
                f"anomalies={', '.join(pairing.get('anomaly_flags') or []) or 'none'}"
            )
        )

    aggregated_anomalies = metrics.get("anomaly_flags") or []
    if aggregated_anomalies:
        lines.extend(["", "### Aggregated Anomaly Flags"])
        for flag in aggregated_anomalies:
            lines.append(f"- {flag}")

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
    assumptions = metrics.get("deterministic_assumptions") or []
    if assumptions:
        lines.extend(["", "### Assumptions"])
        for item in assumptions:
            lines.append(f"- {item}")
    return "\n".join(lines)
