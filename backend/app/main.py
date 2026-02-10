"""
FTIAS Backend - Main Application
FastAPI application entry point
"""

import asyncio
import sys
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import Base, engine
from app.routers import auth, flight_tests, health, parameters, users

# Initialize FastAPI application
app = FastAPI(
    title="FTIAS API",
    description="Flight Test Interactive Analysis Suite - Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    # Avoid touching the real DB during pytest runs; tests provide
    # their own in-memory DB.
    if "pytest" not in sys.modules:
        max_wait_seconds = 30
        deadline = time.monotonic() + max_wait_seconds
        attempt = 0
        while True:
            attempt += 1
            try:
                Base.metadata.create_all(bind=engine)
                break
            except OperationalError as exc:
                remaining = deadline - time.monotonic()
                if attempt == 1:
                    print(
                        "🗄️  Database not reachable yet. "
                        "If you're running Postgres via Docker, start it with:"
                        "`docker compose up -d postgres` (from repo root)."
                    )
                if remaining <= 0:
                    print(
                        "❌ Database connection failed after multiple retries. "
                        "Check that Postgres is running and that your `.env` "
                        "values match (POSTGRES_HOST/PORT/USER/PASSWORD/DB or DATABASE_URL)."
                    )
                    raise exc
                sleep_seconds = min(2 ** min(attempt, 5), max(1.0, remaining))
                await asyncio.sleep(sleep_seconds)
    print("🚀 FTIAS Backend starting...")


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(
    auth.router, prefix="/api/auth", tags=["Authentication"]
)
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(
    flight_tests.router,
    prefix="/api/flight-tests",
    tags=["Flight Tests"],
)
app.include_router(
    parameters.router, prefix="/api/parameters", tags=["Parameters"]
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to FTIAS API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


# Shutdown event is defined below, startup event is defined above


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    print("👋 FTIAS Backend shutting down...")
