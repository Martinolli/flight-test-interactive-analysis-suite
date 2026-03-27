"""
FTIAS Backend - Authentication Router
Login, logout, and token management endpoints
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import auth, schemas
from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter()


@router.post("/login", response_model=schemas.Token)
async def login(login_data: schemas.LoginRequest,
                db: Session = Depends(get_db)):
    """
    Login endpoint - authenticate user and return JWT token
    """
    # Find user by username or email (frontend allows either)
    user = (
        db.query(User)
        .filter(
            or_(
                User.username == login_data.username,
                User.email == login_data.username,
            )
        )
        .first()
    )

    # Verify user exists and password is correct
    if not user or not auth.verify_password(
        login_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Create access token
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    refresh_token_value = auth.create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(_: User = Depends(auth.get_current_active_user)):
    """
    Logout endpoint - invalidate token (client-side)
    Note: JWT tokens are stateless, so logout is handled
    client-side by removing the token
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Get current authenticated user information
    """
    return current_user


class ProfileUpdate(BaseModel):
    """Schema for updating the current user's own profile."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


@router.patch("/me", response_model=schemas.UserResponse)
async def update_current_user(
    update: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_active_user),
):
    """
    Update the authenticated user's own profile (full_name, email).
    """
    if update.full_name is not None:
        current_user.full_name = update.full_name

    if update.email is not None:
        # Check that the new email is not already taken by another account
        existing = (
            db.query(User)
            .filter(User.email == update.email, User.id != current_user.id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use by another account.",
            )
        current_user.email = update.email

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/refresh", response_model=schemas.Token)
async def refresh_token(
    refresh: schemas.RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    """
    payload = auth.decode_token(refresh.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
