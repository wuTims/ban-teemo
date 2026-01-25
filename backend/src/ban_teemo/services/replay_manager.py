"""Replay session management."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ban_teemo.models.draft import DraftAction, DraftState


class ReplayStatus(str, Enum):
    """Status of a replay session."""

    PENDING = "pending"  # Created, not started
    PLAYING = "playing"  # Auto-advancing
    PAUSED = "paused"  # Waiting for resume
    COMPLETE = "complete"  # All actions sent


@dataclass
class ReplaySession:
    """An active replay session."""

    id: str
    game_id: str
    series_id: str
    game_number: int

    # Replay state
    status: ReplayStatus = ReplayStatus.PENDING
    current_index: int = 0  # Next action to send (0-19)
    speed: float = 1.0  # 1.0 = normal, 2.0 = 2x speed
    delay_seconds: float = 3.0  # Base delay between actions

    # Preloaded data
    all_actions: list[DraftAction] = field(default_factory=list)
    draft_state: DraftState | None = None

    # Connection tracking
    created_at: datetime = field(default_factory=datetime.now)
    websocket: Any = None  # Active WebSocket connection
    timer_task: asyncio.Task | None = None  # Background timer


class ReplayManager:
    """In-memory manager for active replay sessions."""

    def __init__(self):
        self.sessions: dict[str, ReplaySession] = {}

    def create_session(
        self,
        game_id: str,
        series_id: str,
        game_number: int,
        actions: list[DraftAction],
        draft_state: DraftState,
        speed: float = 1.0,
        delay_seconds: float = 3.0,
    ) -> ReplaySession:
        """Create a new replay session.

        Args:
            game_id: The game being replayed
            series_id: The series containing the game
            game_number: Game number within the series
            actions: All draft actions for the game (preloaded)
            draft_state: Initial draft state (empty actions)
            speed: Playback speed multiplier (2.0 = 2x speed)
            delay_seconds: Base delay between actions

        Returns:
            The created ReplaySession
        """
        session_id = str(uuid.uuid4())[:8]  # Short ID for URLs
        session = ReplaySession(
            id=session_id,
            game_id=game_id,
            series_id=series_id,
            game_number=game_number,
            all_actions=actions,
            draft_state=draft_state,
            speed=speed,
            delay_seconds=delay_seconds,
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ReplaySession | None:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session and cancel any running timer."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session.timer_task and not session.timer_task.done():
                session.timer_task.cancel()
            del self.sessions[session_id]

    def list_sessions(self) -> list[dict]:
        """List all active sessions (for debugging)."""
        return [
            {
                "id": s.id,
                "game_id": s.game_id,
                "status": s.status.value,
                "current_index": s.current_index,
                "total_actions": len(s.all_actions),
            }
            for s in self.sessions.values()
        ]
