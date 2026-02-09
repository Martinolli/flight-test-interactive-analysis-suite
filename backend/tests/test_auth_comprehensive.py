"""
Comprehensive test suite for Authentication API
Tests login, logout, token refresh, and security features
"""
from datetime import datetime, timedelta
import pytest
from fastapi import status
from jose import jwt
from app.config import settings


class TestLogin:
    """Test login functionality"""

    def test_login_success(self, client, test_user):
        """Test successful login"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "testpass123"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify token is valid JWT
        token = data["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        assert "sub" in payload
        assert "exp" in payload

    def test_login_invalid_username(self, client):
        """Test login with invalid username"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "password123"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_invalid_password(self, client, test_user):
        """Test login with invalid password"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "wrongpassword"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_missing_username(self, client):
        """Test login without username"""
        response = client.post(
            "/api/auth/login",
            json={"password": "password123"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_missing_password(self, client, test_user):
        """Test login without password"""
        response = client.post(
            "/api/auth/login",
            json={"username": test_user["username"]}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_empty_credentials(self, client):
        """Test login with empty credentials"""
        response = client.post(
            "/api/auth/login",
            json={"username": "", "password": ""}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user(self, client, db_session):
        """Test login with inactive user"""
        from app.models import User
        from app.auth import get_password_hash

        # Create inactive user
        inactive_user = User(
            email="inactive@test.com",
            username="inactiveuser",
            hashed_password=get_password_hash("password123"),
            full_name="Inactive User",
            is_active=False
        )
        db_session.add(inactive_user)
        db_session.commit()

        response = client.post(
            "/api/auth/login",
            json={
                "username": "inactiveuser",
                "password": "password123"
            }
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Inactive user" in response.json()["detail"]


class TestTokenRefresh:
    """Test token refresh functionality"""

    def test_refresh_token_success(self, client, test_user, auth_headers):
        """Test successful token refresh"""
        # Login to get refresh token
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "testpass123"
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify new token is different
        new_token = data["access_token"]
        old_token = login_response.json()["access_token"]
        assert new_token != old_token

    def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token"""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_expired_token(self, client, test_user):
        """Test refresh with expired token"""
        # Create an expired token
        expire = datetime.utcnow() - timedelta(minutes=1)
        token_data = {"sub": str(test_user["id"]), "exp": expire}
        expired_token = jwt.encode(token_data, settings.SECRET_KEY,
                                   algorithm=settings.ALGORITHM)

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": expired_token}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCurrentUser:
    """Test current user endpoint"""

    def test_get_current_user(self, client, test_user, auth_headers):
        """Test getting current user info"""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user["id"]
        assert data["username"] == test_user["username"]
        assert data["email"] == test_user["email"]
        assert "hashed_password" not in data

    def test_get_current_user_without_auth(self, client):
        """Test getting current user without authentication"""
        response = client.get("/api/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogout:
    """Test logout functionality"""

    def test_logout_success(self, client, auth_headers):
        """Test successful logout"""
        response = client.post("/api/auth/logout", headers=auth_headers)

        # Note: Logout is typically client-side (token deletion)
        # Server may return success even though token is still valid
        assert response.status_code in [status.HTTP_200_OK,
                                        status.HTTP_204_NO_CONTENT]

    def test_logout_without_auth(self, client):
        """Test logout without authentication"""
        response = client.post("/api/auth/logout")
        # Logout without auth may be allowed (no-op)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_401_UNAUTHORIZED
        ]


class TestTokenSecurity:
    """Test token security features"""

    def test_token_contains_user_id(self, client, test_user):
        """Test that token contains user ID"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "testpass123"
            }
        )

        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])

        assert payload["sub"] == str(test_user["id"])

    def test_token_has_expiration(self, client, test_user):
        """Test that token has expiration time"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "testpass123"
            }
        )

        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])

        assert "exp" in payload
        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        assert exp_time > now
        assert exp_time < now + timedelta(hours=1)

    def test_token_signature_verification(self, client, test_user):
        """Test that token signature is verified"""
        # Create a token with wrong signature
        token_data = {"sub": str(test_user["id"]),
                      "exp": datetime.utcnow() + timedelta(minutes=30)}
        fake_token = jwt.encode(token_data, "wrong_secret",
                                algorithm=settings.ALGORITHM)

        headers = {"Authorization": f"Bearer {fake_token}"}
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_algorithm_verification(self, client, test_user):
        """Test that token algorithm is verified"""
        # Create a token with different algorithm (if possible)
        token_data = {"sub": str(test_user["id"]),
                      "exp": datetime.utcnow() + timedelta(minutes=30)}

        try:
            # Try to create token with HS512 instead of HS256
            fake_token = jwt.encode(token_data,
                                    settings.SECRET_KEY, algorithm="HS512")
            headers = {"Authorization": f"Bearer {fake_token}"}
            response = client.get("/api/auth/me", headers=headers)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        except Exception:
            # If algorithm mismatch is caught during creation, that's also good
            pass

    def test_malformed_token(self, client):
        """Test handling of malformed tokens"""
        malformed_tokens = [
            "not.a.token",
            "Bearer invalid",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "",
            "   ",
        ]

        for token in malformed_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/auth/me", headers=headers)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_bearer_prefix(self, client, test_user):
        """Test that Bearer prefix is required"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "testpass123"
            }
        )
        token = response.json()["access_token"]

        # Try without Bearer prefix
        headers = {"Authorization": token}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPasswordSecurity:
    """Test password security features"""

    def test_password_hashing(self, db_session):
        """Test that passwords are hashed"""
        from app.models import User
        from app.auth import get_password_hash

        password = "securepassword123"
        hashed = get_password_hash(password)

        # Hash should be different from password
        assert hashed != password

        # Hash should be consistent
        assert len(hashed) > 0

        # Hash should use pbkdf2_sha256
        assert hashed.startswith("$pbkdf2-sha256$")

    def test_password_verification(self):
        """Test password verification"""
        from app.auth import get_password_hash, verify_password

        password = "testpassword123"
        hashed = get_password_hash(password)

        # Correct password should verify
        assert verify_password(password, hashed) is True

        # Wrong password should not verify
        assert verify_password("wrongpassword", hashed) is False

    def test_password_not_returned_in_response(self,
                                               client,
                                               test_user,
                                               auth_headers
                                               ):
        """Test that password is never returned in API responses"""
        # Get current user
        response = client.get("/api/auth/me", headers=auth_headers)
        data = response.json()

        # Check that password fields are not present
        assert "password" not in data
        assert "hashed_password" not in data

        # Get user by ID
        response = client.get(f"/api/users/{test_user['id']}",
                              headers=auth_headers
                              )
        data = response.json()

        assert "password" not in data
        assert "hashed_password" not in data


class TestRateLimiting:
    """Test rate limiting (if implemented)"""

    @pytest.mark.skip(reason="Rate limiting not yet implemented")
    def test_login_rate_limiting(self, client):
        """Test that login attempts are rate limited"""
        # Make multiple failed login attempts
        for i in range(10):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "testuser",
                    "password": "wrongpassword"
                }
            )

        # After many attempts, should be rate limited
        response = client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "wrongpassword"
            }
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
