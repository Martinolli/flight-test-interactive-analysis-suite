"""
FTIAS Backend - User Endpoint Tests
"""

import pytest
from fastapi import status


@pytest.mark.api
@pytest.mark.database
def test_create_user(client, sample_user_data, admin_headers):
    """Test creating a new user"""
    response = client.post("/api/users/", json=sample_user_data, headers=admin_headers)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == sample_user_data["email"]
    assert data["username"] == sample_user_data["username"]
    assert data["full_name"] == sample_user_data["full_name"]
    assert "id" in data
    assert "password" not in data  # Password should not be returned
    assert "hashed_password" not in data


@pytest.mark.api
@pytest.mark.database
def test_create_duplicate_user(client, sample_user_data, admin_headers):
    """Test creating a user with duplicate email fails"""
    # Create first user
    client.post("/api/users/", json=sample_user_data, headers=admin_headers)

    # Try to create duplicate
    response = client.post("/api/users/", json=sample_user_data, headers=admin_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.api
@pytest.mark.database
def test_get_users(client, sample_user_data, admin_headers):
    """Test getting list of users"""
    # Create a user first
    client.post("/api/users/", json=sample_user_data, headers=admin_headers)

    # Get users
    response = client.get("/api/users/", headers=admin_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    emails = {item["email"] for item in data}
    assert sample_user_data["email"] in emails


@pytest.mark.api
@pytest.mark.database
def test_get_user_by_id(client, sample_user_data, admin_headers):
    """Test getting a specific user by ID"""
    # Create a user
    create_response = client.post("/api/users/", json=sample_user_data, headers=admin_headers)
    user_id = create_response.json()["id"]

    # Get user by ID
    response = client.get(f"/api/users/{user_id}", headers=admin_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == sample_user_data["email"]


@pytest.mark.api
@pytest.mark.database
def test_get_nonexistent_user(client, admin_headers):
    """Test getting a user that doesn't exist"""
    response = client.get("/api/users/99999", headers=admin_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.api
@pytest.mark.database
def test_update_user(client, sample_user_data, admin_headers):
    """Test updating a user"""
    # Create a user
    create_response = client.post("/api/users/", json=sample_user_data, headers=admin_headers)
    user_id = create_response.json()["id"]

    # Update user
    update_data = {
        "full_name": "Updated Name",
        "email": sample_user_data["email"]
    }
    response = client.put(f"/api/users/{user_id}", json=update_data, headers=admin_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["id"] == user_id


@pytest.mark.api
@pytest.mark.database
def test_delete_user(client, sample_user_data, admin_headers):
    """Test deleting a user"""
    # Create a user
    create_response = client.post("/api/users/", json=sample_user_data, headers=admin_headers)
    user_id = create_response.json()["id"]

    # Delete user
    response = client.delete(f"/api/users/{user_id}", headers=admin_headers)

    assert response.status_code == status.HTTP_200_OK
    assert "deleted successfully" in response.json()["message"].lower()

    # Verify user is deleted
    get_response = client.get(f"/api/users/{user_id}", headers=admin_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.api
@pytest.mark.database
def test_delete_nonexistent_user(client, admin_headers):
    """Test deleting a user that doesn't exist"""
    response = client.delete("/api/users/99999", headers=admin_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.unit
def test_user_data_validation(client, admin_headers):
    """Test user data validation"""
    # Test missing required fields
    invalid_data = {
        "email": "test@example.com"
        # Missing username, full_name, password
    }
    response = client.post("/api/users/", json=invalid_data, headers=admin_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.unit
def test_invalid_email_format(client, admin_headers):
    """Test invalid email format"""
    invalid_data = {
        "email": "not-an-email",
        "username": "testuser",
        "full_name": "Test User",
        "password": "password123"
    }
    response = client.post("/api/users/", json=invalid_data, headers=admin_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.api
@pytest.mark.database
def test_non_admin_cannot_access_users_router(client, auth_headers):
    """Regular authenticated users cannot manage /api/users endpoints."""
    response = client.get("/api/users/", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
