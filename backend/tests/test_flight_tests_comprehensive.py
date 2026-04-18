"""
Comprehensive test suite for Flight Tests API
Tests all CRUD operations, CSV upload, data retrieval, and edge cases
"""

import io
from datetime import datetime

from fastapi import status

from app.auth import get_password_hash
from app.models import (
    AnalysisJob,
    DataPoint,
    DatasetVersion,
    FlightTest,
    IngestionSession,
    TestParameter,
    User,
)


class TestFlightTestCRUD:
    """Test Flight Test CRUD operations"""

    def test_create_flight_test(self, client, test_user, auth_headers):
        """Test creating a new flight test"""
        response = client.post(
            "/api/flight-tests/",
            json={
                "test_name": "Test Flight Alpha",
                "aircraft_type": "F-16",
                "test_date": "2025-08-15",
                "duration_seconds": 3600.0,
                "description": "High-altitude performance test",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["test_name"] == "Test Flight Alpha"
        assert data["aircraft_type"] == "F-16"
        assert data["created_by_id"] == test_user["id"]
        assert "id" in data
        assert "created_at" in data

    def test_create_duplicate_flight_test(self, client, auth_headers):
        """Test creating a flight test with duplicate name"""
        # Create first flight test
        client.post(
            "/api/flight-tests/",
            json={
                "test_name": "Duplicate Test",
                "aircraft_type": "F-16",
                "test_date": "2025-08-15",
            },
            headers=auth_headers,
        )

        # Try to create duplicate
        response = client.post(
            "/api/flight-tests/",
            json={
                "test_name": "Duplicate Test",
                "aircraft_type": "F-18",
                "test_date": "2025-08-16",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"]

    def test_list_flight_tests(self, client, test_user, auth_headers):
        """Test listing all flight tests for current user"""
        # Create multiple flight tests
        for i in range(3):
            client.post(
                "/api/flight-tests/",
                json={
                    "test_name": f"Test Flight {i}",
                    "aircraft_type": "F-16",
                    "test_date": "2025-08-15",
                },
                headers=auth_headers,
            )

        response = client.get("/api/flight-tests/", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 3
        assert all(ft["created_by_id"] == test_user["id"] for ft in data)

    def test_list_flight_tests_pagination(self, client, auth_headers):
        """Test pagination in flight test listing"""
        # Create 5 flight tests
        for i in range(5):
            client.post(
                "/api/flight-tests/",
                json={
                    "test_name": f"Pagination Test {i}",
                    "aircraft_type": "F-16",
                    "test_date": "2025-08-15",
                },
                headers=auth_headers,
            )

        # Test with limit
        response = client.get("/api/flight-tests/?limit=3",
                              headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 3

        # Test with skip
        response = client.get("/api/flight-tests/?skip=2&limit=2",
                              headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 2

    def test_get_flight_test_by_id(self, client, auth_headers):
        """Test retrieving a specific flight test by ID"""
        # Create a flight test
        create_response = client.post(
            "/api/flight-tests/",
            json={
                "test_name": "Specific Test",
                "aircraft_type": "F-16",
                "test_date": "2025-08-15",
                "description": "Test description",
            },
            headers=auth_headers,
        )
        test_id = create_response.json()["id"]

        # Retrieve it
        response = client.get(f"/api/flight-tests/{test_id}",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_id
        assert data["test_name"] == "Specific Test"
        assert data["description"] == "Test description"

    def test_get_nonexistent_flight_test(self, client, auth_headers):
        """Test retrieving a flight test that doesn't exist"""
        response = client.get("/api/flight-tests/99999", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_other_user_flight_test(self, client,
                                        auth_headers, db_session):
        """Test that users cannot access other users' flight tests"""

        # Create another user
        other_user = User(
            email="other@test.com",
            username="otheruser",
            hashed_password=get_password_hash("password123"),
            full_name="Other User",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        # Create flight test for other user
        other_test = FlightTest(
            test_name="Other User Test", aircraft_type="F-18",
            created_by_id=other_user.id
        )
        db_session.add(other_test)
        db_session.commit()
        db_session.refresh(other_test)

        # Try to access with current user's token
        response = client.get(f"/api/flight-tests/{other_test.id}",
                              headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_flight_test(self, client, auth_headers):
        """Test updating a flight test"""
        # Create a flight test
        create_response = client.post(
            "/api/flight-tests/",
            json={"test_name": "Update Test", "aircraft_type": "F-16",
                  "test_date": "2025-08-15"},
            headers=auth_headers,
        )
        test_id = create_response.json()["id"]

        # Update it
        response = client.put(
            f"/api/flight-tests/{test_id}",
            json={
                "test_name": "Updated Test",
                "aircraft_type": "F-18",
                "test_date": "2025-08-16",
                "description": "Updated description",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["test_name"] == "Updated Test"
        assert data["aircraft_type"] == "F-18"
        assert data["description"] == "Updated description"

    def test_delete_flight_test(self, client, auth_headers):
        """Test deleting a flight test"""
        # Create a flight test
        create_response = client.post(
            "/api/flight-tests/",
            json={"test_name": "Delete Test", "aircraft_type": "F-16",
                  "test_date": "2025-08-15"},
            headers=auth_headers,
        )
        test_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/flight-tests/{test_id}",
                                 headers=auth_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's gone
        get_response = client.get(f"/api/flight-tests/{test_id}",
                                  headers=auth_headers)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_flight_test_cascades_data(self, client, test_user,
                                              auth_headers, db_session):
        """Test that deleting a flight test
        also deletes associated data points"""

        # Create flight test
        flight_test = FlightTest(
            test_name="Cascade Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Create parameter
        parameter = TestParameter(name="TEST_PARAM",
                                  description="Test Parameter", unit="deg")
        db_session.add(parameter)
        db_session.commit()
        db_session.refresh(parameter)

        # Create data points
        for i in range(5):
            data_point = DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=parameter.id,
                timestamp=datetime(2025, 8, 15, 10, i, 0),
                value=float(i),
            )
            db_session.add(data_point)
        db_session.commit()

        # Verify data points exist
        data_points = (
            db_session.query(DataPoint).filter(DataPoint.flight_test_id == flight_test.id).all()
        )
        assert len(data_points) == 5

        # Delete flight test
        response = client.delete(f"/api/flight-tests/{flight_test.id}",
                                 headers=auth_headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify data points are deleted
        data_points = (
            db_session.query(DataPoint).filter(DataPoint.flight_test_id == flight_test.id).all()
        )
        assert len(data_points) == 0

    def test_delete_flight_test_with_dataset_versions_sessions_and_analysis_jobs(
        self, client, test_user, auth_headers, db_session
    ):
        """Deleting a versioned/provenance-rich flight test should remove all linked rows."""
        flight_test = FlightTest(
            test_name="Delete Provenance-Rich Test",
            aircraft_type="F-16",
            created_by_id=test_user["id"],
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        parameter = TestParameter(
            name="DELETE_PROVENANCE_PARAM",
            description="Delete provenance test parameter",
            unit="kt",
        )
        db_session.add(parameter)
        db_session.commit()
        db_session.refresh(parameter)

        session_v1 = IngestionSession(
            flight_test_id=flight_test.id,
            filename="v1.csv",
            file_type="csv",
            source_format="csv",
            row_count=2,
            status="success",
            uploaded_by_id=test_user["id"],
        )
        session_v2 = IngestionSession(
            flight_test_id=flight_test.id,
            filename="v2.csv",
            file_type="csv",
            source_format="csv",
            row_count=2,
            status="success",
            uploaded_by_id=test_user["id"],
        )
        db_session.add_all([session_v1, session_v2])
        db_session.flush()

        dataset_v1 = DatasetVersion(
            flight_test_id=flight_test.id,
            version_number=1,
            label="v1",
            status="success",
            row_count=2,
            data_points_count=2,
            source_session_id=session_v1.id,
            created_by_id=test_user["id"],
        )
        dataset_v2 = DatasetVersion(
            flight_test_id=flight_test.id,
            version_number=2,
            label="v2",
            status="success",
            row_count=2,
            data_points_count=2,
            source_session_id=session_v2.id,
            created_by_id=test_user["id"],
        )
        db_session.add_all([dataset_v1, dataset_v2])
        db_session.flush()

        session_v1.dataset_version_id = dataset_v1.id
        session_v2.dataset_version_id = dataset_v2.id
        flight_test.active_dataset_version_id = dataset_v2.id

        db_session.add_all(
            [
                DataPoint(
                    flight_test_id=flight_test.id,
                    dataset_version_id=dataset_v1.id,
                    parameter_id=parameter.id,
                    timestamp=datetime(2025, 8, 15, 10, 0, 0),
                    value=101.0,
                ),
                DataPoint(
                    flight_test_id=flight_test.id,
                    dataset_version_id=dataset_v2.id,
                    parameter_id=parameter.id,
                    timestamp=datetime(2025, 8, 15, 10, 0, 1),
                    value=202.0,
                ),
            ]
        )

        db_session.add_all(
            [
                AnalysisJob(
                    flight_test_id=flight_test.id,
                    created_by_id=test_user["id"],
                    dataset_version_id=dataset_v1.id,
                    status="completed",
                    model_name="gpt-4o-mini",
                    model_version="test",
                    parameters_analysed=1,
                    parameter_stats_snapshot_json="[]",
                    prompt_text="prompt-v1",
                    retrieved_source_ids_json="[]",
                    retrieved_sources_snapshot_json="[]",
                    output_sha256="a" * 64,
                    analysis_text="analysis-v1",
                ),
                AnalysisJob(
                    flight_test_id=flight_test.id,
                    created_by_id=test_user["id"],
                    dataset_version_id=dataset_v2.id,
                    status="completed",
                    model_name="gpt-4o-mini",
                    model_version="test",
                    parameters_analysed=1,
                    parameter_stats_snapshot_json="[]",
                    prompt_text="prompt-v2",
                    retrieved_source_ids_json="[]",
                    retrieved_sources_snapshot_json="[]",
                    output_sha256="b" * 64,
                    analysis_text="analysis-v2",
                ),
            ]
        )
        db_session.commit()

        db_session.refresh(flight_test)
        assert flight_test.active_dataset_version_id == dataset_v2.id
        assert dataset_v1.source_session_id == session_v1.id
        assert dataset_v2.source_session_id == session_v2.id

        assert (
            db_session.query(DataPoint)
            .filter(DataPoint.flight_test_id == flight_test.id)
            .count()
            == 2
        )
        assert (
            db_session.query(DatasetVersion)
            .filter(DatasetVersion.flight_test_id == flight_test.id)
            .count()
            == 2
        )
        assert (
            db_session.query(IngestionSession)
            .filter(IngestionSession.flight_test_id == flight_test.id)
            .count()
            == 2
        )
        assert (
            db_session.query(AnalysisJob)
            .filter(AnalysisJob.flight_test_id == flight_test.id)
            .count()
            == 2
        )

        response = client.delete(
            f"/api/flight-tests/{flight_test.id}",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert (
            db_session.query(FlightTest)
            .filter(FlightTest.id == flight_test.id)
            .first()
            is None
        )
        assert (
            db_session.query(DataPoint)
            .filter(DataPoint.flight_test_id == flight_test.id)
            .count()
            == 0
        )
        assert (
            db_session.query(DatasetVersion)
            .filter(DatasetVersion.flight_test_id == flight_test.id)
            .count()
            == 0
        )
        assert (
            db_session.query(IngestionSession)
            .filter(IngestionSession.flight_test_id == flight_test.id)
            .count()
            == 0
        )
        assert (
            db_session.query(AnalysisJob)
            .filter(AnalysisJob.flight_test_id == flight_test.id)
            .count()
            == 0
        )


class TestCSVUpload:
    """Test CSV upload functionality"""

    def test_csv_upload_simple(self, client, test_user,
                               auth_headers, db_session):
        """Test uploading a simple CSV file"""
        # Create flight test
        flight_test = FlightTest(
            test_name="CSV Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Create CSV content
        csv_content = """timestamp,ALT,IAS,PITCH
s,ft,kt,deg
0.0,5000.0,250.0,5.2
0.1,5050.0,251.0,5.3
0.2,5100.0,252.0,5.4"""

        # Upload CSV
        files = {"file": ("test.csv",
                          io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["message"] == "CSV data uploaded successfully"
        assert data["rows_processed"] == 3
        assert data["data_points_created"] == 9  # 3 rows × 3 parameters

    def test_csv_upload_two_header_format(self, client,
                                          test_user, auth_headers, db_session):
        """Test uploading CSV with two-header format (names + units)"""
        # Create flight test
        flight_test = FlightTest(
            test_name="Two Header CSV Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Create CSV with two headers
        csv_content = """Description,ROLL_ANGLE,PITCH_ANGLE,YAW_RATE
EU,deg,deg,deg/s
0:00:00:00.000,0.5,0.8,0.03
0:00:00:01.000,0.6,0.9,0.04"""

        # Upload CSV
        files = {"file": ("test.csv",
                          io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["message"] == "CSV data uploaded successfully"
        assert data["rows_processed"] == 2

        # Verify parameters were created with units

        roll_param = (
            db_session.query(TestParameter)
            .filter(TestParameter.name == "ROLL_ANGLE")
            .first()
        )
        assert roll_param is not None
        assert roll_param.unit == "deg"

    def test_csv_upload_invalid_file_type(self, client,
                                          test_user, auth_headers, db_session):
        """Test uploading a non-CSV file"""

        # Create flight test
        flight_test = FlightTest(
            test_name="Invalid File Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Try to upload a text file
        files = {"file": ("test.txt", io.BytesIO(b"not a csv"), "text/plain")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "CSV" in response.json()["detail"]

    def test_csv_upload_empty_file(self, client,
                                   test_user, auth_headers, db_session):
        """Test uploading an empty CSV file"""

        # Create flight test
        flight_test = FlightTest(
            test_name="Empty CSV Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Upload empty CSV
        csv_content = ""
        files = {"file": ("test.csv",
                          io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_csv_upload_missing_timestamp(self, client,
                                          test_user, auth_headers, db_session):
        """Test uploading CSV without timestamp column"""

        # Create flight test
        flight_test = FlightTest(
            test_name="No Timestamp CSV Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # CSV without timestamp
        csv_content = """ALT,IAS,PITCH
5000.0,250.0,5.2
5050.0,251.0,5.3"""

        files = {"file": ("test.csv",
                          io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "timestamp" in response.json()["detail"].lower()

    def test_csv_upload_invalid_timestamp_format(self, client,
                                                 test_user, auth_headers, db_session):
        """Invalid timestamp values should fail with row-level detail."""
        flight_test = FlightTest(
            test_name="Invalid Timestamp CSV Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        csv_content = """timestamp,ALT,IAS
s,ft,kt
abc,5000.0,250.0
0.1,5050.0,251.0"""

        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"].lower()
        assert "timestamp validation failed" in detail
        assert "row 3" in detail

    def test_csv_upload_missing_timestamp_value(self, client,
                                                test_user, auth_headers, db_session):
        """Blank timestamp cells should fail with row-level detail."""
        flight_test = FlightTest(
            test_name="Blank Timestamp CSV Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        csv_content = """timestamp,ALT,IAS
s,ft,kt
,5000.0,250.0
0.1,5050.0,251.0"""

        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"].lower()
        assert "timestamp validation failed" in detail
        assert "row 3" in detail

    def test_csv_upload_nonexistent_flight_test(self, client, auth_headers):
        """Test uploading CSV to non-existent flight test"""
        csv_content = """timestamp,ALT
0.0,5000.0"""

        files = {"file": ("test.csv",
                          io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            "/api/flight-tests/99999/upload-csv",
            files=files, headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_csv_upload_creates_success_ingestion_session(
        self, client, test_user, auth_headers, db_session
    ):
        """Successful upload must persist a success ingestion session."""
        flight_test = FlightTest(
            test_name="Session Success CSV Test",
            aircraft_type="F-16",
            created_by_id=test_user["id"],
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        csv_content = """timestamp,ALT,IAS
s,ft,kt
0.0,5000.0,250.0
0.1,5050.0,251.0"""
        files = {"file": ("session_success.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        payload = response.json()
        assert "session_id" in payload

        session = (
            db_session.query(IngestionSession)
            .filter(IngestionSession.id == payload["session_id"])
            .first()
        )
        assert session is not None
        assert session.status == "success"
        assert session.flight_test_id == flight_test.id
        assert session.filename == "session_success.csv"
        assert session.dataset_version_id is not None
        assert session.row_count == 2
        assert session.error_message is None

    def test_csv_upload_creates_dataset_version_and_sets_active(
        self, client, test_user, auth_headers, db_session
    ):
        flight_test = FlightTest(
            test_name="Dataset Version CSV Test",
            aircraft_type="F-16",
            created_by_id=test_user["id"],
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        csv_content = """timestamp,ALT
s,ft
0.0,5000.0
0.1,5050.0"""
        files = {"file": ("dataset_v1.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        payload = response.json()
        assert payload["dataset_version_id"] > 0
        assert payload["active_dataset_version_id"] == payload["dataset_version_id"]

        db_session.refresh(flight_test)
        assert flight_test.active_dataset_version_id == payload["dataset_version_id"]

        version = (
            db_session.query(DatasetVersion)
            .filter(DatasetVersion.id == payload["dataset_version_id"])
            .first()
        )
        assert version is not None
        assert version.version_number == 1
        assert version.status == "success"

        versions_response = client.get(
            f"/api/flight-tests/{flight_test.id}/dataset-versions",
            headers=auth_headers,
        )
        assert versions_response.status_code == status.HTTP_200_OK
        versions = versions_response.json()
        assert len(versions) == 1
        assert versions[0]["is_active"] is True
        assert versions[0]["version_number"] == 1

    def test_dataset_versions_preserve_history_and_activation_switches_default(
        self, client, test_user, auth_headers, db_session
    ):
        flight_test = FlightTest(
            test_name="Dataset History Test",
            aircraft_type="F-16",
            created_by_id=test_user["id"],
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        first_csv = """timestamp,ALT
s,ft
0.0,100.0"""
        second_csv = """timestamp,ALT
s,ft
0.0,200.0"""

        r1 = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files={"file": ("v1.csv", io.BytesIO(first_csv.encode()), "text/csv")},
            headers=auth_headers,
        )
        assert r1.status_code == status.HTTP_201_CREATED
        v1_id = r1.json()["dataset_version_id"]

        r2 = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files={"file": ("v2.csv", io.BytesIO(second_csv.encode()), "text/csv")},
            headers=auth_headers,
        )
        assert r2.status_code == status.HTTP_201_CREATED
        v2_id = r2.json()["dataset_version_id"]
        assert v2_id != v1_id

        all_points = (
            db_session.query(DataPoint)
            .filter(DataPoint.flight_test_id == flight_test.id)
            .all()
        )
        assert len(all_points) == 2  # no overwrite; both versions are retained
        assert {p.dataset_version_id for p in all_points} == {v1_id, v2_id}

        # Default read follows active dataset (latest upload = v2)
        default_series = client.get(
            f"/api/flight-tests/{flight_test.id}/parameters/data?parameters=ALT",
            headers=auth_headers,
        )
        assert default_series.status_code == status.HTTP_200_OK
        default_payload = default_series.json()
        assert default_payload[0]["data"][0]["value"] == 200.0

        # Explicit read of v1 retrieves historical data.
        v1_series = client.get(
            f"/api/flight-tests/{flight_test.id}/parameters/data?parameters=ALT&dataset_version_id={v1_id}",
            headers=auth_headers,
        )
        assert v1_series.status_code == status.HTTP_200_OK
        v1_payload = v1_series.json()
        assert v1_payload[0]["data"][0]["value"] == 100.0

        # Switch active dataset back to v1 and verify default read follows it.
        activate = client.post(
            f"/api/flight-tests/{flight_test.id}/dataset-versions/{v1_id}/activate",
            headers=auth_headers,
        )
        assert activate.status_code == status.HTTP_200_OK
        switched_default = client.get(
            f"/api/flight-tests/{flight_test.id}/parameters/data?parameters=ALT",
            headers=auth_headers,
        )
        assert switched_default.status_code == status.HTTP_200_OK
        switched_payload = switched_default.json()
        assert switched_payload[0]["data"][0]["value"] == 100.0

    def test_csv_upload_failure_persists_failed_ingestion_session(
        self, client, test_user, auth_headers, db_session
    ):
        """Validation failure must persist a failed ingestion session with error detail."""
        flight_test = FlightTest(
            test_name="Session Failure CSV Test",
            aircraft_type="F-16",
            created_by_id=test_user["id"],
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        csv_content = """timestamp,ALT
s,ft
bad-time,5000.0
0.1,5050.0"""
        files = {"file": ("session_failure.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            f"/api/flight-tests/{flight_test.id}/upload-csv",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        session = (
            db_session.query(IngestionSession)
            .filter(
                IngestionSession.flight_test_id == flight_test.id,
                IngestionSession.filename == "session_failure.csv",
            )
            .order_by(IngestionSession.created_at.desc())
            .first()
        )
        assert session is not None
        assert session.status == "failed"
        assert session.error_message is not None
        assert "timestamp validation failed" in session.error_message.lower()

    def test_ingestion_session_endpoints_are_tenant_scoped(
        self, client, test_user, auth_headers, db_session
    ):
        """Session list/detail must only expose records belonging to current user."""
        own_test = FlightTest(
            test_name="Own Sessions Test",
            aircraft_type="F-16",
            created_by_id=test_user["id"],
        )
        db_session.add(own_test)
        db_session.commit()
        db_session.refresh(own_test)

        own_session = IngestionSession(
            flight_test_id=own_test.id,
            filename="own.csv",
            file_type="csv",
            source_format="csv",
            row_count=10,
            status="success",
            uploaded_by_id=test_user["id"],
        )
        db_session.add(own_session)

        other_user = User(
            email="upload-other@test.com",
            username="uploadotheruser",
            hashed_password=get_password_hash("password123"),
            full_name="Upload Other User",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        other_test = FlightTest(
            test_name="Other Sessions Test",
            aircraft_type="F-18",
            created_by_id=other_user.id,
        )
        db_session.add(other_test)
        db_session.commit()
        db_session.refresh(other_test)

        other_session = IngestionSession(
            flight_test_id=other_test.id,
            filename="other.csv",
            file_type="csv",
            source_format="csv",
            row_count=5,
            status="success",
            uploaded_by_id=other_user.id,
        )
        db_session.add(other_session)
        db_session.commit()
        db_session.refresh(own_session)

        list_response = client.get(
            f"/api/flight-tests/{own_test.id}/ingestion-sessions",
            headers=auth_headers,
        )
        assert list_response.status_code == status.HTTP_200_OK
        items = list_response.json()
        assert len(items) == 1
        assert items[0]["filename"] == "own.csv"

        detail_response = client.get(
            f"/api/flight-tests/{own_test.id}/ingestion-sessions/{own_session.id}",
            headers=auth_headers,
        )
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.json()["filename"] == "own.csv"

        forbidden_list = client.get(
            f"/api/flight-tests/{other_test.id}/ingestion-sessions",
            headers=auth_headers,
        )
        assert forbidden_list.status_code == status.HTTP_404_NOT_FOUND


class TestDataRetrieval:
    """Test data point retrieval"""

    def test_get_data_points(self, client, test_user,
                             auth_headers, db_session):
        """Test retrieving data points for a flight test"""

        # Create flight test
        flight_test = FlightTest(
            test_name="Data Retrieval Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Create parameter
        parameter = TestParameter(name="ALT",
                                  description="Altitude", unit="ft")
        db_session.add(parameter)
        db_session.commit()
        db_session.refresh(parameter)

        # Create data points
        for i in range(10):
            data_point = DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=parameter.id,
                timestamp=datetime(2025, 8, 15, 10, 0, i),
                value=5000.0 + i * 50.0,
            )
            db_session.add(data_point)
        db_session.commit()

        # Retrieve data points
        response = client.get(f"/api/flight-tests/{flight_test.id}/data",
                              headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 10
        assert all("timestamp" in dp for dp in data)
        assert all("value" in dp for dp in data)

    def test_get_data_points_with_pagination(self, client,
                                             test_user, auth_headers,
                                             db_session):
        """Test data point retrieval with pagination"""
        from app.models import DataPoint, FlightTest, TestParameter

        # Create flight test
        flight_test = FlightTest(
            test_name="Pagination Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Create parameter
        parameter = TestParameter(name="ALT",
                                  description="Altitude", unit="ft")
        db_session.add(parameter)
        db_session.commit()
        db_session.refresh(parameter)

        # Create 20 data points
        for i in range(20):
            data_point = DataPoint(
                flight_test_id=flight_test.id,
                parameter_id=parameter.id,
                timestamp=datetime(2025, 8, 15, 10, 0, i),
                value=5000.0 + i * 50.0,
            )
            db_session.add(data_point)
        db_session.commit()

        # Test with limit
        response = client.get(
            f"/api/flight-tests/{flight_test.id}/data?limit=10",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 10

        # Test with skip and limit
        response = client.get(
            f"/api/flight-tests/{flight_test.id}/data?skip=10&limit=5",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5

    def test_get_data_points_parameter_filter(self, client,
                                              test_user, auth_headers,
                                              db_session):
        """Test filtering data points by parameter"""
        from app.models import DataPoint, FlightTest, TestParameter

        # Create flight test
        flight_test = FlightTest(
            test_name="Filter Test", aircraft_type="F-16",
            created_by_id=test_user["id"]
        )
        db_session.add(flight_test)
        db_session.commit()
        db_session.refresh(flight_test)

        # Create two parameters
        alt_param = TestParameter(name="ALT",
                                  description="Altitude", unit="ft")
        ias_param = TestParameter(name="IAS",
                                  description="Airspeed", unit="kt")
        db_session.add(alt_param)
        db_session.add(ias_param)
        db_session.commit()
        db_session.refresh(alt_param)
        db_session.refresh(ias_param)

        # Create data points for both parameters
        for i in range(5):
            db_session.add(
                DataPoint(
                    flight_test_id=flight_test.id,
                    parameter_id=alt_param.id,
                    timestamp=datetime(2025, 8, 15, 10, 0, i),
                    value=5000.0 + i * 50.0,
                )
            )
            db_session.add(
                DataPoint(
                    flight_test_id=flight_test.id,
                    parameter_id=ias_param.id,
                    timestamp=datetime(2025, 8, 15, 10, 0, i),
                    value=250.0 + i * 5.0,
                )
            )
        db_session.commit()

        # Filter by ALT parameter
        response = client.get(
            f"/api/flight-tests/{flight_test.id}/data" f"?parameter_id={alt_param.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
        assert all(dp["parameter_id"] == alt_param.id for dp in data)


class TestAuthentication:
    """Test authentication requirements"""

    def test_create_flight_test_without_auth(self, client):
        """Test that creating flight test requires authentication"""
        response = client.post(
            "/api/flight-tests/",
            json={"test_name": "Unauthorized Test", "aircraft_type": "F-16"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_flight_tests_without_auth(self, client):
        """Test that listing flight tests requires authentication"""
        response = client.get("/api/flight-tests/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_upload_csv_without_auth(self, client):
        """Test that CSV upload requires authentication"""
        csv_content = """timestamp,ALT
0.0,5000.0"""
        files = {"file": ("test.csv",
                          io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post("/api/flight-tests/1/upload-csv", files=files)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token(self, client):
        """Test that invalid token is rejected"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/flight-tests/", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
