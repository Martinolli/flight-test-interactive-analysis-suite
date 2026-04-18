"""Regression checks for deterministic takeoff wording hardening."""

from app.routers.documents import _build_deterministic_takeoff_section


def test_deterministic_takeoff_section_uses_estimate_and_corrections_wording():
    section = _build_deterministic_takeoff_section(
        {
            "available": True,
            "distance_ft": 1325.4,
            "distance_m": 403.9,
            "wow_channels_used": 2,
            "wow_ground_threshold": 0.5,
            "start_timestamp": "2026-04-18T08:30:00Z",
            "liftoff_timestamp": "2026-04-18T08:30:14Z",
            "start_wow_mean": 1.0,
            "liftoff_wow_mean": 0.0,
            "start_speed_kt": 8.5,
            "liftoff_speed_kt": 82.1,
            "run_time_s": 14.2,
            "mean_accel_fts2": 8.53,
            "sensor_accel_mean_g": 0.27,
            "sensor_accel_mean_fts2": 8.68,
            "sample_intervals_used": 238,
        }
    )

    assert "Estimated takeoff ground roll to liftoff" in section
    assert "Deterministic data-derived estimate" in section
    assert "Corrections not applied" in section
    assert "not a certification-corrected takeoff distance" in section
