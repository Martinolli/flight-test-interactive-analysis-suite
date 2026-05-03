"""Test CSV upload functionality."""

from io import BytesIO

import pytest
from fastapi import status


def _build_sample_csv_file() -> BytesIO:
    content = (
        "timestamp,ALT,IAS,PITCH\n"
        "2025-08-06T08:50:00,1000,120,2.5\n"
        "2025-08-06T08:50:01,1010,121,2.6\n"
        "2025-08-06T08:50:02,1025,123,2.7\n"
    )
    return BytesIO(content.encode("utf-8"))


def _create_user(client, user_data: dict, admin_headers: dict) -> None:
    response = client.post("/api/users/", json=user_data, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()["access_token"]


def _create_flight_test(client, token: str) -> int:
    response = client.post(
        "/api/flight-tests/",
        json={
            "test_name": "CSV Upload Test",
            "aircraft_type": "TestCraft",
            "description": "Upload CSV and validate data points",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


@pytest.mark.api
@pytest.mark.database
def test_csv_upload_flow(client, sample_user_data, admin_headers):
    """Upload a CSV file and verify data points are created."""
    _create_user(client, sample_user_data, admin_headers)
    token = _login(
        client,
        sample_user_data["username"],
        sample_user_data["password"],
    )
    flight_test_id = _create_flight_test(client, token)

    with _build_sample_csv_file() as csv_file:
        response = client.post(
            f"/api/flight-tests/{flight_test_id}/upload-csv",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("flight_test_upload_fixture.csv", csv_file, "text/csv")},
        )

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert result["message"] == "CSV data uploaded successfully"
    assert "rows_processed" in result
    assert "data_points_created" in result
    assert result["rows_processed"] >= 1

    response = client.get(
        f"/api/flight-tests/{flight_test_id}/data?limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == status.HTTP_200_OK
    data_points = response.json()
    assert isinstance(data_points, list)
    assert len(data_points) <= 5
    if data_points:
        assert "timestamp" in data_points[0]
        assert "value" in data_points[0]
