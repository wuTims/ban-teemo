"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import WebSocket

from ban_teemo.config import settings
from ban_teemo.api.routes.replay import router as replay_router
from ban_teemo.api.routes.simulator import router as simulator_router
from ban_teemo.api.websockets.replay_ws import replay_websocket
from ban_teemo.repositories.draft_repository import DraftRepository
from ban_teemo.services.replay_manager import ReplayManager
from ban_teemo.services.draft_service import DraftService


# Database path - use settings or default to draft_data.duckdb in repo root
def get_database_path() -> Path:
    """Get the database path from settings or default location."""
    if settings.database_path:
        db_path = Path(settings.database_path)
        if db_path.is_absolute():
            return db_path
        # Relative path - resolve from repo root
        repo_root = Path(__file__).parent.parent.parent.parent
        return repo_root / settings.database_path
    # Default: data/draft_data.duckdb in repo root
    return Path(__file__).parent.parent.parent.parent / "data" / "draft_data.duckdb"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    db_path = get_database_path()
    # Startup: Initialize repository and managers
    if not hasattr(app.state, "repository"):
        app.state.repository = DraftRepository(str(db_path))
    if not hasattr(app.state, "replay_manager"):
        app.state.replay_manager = ReplayManager()
    if not hasattr(app.state, "service"):
        app.state.service = DraftService(str(db_path))
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
    allow_origins=settings.cors_origins_list,
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
app.include_router(simulator_router)


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
