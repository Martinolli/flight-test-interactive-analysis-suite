"""
FTIAS Backend - Main Application
FastAPI application entry point
"""

import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import health, users

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
    # Avoid touching the real DB during pytest runs; tests provide their own in-memory DB.
    if "pytest" not in sys.modules:
        Base.metadata.create_all(bind=engine)
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
app.include_router(users.router, prefix="/api/users", tags=["Users"])


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
