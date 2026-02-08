"""
FTIAS Backend - Health Check Router
Health check and status endpoints
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint

    Checks:
    - API is running
    - Database connection is working

    Returns:
        HealthResponse: Health status
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except SQLAlchemyError as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        database=db_status,
        timestamp=datetime.utcnow(),
    )


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint

    Returns:
        dict: Pong response
    """
    return {"message": "pong", "timestamp": datetime.utcnow()}
