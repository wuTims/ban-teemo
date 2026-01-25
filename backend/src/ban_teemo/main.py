"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import WebSocket

from ban_teemo.config import settings
from ban_teemo.api.routes.replay import router as replay_router
from ban_teemo.api.websockets.replay_ws import replay_websocket
from ban_teemo.repositories.draft_repository import DraftRepository
from ban_teemo.services.replay_manager import ReplayManager
from ban_teemo.services.draft_service import DraftService


# Data path - use outputs/full_2024_2025/csv relative to project root
# __file__ = .../backend/src/ban_teemo/main.py -> need 4 parents to reach ban-teemo/
DATA_PATH = Path(__file__).parent.parent.parent.parent / "outputs" / "full_2024_2025" / "csv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: Initialize repository and managers
    app.state.repository = DraftRepository(str(DATA_PATH))
    app.state.replay_manager = ReplayManager()
    app.state.service = DraftService(str(DATA_PATH))
    yield
    # Shutdown: Clean up resources
    pass


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


# Register routers
app.include_router(replay_router)


# WebSocket endpoint for replay
@app.websocket("/ws/replay/{session_id}")
async def websocket_replay(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for draft replay streaming."""
    await replay_websocket(
        websocket,
        session_id,
        app.state.replay_manager,
        app.state.service,
    )
