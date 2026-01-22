"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ban_teemo.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: Initialize database connections, load models, etc.
    yield
    # Shutdown: Clean up resources


app = FastAPI(
    title="Ban Teemo",
    description="LoL Draft Assistant - Real-time draft recommendations",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ban-teemo"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Ban Teemo API",
        "version": "0.1.0",
        "docs": "/docs",
    }
