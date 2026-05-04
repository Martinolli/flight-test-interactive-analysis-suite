"""Tests for failed ingestion cleanup safety and ownership rules."""

from datetime import datetime

from app.auth import get_password_hash
from app.models import (
    AnalysisJob,
    DataPoint,
    DatasetVersion,
    FlightTest,
    FratAssessment,
    IngestionSession,
    TestParameter,
    User,
)


def _create_flight_test(db_session, user_id: int, name: str = "Cleanup Test"):
    flight_test = FlightTest(
        test_name=name,
        aircraft_type="F-16",
        created_by_id=user_id,
    )
    db_session.add(flight_test)
    db_session.commit()
    db_session.refresh(flight_test)
    return flight_test


def _create_dataset_with_session(
    db_session,
    *,
    flight_test,
    user_id: int,
    session_status: str = "failed",
    dataset_status: str = "failed",
    active: bool = False,
    point_count: int = 2,
):
    session = IngestionSession(
        flight_test_id=flight_test.id,
        filename="failed_upload.csv",
        file_type="csv",
        source_format="csv",
        status=session_status,
        error_message="Error processing CSV file: invalid timestamp",
        uploaded_by_id=user_id,
    )
    db_session.add(session)
    db_session.flush()

    dataset = DatasetVersion(
        flight_test_id=flight_test.id,
        version_number=1,
        label="v1",
        status=dataset_status,
        row_count=point_count,
        data_points_count=point_count,
        source_session_id=session.id,
        created_by_id=user_id,
    )
    db_session.add(dataset)
    db_session.flush()

    session.dataset_version_id = dataset.id
    db_session.add(session)

    parameter = TestParameter(name=f"CLEANUP_PARAM_{flight_test.id}", unit="kt")
    db_session.add(parameter)
    db_session.flush()
    for index in range(point_count):
        db_session.add(
            DataPoint(
                flight_test_id=flight_test.id,
                dataset_version_id=dataset.id,
                parameter_id=parameter.id,
                timestamp=datetime(2026, 5, 4, 0, 0, index),
                value=float(index),
            )
        )

    if active:
        flight_test.active_dataset_version_id = dataset.id
        db_session.add(flight_test)

    db_session.commit()
    db_session.refresh(session)
    db_session.refresh(dataset)
    return session, dataset


def _cleanup(client, headers, flight_test_id: int, session_id: int):
    return client.delete(
        f"/api/flight-tests/{flight_test_id}/ingestion-sessions/{session_id}/cleanup",
        headers=headers,
    )


def test_failed_ingestion_cleanup_succeeds_for_owner_and_removes_partial_data(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"])
    session, dataset = _create_dataset_with_session(
        db_session,
        flight_test=flight_test,
        user_id=test_user["id"],
        point_count=3,
    )
    session_id = session.id
    dataset_id = dataset.id

    response = _cleanup(client, auth_headers, flight_test.id, session_id)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "cleaned"
    assert payload["ingestion_session_id"] == session_id
    assert payload["dataset_version_id"] == dataset_id
    assert payload["deleted_data_point_count"] == 3
    assert payload["removed_records"] == {
        "ingestion_sessions": 1,
        "dataset_versions": 1,
        "data_points": 3,
        "test_parameters": 0,
    }
    assert "successful dataset versions were preserved" in payload["message"]
    assert db_session.get(IngestionSession, session_id) is None
    assert db_session.get(DatasetVersion, dataset_id) is None
    assert (
        db_session.query(DataPoint).filter(DataPoint.dataset_version_id == dataset_id).count() == 0
    )


def test_failed_ingestion_cleanup_without_dataset_removes_session_only(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "No Dataset Cleanup")
    session = IngestionSession(
        flight_test_id=flight_test.id,
        filename="failed_before_dataset.csv",
        file_type="csv",
        source_format="csv",
        status="failed",
        error_message="File must be a CSV file",
        uploaded_by_id=test_user["id"],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    response = _cleanup(client, auth_headers, flight_test.id, session.id)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["dataset_version_id"] is None
    assert payload["deleted_data_point_count"] == 0
    assert payload["removed_records"]["dataset_versions"] == 0
    assert db_session.get(IngestionSession, session.id) is None


def test_cleanup_denied_for_successful_dataset_version(client, db_session, test_user, auth_headers):
    flight_test = _create_flight_test(db_session, test_user["id"], "Success Dataset")
    session, _dataset = _create_dataset_with_session(
        db_session,
        flight_test=flight_test,
        user_id=test_user["id"],
        session_status="failed",
        dataset_status="success",
    )

    response = _cleanup(client, auth_headers, flight_test.id, session.id)

    assert response.status_code == 400
    assert "Successful dataset versions cannot be cleaned up" in response.json()["detail"]


def test_cleanup_denied_for_successful_ingestion_session(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "Success Session")
    session, _dataset = _create_dataset_with_session(
        db_session,
        flight_test=flight_test,
        user_id=test_user["id"],
        session_status="success",
        dataset_status="success",
    )

    response = _cleanup(client, auth_headers, flight_test.id, session.id)

    assert response.status_code == 400
    assert "failed or cancelled ingestion sessions" in response.json()["detail"]


def test_cleanup_denied_for_active_dataset_version(client, db_session, test_user, auth_headers):
    flight_test = _create_flight_test(db_session, test_user["id"], "Active Failed Dataset")
    session, _dataset = _create_dataset_with_session(
        db_session,
        flight_test=flight_test,
        user_id=test_user["id"],
        active=True,
    )

    response = _cleanup(client, auth_headers, flight_test.id, session.id)

    assert response.status_code == 400
    assert "Active dataset versions cannot be cleaned up" in response.json()["detail"]


def test_cleanup_denied_when_dataset_referenced_by_analysis_job(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "Analysis Ref")
    session, dataset = _create_dataset_with_session(
        db_session,
        flight_test=flight_test,
        user_id=test_user["id"],
    )
    db_session.add(
        AnalysisJob(
            flight_test_id=flight_test.id,
            created_by_id=test_user["id"],
            dataset_version_id=dataset.id,
            status="completed",
            model_name="gpt-4o-mini",
            prompt_text="Prompt",
            output_sha256="a" * 64,
            analysis_text="Analysis",
        )
    )
    db_session.commit()

    response = _cleanup(client, auth_headers, flight_test.id, session.id)

    assert response.status_code == 400
    assert "saved analysis job" in response.json()["detail"]


def test_cleanup_denied_when_dataset_referenced_by_frat_assessment(
    client, db_session, test_user, auth_headers
):
    flight_test = _create_flight_test(db_session, test_user["id"], "FRAT Ref")
    session, dataset = _create_dataset_with_session(
        db_session,
        flight_test=flight_test,
        user_id=test_user["id"],
    )
    db_session.add(
        FratAssessment(
            flight_test_id=flight_test.id,
            dataset_version_id=dataset.id,
            created_by_id=test_user["id"],
            status="draft",
            assessment_name="Dataset-linked FRAT",
        )
    )
    db_session.commit()

    response = _cleanup(client, auth_headers, flight_test.id, session.id)

    assert response.status_code == 400
    assert "FRAT assessment" in response.json()["detail"]


def test_cleanup_denied_for_another_users_records(client, db_session, test_user, auth_headers):
    other_user = User(
        email="cleanup-other@test.com",
        username="cleanupother",
        hashed_password=get_password_hash("otherpass123"),
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_test = _create_flight_test(db_session, other_user.id, "Other Owner")
    other_session, _dataset = _create_dataset_with_session(
        db_session,
        flight_test=other_test,
        user_id=other_user.id,
    )

    response = _cleanup(client, auth_headers, other_test.id, other_session.id)

    assert response.status_code == 404
    assert "Ingestion session not found" in response.json()["detail"]
