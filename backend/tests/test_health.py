"""
FTIAS Backend - Health Endpoint Tests
"""

import pytest
from fastapi import status


@pytest.mark.api
def test_root_endpoint(client):
    """Test root endpoint returns welcome message"""
    response = client.get("/")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data
    assert "FTIAS" in data["message"]
    assert "version" in data
    assert "status" in data
    assert data["status"] == "running"


@pytest.mark.api
def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/api/health")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "database" in data
    assert "timestamp" in data


@pytest.mark.api
def test_ping_endpoint(client):
    """Test ping endpoint"""
    response = client.get("/api/ping")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data
    assert data["message"] == "pong"
    assert "timestamp" in data
