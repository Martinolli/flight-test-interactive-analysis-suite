"""Tests for dataset-scoped dashboard duration window derivation."""

from datetime import datetime, timedelta

from fastapi import status

from app.models import DataPoint, DatasetVersion, FlightTest, TestParameter, User
from app.routers import flight_tests as flight_tests_router


def _create_flight_test(db_session, user_id: int, name: str = "Duration Test"):
    flight_test = FlightTest(
        test_name=name,
        aircraft_type="F-16",
        created_by_id=user_id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)
    return flight_test


def _create_dataset(db_session, flight_test, user_id: int, version_number: int = 1):
    dataset = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=version_number,
        label=f"v{version_number}",
        status="success",
        row_count=0,
        data_points_count=0,
        created_by_id=user_id,
    )
    db_session.add(dataset)
    db_session.commit()
    db_session.refresh(dataset)
    return dataset


def _create_parameter(db_session, name: str = "DURATION_ALT"):
    parameter = TestParameter(name=name, unit="ft")
    db_session.add(parameter)
    db_session.commit()
    db_session.refresh(parameter)
    return parameter


def _add_points(db_session, flight_test, dataset, parameter, timestamps):
    for index, timestamp in enumerate(timestamps):
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                dataset_version_id=dataset.id,
                parameter_id=parameter.id,
                timestamp=timestamp,
                value=float(index),
            )
        )
    dataset.row_count = len(timestamps)
    dataset.data_points_count = len(timestamps)
    db_session.add(dataset)
    db_session.commit()


def _duration_by_dataset(client, headers, flight_test_id: int):
    response = client.get(
        f"/api/flight-tests/{flight_test_id}/dataset-versions",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return {item["id"]: item["dataset_duration"] for item in response.json()}


def test_dataset_duration_multiple_timestamps_returns_window(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"])
    dataset = _create_dataset(db_session, flight_test, test_user["id"])
    parameter = _create_parameter(db_session)
    start = datetime(2026, 5, 4, 8, 0, 0)
    end = start + timedelta(seconds=452.3)
    _add_points(db_session, flight_test, dataset, parameter, [end, start])

    durations = _duration_by_dataset(client, auth_headers, flight_test.id)
    duration = durations[dataset.id]

    assert duration["dataset_version_id"] == dataset.id
    assert duration["dataset_label"] == "v1"
    assert duration["status"] == "available"
    assert duration["duration_seconds"] == 452.3
    assert duration["duration_label"] == "7 min 32 s"
    assert duration["start_timestamp"].startswith("2026-05-04T08:00:00")
    assert duration["end_timestamp"].startswith("2026-05-04T08:07:32.300000")


def test_dataset_duration_single_timestamp_returns_zero_seconds(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "Single Timestamp")
    dataset = _create_dataset(db_session, flight_test, test_user["id"])
    parameter = _create_parameter(db_session, "DURATION_SINGLE_ALT")
    timestamp = datetime(2026, 5, 4, 9, 15, 0)
    _add_points(db_session, flight_test, dataset, parameter, [timestamp])

    duration = _duration_by_dataset(client, auth_headers, flight_test.id)[dataset.id]

    assert duration["status"] == "available"
    assert duration["duration_seconds"] == 0
    assert duration["duration_label"] == "0 s"
    assert duration["start_timestamp"] == duration["end_timestamp"]


def test_dataset_duration_no_data_returns_structured_no_data(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "No Data Duration")
    dataset = _create_dataset(db_session, flight_test, test_user["id"])

    duration = _duration_by_dataset(client, auth_headers, flight_test.id)[dataset.id]

    assert duration == {
        "dataset_version_id": dataset.id,
        "dataset_label": "v1",
        "start_timestamp": None,
        "end_timestamp": None,
        "duration_seconds": None,
        "duration_label": "N/A",
        "status": "no_data",
    }


def test_dataset_duration_is_scoped_to_each_dataset_version(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "Scoped Duration")
    parameter = _create_parameter(db_session, "DURATION_SCOPED_ALT")
    v1 = _create_dataset(db_session, flight_test, test_user["id"], version_number=1)
    v2 = _create_dataset(db_session, flight_test, test_user["id"], version_number=2)
    start = datetime(2026, 5, 4, 10, 0, 0)
    _add_points(db_session, flight_test, v1, parameter, [start, start + timedelta(seconds=10)])
    _add_points(db_session, flight_test, v2, parameter, [start, start + timedelta(seconds=100)])

    durations = _duration_by_dataset(client, auth_headers, flight_test.id)

    assert durations[v1.id]["duration_seconds"] == 10
    assert durations[v1.id]["duration_label"] == "10 s"
    assert durations[v2.id]["duration_seconds"] == 100
    assert durations[v2.id]["duration_label"] == "1 min 40 s"


def test_other_user_cannot_access_dataset_duration(client, db_session, test_user, auth_headers):
    other_user = User(
        email="duration-other@test.com",
        username="durationother",
        hashed_password="not-used",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_test = _create_flight_test(db_session, other_user.id, "Other Duration")
    _create_dataset(db_session, other_test, other_user.id)

    response = client.get(
        f"/api/flight-tests/{other_test.id}/dataset-versions",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_invalid_timestamp_summary_returns_invalid_status(db_session, test_user):
    flight_test = _create_flight_test(db_session, test_user["id"], "Invalid Duration")
    dataset = _create_dataset(db_session, flight_test, test_user["id"])

    duration = flight_tests_router._build_dataset_duration(
        dataset,
        timestamp_summary={"start": "not-a-date", "end": "also-not-a-date", "count": 2},
    )

    assert duration.status == "invalid_timestamps"
    assert duration.duration_label == "N/A"
    assert duration.duration_seconds is None
