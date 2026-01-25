"""REST endpoints for replay functionality."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ban_teemo.models.draft import DraftAction, DraftPhase, DraftState
from ban_teemo.models.team import Player, TeamContext

router = APIRouter(prefix="/api", tags=["replay"])


class StartReplayRequest(BaseModel):
    """Request body for starting a replay."""

    series_id: str
    game_number: int
    speed: float = 1.0
    delay_seconds: float = 3.0


class StartReplayResponse(BaseModel):
    """Response from starting a replay."""

    session_id: str
    total_actions: int
    blue_team: str
    red_team: str
    patch: str | None
    websocket_url: str


class SeriesInfo(BaseModel):
    """Brief series information for listing."""

    id: str
    match_date: str
    format: str
    blue_team_id: str
    blue_team_name: str
    red_team_id: str
    red_team_name: str


class SeriesListResponse(BaseModel):
    """Response containing list of series."""

    series: list[SeriesInfo]


class PlayerInfo(BaseModel):
    """Player information for preview."""

    id: str
    name: str
    role: str


class TeamPreview(BaseModel):
    """Team preview information."""

    id: str
    name: str
    side: str
    players: list[PlayerInfo]


class GamePreviewResponse(BaseModel):
    """Response for game preview (teams + players, no draft)."""

    game_id: str
    series_id: str
    game_number: int
    patch: str | None
    blue_team: TeamPreview
    red_team: TeamPreview


@router.get("/series", response_model=SeriesListResponse)
def list_series(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """List available series for replay."""
    repo = request.app.state.repository
    series_data = repo.get_series_list(limit=limit)
    return SeriesListResponse(
        series=[SeriesInfo(**s) for s in series_data]
    )


@router.get("/series/{series_id}/games")
def get_series_games(request: Request, series_id: str):
    """Get all games in a series."""
    repo = request.app.state.repository
    games = repo.get_games_for_series(series_id)
    if not games:
        raise HTTPException(404, f"Series not found: {series_id}")
    return {"series_id": series_id, "games": games}


@router.get("/game/preview/{series_id}/{game_number}", response_model=GamePreviewResponse)
def get_game_preview(request: Request, series_id: str, game_number: int):
    """Get team and player info for a game without starting replay.

    Returns team names, IDs, and players for display before starting replay.
    """
    repo = request.app.state.repository

    # Get game info
    game_info = repo.get_game_info(series_id, game_number)
    if not game_info:
        raise HTTPException(404, f"Game not found: {series_id} game {game_number}")

    game_id = game_info["game_id"]

    # Load teams by actual game side
    blue_team_data = repo.get_team_for_game_side(game_id, "blue")
    red_team_data = repo.get_team_for_game_side(game_id, "red")

    if not blue_team_data or not red_team_data:
        raise HTTPException(500, "Failed to load team data")

    # Load players
    blue_players = repo.get_players_for_game_by_side(game_id, "blue")
    red_players = repo.get_players_for_game_by_side(game_id, "red")

    return GamePreviewResponse(
        game_id=game_id,
        series_id=series_id,
        game_number=game_number,
        patch=game_info.get("patch_version"),
        blue_team=TeamPreview(
            id=blue_team_data["id"],
            name=blue_team_data["name"],
            side="blue",
            players=[PlayerInfo(id=p["id"], name=p["name"], role=p["role"]) for p in blue_players],
        ),
        red_team=TeamPreview(
            id=red_team_data["id"],
            name=red_team_data["name"],
            side="red",
            players=[PlayerInfo(id=p["id"], name=p["name"], role=p["role"]) for p in red_players],
        ),
    )


@router.post("/replay/start", response_model=StartReplayResponse)
def start_replay(request: Request, body: StartReplayRequest):
    """Create a replay session and return session_id.

    Client should then connect to the WebSocket at websocket_url
    to receive draft actions.
    """
    repo = request.app.state.repository
    service = request.app.state.service
    manager = request.app.state.replay_manager

    # Load game info
    game_info = repo.get_game_info(body.series_id, body.game_number)
    if not game_info:
        raise HTTPException(
            404, f"Game not found: {body.series_id} game {body.game_number}"
        )

    game_id = game_info["game_id"]

    # Load teams by which side they actually played on in this game
    # (not series-level assignments which can swap between games)
    blue_team_data = repo.get_team_for_game_side(game_id, "blue")
    red_team_data = repo.get_team_for_game_side(game_id, "red")

    if not blue_team_data or not red_team_data:
        raise HTTPException(500, "Failed to load team data for game")

    blue_players = repo.get_players_for_game_by_side(game_id, "blue")
    red_players = repo.get_players_for_game_by_side(game_id, "red")

    blue_team = TeamContext(
        id=blue_team_data["id"],
        name=blue_team_data["name"],
        side="blue",
        players=[Player(id=p["id"], name=p["name"], role=p["role"]) for p in blue_players],
    )
    red_team = TeamContext(
        id=red_team_data["id"],
        name=red_team_data["name"],
        side="red",
        players=[Player(id=p["id"], name=p["name"], role=p["role"]) for p in red_players],
    )

    # Load draft actions
    actions_data = repo.get_draft_actions(game_id)
    actions = [
        DraftAction(
            sequence=a["sequence"],
            action_type=a["action_type"],
            team_side=a["team_side"],
            champion_id=a["champion_id"],
            champion_name=a["champion_name"],
        )
        for a in actions_data
    ]

    # Parse match date
    match_date_str = game_info["match_date"]
    if isinstance(match_date_str, str):
        # Handle ISO format date string
        match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
    else:
        match_date = match_date_str

    # Determine first action's team/type from actual game data
    first_action = actions[0] if actions else None
    first_team = first_action.team_side if first_action else None
    first_action_type = first_action.action_type if first_action else None

    # Build initial draft state (empty - no actions yet)
    initial_state = DraftState(
        game_id=game_id,
        series_id=body.series_id,
        game_number=body.game_number,
        patch_version=game_info["patch_version"] or "unknown",
        match_date=match_date,
        blue_team=blue_team,
        red_team=red_team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team=first_team,
        next_action=first_action_type,
    )

    # Create session
    session = manager.create_session(
        game_id=game_id,
        series_id=body.series_id,
        game_number=body.game_number,
        actions=actions,
        draft_state=initial_state,
        speed=body.speed,
        delay_seconds=body.delay_seconds,
    )

    return StartReplayResponse(
        session_id=session.id,
        total_actions=len(actions),
        blue_team=blue_team.name,
        red_team=red_team.name,
        patch=game_info["patch_version"],
        websocket_url=f"/ws/replay/{session.id}",
    )


@router.get("/replay/{session_id}")
def get_replay_status(request: Request, session_id: str):
    """Get current status of a replay session."""
    manager = request.app.state.replay_manager
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")

    return {
        "session_id": session.id,
        "status": session.status.value,
        "current_index": session.current_index,
        "total_actions": len(session.all_actions),
        "speed": session.speed,
    }


@router.delete("/replay/{session_id}")
def stop_replay(request: Request, session_id: str):
    """Stop and remove a replay session."""
    manager = request.app.state.replay_manager
    session = manager.get_session(session_id)

    if not session:
        raise HTTPException(404, f"Session not found: {session_id}")

    manager.remove_session(session_id)
    return {"success": True, "session_id": session_id}
