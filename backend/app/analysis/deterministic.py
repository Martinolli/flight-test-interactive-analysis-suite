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
            "channel_summaries": channel_summaries[:6],
            },
            assumptions=[
                "This mode performs descriptive screening (RMS/peaks/spread/exceedance) on available vibration-like channels.",
                "Exceedance markers use a simple 3-sigma-from-mean heuristic per channel.",
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
