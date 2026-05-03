"""Tests for P3.3 bounded atmosphere / air-data engineering support."""

from datetime import datetime, timedelta

from app.analysis import compute_performance_metrics
from app.analysis.air_data import (
    density_altitude_estimate_ft,
    estimate_mach_from_tas_knots_and_temperature_c,
    estimate_tas_from_cas_and_sigma_knots,
    isa_atmosphere_from_pressure_altitude_ft,
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


def test_air_data_helpers_return_bounded_engineering_values():
    isa = isa_atmosphere_from_pressure_altitude_ft(5000.0)
    assert isa is not None
    assert isa["sigma"] < 1.0
    assert isa["temperature_c"] < 15.0

    density_alt = density_altitude_estimate_ft(5000.0, 35.0)
    assert density_alt is not None
    assert density_alt > 5000.0

    tas_est = estimate_tas_from_cas_and_sigma_knots(150.0, isa["sigma"])
    assert tas_est is not None
    assert tas_est > 150.0

    mach_est = estimate_mach_from_tas_knots_and_temperature_c(tas_est, 5.0)
    assert mach_est is not None
    assert 0.1 < mach_est < 1.0


def test_performance_calculator_includes_air_data_support_with_channels(db_session, test_user):
    flight_test = _make_flight_test(
        db_session, test_user["id"], "Performance Air-Data Support Test"
    )
    pa = _make_parameter(db_session, "PRESSURE ALTITUDE", "ft")
    oat = _make_parameter(db_session, "OAT", "C")
    cas = _make_parameter(db_session, "CAS", "kt")
    tas = _make_parameter(db_session, "TAS", "kt")
    mach = _make_parameter(db_session, "MACH", "")
    gs = _make_parameter(db_session, "GROUND SPEED", "kt")

    base_ts = datetime(2026, 4, 24, 8, 0, 0)
    pa_values = [4500.0, 4700.0, 4900.0, 5100.0, 5300.0, 5500.0]
    oat_values = [22.0, 21.5, 21.0, 20.0, 19.0, 18.5]
    cas_values = [142.0, 145.0, 149.0, 152.0, 156.0, 160.0]
    tas_values = [151.0, 154.0, 158.0, 161.0, 165.0, 168.0]
    mach_values = [0.26, 0.27, 0.28, 0.29, 0.30, 0.31]
    gs_values = [140.0, 144.0, 148.0, 151.0, 155.0, 159.0]

    for i in range(len(pa_values)):
        ts = base_ts + timedelta(seconds=5 * i)
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id, parameter_id=pa.id, timestamp=ts, value=pa_values[i]
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=oat.id,
                timestamp=ts,
                value=oat_values[i],
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=cas.id,
                timestamp=ts,
                value=cas_values[i],
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=tas.id,
                timestamp=ts,
                value=tas_values[i],
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=mach.id,
                timestamp=ts,
                value=mach_values[i],
            )
        )
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id, parameter_id=gs.id, timestamp=ts, value=gs_values[i]
            )
        )
    db_session.commit()

    result = compute_performance_metrics(db_session, flight_test.id)
    assert result["available"] is True
    assert result["capability_key"] == "performance_general"

    air_data = result.get("air_data_support")
    assert isinstance(air_data, dict)
    assert air_data.get("available") is True
    assert "PRESSURE ALTITUDE" in (air_data.get("channels_used") or [])
    assert air_data.get("pressure_altitude_ft") is not None
    assert air_data.get("density_altitude_ft") is not None
    assert air_data.get("tas_est_from_cas_sigma_kt") is not None
    assert air_data.get("mach_est_from_tas_temp") is not None
    assert len(result.get("deterministic_assumptions") or []) > 0


def test_performance_air_data_support_degrades_gracefully_when_channels_missing(
    db_session, test_user
):
    flight_test = _make_flight_test(
        db_session, test_user["id"], "Performance Air-Data Degradation Test"
    )
    gs = _make_parameter(db_session, "GROUND SPEED", "kt")

    base_ts = datetime(2026, 4, 24, 9, 0, 0)
    for i, value in enumerate([120.0, 126.0, 131.0, 136.0]):
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=gs.id,
                timestamp=base_ts + timedelta(seconds=5 * i),
                value=value,
            )
        )
    db_session.commit()

    result = compute_performance_metrics(db_session, flight_test.id)
    assert result["available"] is True
    air_data = result.get("air_data_support")
    assert isinstance(air_data, dict)
    assert air_data.get("available") is False
    skipped = air_data.get("skipped_calculations") or []
    assert any("pressure-altitude channel unavailable" in item for item in skipped)
