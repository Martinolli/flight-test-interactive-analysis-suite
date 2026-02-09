"""Test CSV upload functionality."""

from pathlib import Path

import pytest
from fastapi import status


def _get_csv_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "sample_data" / "Flight_Test_Data_2025_08_06.csv"


def _create_user(client, user_data: dict) -> None:
    response = client.post("/api/users/", json=user_data)
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
def test_csv_upload_flow(client, sample_user_data):
    """Upload a CSV file and verify data points are created."""
    _create_user(client, sample_user_data)
    token = _login(
        client,
        sample_user_data["username"],
        sample_user_data["password"],
    )
    flight_test_id = _create_flight_test(client, token)

    csv_path = _get_csv_path()
    assert csv_path.exists(), f"Sample CSV not found at {csv_path}"

    with csv_path.open("rb") as csv_file:
        response = client.post(
            f"/api/flight-tests/{flight_test_id}/upload-csv",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (csv_path.name, csv_file, "text/csv")},
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
