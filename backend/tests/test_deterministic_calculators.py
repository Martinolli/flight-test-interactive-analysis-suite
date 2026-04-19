"""Unit tests for modular deterministic calculators introduced in P2.2."""

from datetime import datetime, timedelta

from app.analysis import (
    compute_buffet_vibration_metrics,
    compute_landing_metrics,
    compute_performance_metrics,
    compute_takeoff_metrics,
)
from app.models import DataPoint, FlightTest, TestParameter


def _make_flight_test(db_session, owner_id: int, name: str) -> FlightTest:
    flight_test = FlightTest(
        test_name=name,
        aircraft_type="F-16",
        created_by_id=owner_id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)
    return flight_test


def _make_parameter(db_session, name: str, unit: str) -> TestParameter:
    param = TestParameter(name=name, unit=unit)
    db_session.add(param)
    db_session.commit()
    db_session.refresh(param)
    return param


def test_takeoff_calculator_regression_with_wow_and_groundspeed(db_session, test_user):
    flight_test = _make_flight_test(db_session, test_user["id"], "Takeoff Calc Test")
    gs = _make_parameter(db_session, "GROUND SPEED", "kt")
    wow = _make_parameter(db_session, "WEIGHT ON WHEELS", "")

    base_ts = datetime(2026, 4, 19, 12, 0, 0)
    speed_trace = [0.0, 5.0, 20.0, 45.0, 72.0, 84.0]
    wow_trace = [1.0, 1.0, 1.0, 1.0, 0.7, 0.0]
    for i, (spd, wow_value) in enumerate(zip(speed_trace, wow_trace)):
        ts = base_ts + timedelta(seconds=i)
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=gs.id,
                timestamp=ts,
                value=spd,
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=wow.id,
                timestamp=ts,
                value=wow_value,
            )
        )
    db_session.commit()

    result = compute_takeoff_metrics(db_session, flight_test.id)
    assert result["available"] is True
    assert result["capability_key"] == "takeoff"
    assert result["distance_ft"] > 0
    assert result["capability_outcome"] in {"allow_with_limitations", "partial_estimate"}
    assert isinstance(result["deterministic_metrics"], dict)
    assert isinstance(result["deterministic_assumptions"], list)
    assert result["deterministic_metrics"]["distance_ft"] == result["distance_ft"]


def test_landing_calculator_supported_with_touchdown_transition(db_session, test_user):
    flight_test = _make_flight_test(db_session, test_user["id"], "Landing Calc Test")
    gs = _make_parameter(db_session, "GROUND SPEED", "kt")
    wow = _make_parameter(db_session, "WOW RH", "")

    base_ts = datetime(2026, 4, 19, 13, 0, 0)
    speed_trace = [135.0, 120.0, 98.0, 76.0, 44.0, 18.0, 6.0]
    wow_trace = [0.0, 0.0, 0.3, 1.0, 1.0, 1.0, 1.0]
    for i, (spd, wow_value) in enumerate(zip(speed_trace, wow_trace)):
        ts = base_ts + timedelta(seconds=i)
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=gs.id,
                timestamp=ts,
                value=spd,
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=wow.id,
                timestamp=ts,
                value=wow_value,
            )
        )
    db_session.commit()

    result = compute_landing_metrics(db_session, flight_test.id)
    assert result["available"] is True
    assert result["capability_key"] == "landing"
    assert result["distance_ft"] > 0
    assert result["touchdown_speed_kt"] >= result["rollout_end_speed_kt"]
    assert "deterministic_metrics" in result
    assert len(result["deterministic_assumptions"]) > 0


def test_landing_calculator_blocks_when_wow_signal_missing(db_session, test_user):
    flight_test = _make_flight_test(db_session, test_user["id"], "Landing Missing WOW Test")
    gs = _make_parameter(db_session, "GROUND SPEED", "kt")
    base_ts = datetime(2026, 4, 19, 13, 30, 0)
    for i, spd in enumerate([130.0, 118.0, 95.0, 70.0]):
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=gs.id,
                timestamp=base_ts + timedelta(seconds=i),
                value=spd,
            )
        )
    db_session.commit()

    result = compute_landing_metrics(db_session, flight_test.id)
    assert result["available"] is False
    assert result["capability_reason_key"] == "missing_required_signals"
    assert "Weight-on-wheels" in result["reason"] or "Weight-on-wheels".lower() in result["reason"].lower()


def test_performance_calculator_returns_non_takeoff_metrics(db_session, test_user):
    flight_test = _make_flight_test(db_session, test_user["id"], "Performance Calc Test")
    alt = _make_parameter(db_session, "PRESSURE ALTITUDE", "ft")
    gs = _make_parameter(db_session, "GROUND SPEED", "kt")
    base_ts = datetime(2026, 4, 19, 14, 0, 0)
    alt_values = [5000.0, 5100.0, 5235.0, 5400.0]
    gs_values = [120.0, 126.0, 133.0, 140.0]
    for i, (a, s) in enumerate(zip(alt_values, gs_values)):
        ts = base_ts + timedelta(seconds=5 * i)
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=alt.id,
                timestamp=ts,
                value=a,
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=gs.id,
                timestamp=ts,
                value=s,
            )
        )
    db_session.commit()

    result = compute_performance_metrics(db_session, flight_test.id)
    assert result["available"] is True
    assert result["capability_key"] == "performance_general"
    assert result["mean_climb_rate_fpm"] is not None
    assert result["speed_delta_kt"] is not None
    assert "deterministic_metrics" in result
    assert len(result["deterministic_assumptions"]) > 0


def test_buffet_vibration_calculator_returns_screening_output(db_session, test_user):
    flight_test = _make_flight_test(db_session, test_user["id"], "Buffet Calc Test")
    vib = _make_parameter(db_session, "AIRFRAME VIBRATION Y", "g")
    base_ts = datetime(2026, 4, 19, 15, 0, 0)
    values = [0.02, 0.03, 0.02, 0.07, 0.12, 0.15, 0.09, 0.04, 0.03, 0.02]
    for i, value in enumerate(values):
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=vib.id,
                timestamp=base_ts + timedelta(milliseconds=200 * i),
                value=value,
            )
        )
    db_session.commit()

    result = compute_buffet_vibration_metrics(db_session, flight_test.id)
    assert result["available"] is True
    assert result["capability_key"] == "buffet_vibration"
    assert result["channels_screened"] >= 1
    assert len(result["channel_summaries"]) >= 1
    assert "deterministic_metrics" in result
    assert len(result["deterministic_assumptions"]) > 0
