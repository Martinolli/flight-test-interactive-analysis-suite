"""
FTIAS Backend - Main Application
FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import health, users

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI application
app = FastAPI(
    title="FTIAS API",
    description="Flight Test Interactive Analysis Suite - Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    print("🚀 FTIAS Backend starting...")
    print(f"📊 Database: {settings.DATABASE_URL}")
    print(f"🔧 Debug mode: {settings.DEBUG}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    print("👋 FTIAS Backend shutting down...")
