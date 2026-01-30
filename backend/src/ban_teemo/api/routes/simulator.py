"""REST endpoints for draft simulator."""

import threading
import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ban_teemo.models.simulator import SimulatorSession, GameResult
from ban_teemo.models.draft import DraftState, DraftAction, DraftPhase
from ban_teemo.models.team import Player, TeamContext
from ban_teemo.models.recommendations import PickRecommendation, RoleGroupedRecommendations
from ban_teemo.services.enemy_simulator_service import EnemySimulatorService
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine
from ban_teemo.services.ban_recommendation_service import BanRecommendationService
from ban_teemo.services.team_evaluation_service import TeamEvaluationService
from ban_teemo.services.scoring_logger import ScoringLogger
from ban_teemo.repositories.draft_repository import DraftRepository

# Constants
DEFAULT_PATCH_VERSION = "15.18"
MAX_TEAMS_LIMIT = 500
SESSION_TTL_SECONDS = 60 * 60
SESSION_CLEANUP_INTERVAL_SECONDS = 60

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# In-memory session storage with thread-safe access
_sessions: dict[str, SimulatorSession] = {}
_sessions_lock = threading.Lock()
_session_locks: dict[str, threading.Lock] = {}
_session_loggers: dict[str, ScoringLogger] = {}  # Diagnostic loggers per session
_cleanup_lock = threading.Lock()
_last_cleanup = 0.0


def _is_session_expired(session: SimulatorSession, now: float) -> bool:
    return (now - session.last_access) >= SESSION_TTL_SECONDS


def _touch_session(session: SimulatorSession, now: float) -> None:
    session.last_access = now


def _prune_expired_sessions(now: float | None = None) -> None:
    """Remove expired sessions opportunistically."""
    global _last_cleanup
    now = now or time.time()
    if now - _last_cleanup < SESSION_CLEANUP_INTERVAL_SECONDS:
        return

    with _cleanup_lock:
        if now - _last_cleanup < SESSION_CLEANUP_INTERVAL_SECONDS:
            return

        expired: list[str] = []
        with _sessions_lock:
            for session_id, session in _sessions.items():
                lock = _session_locks.get(session_id)
                if lock and lock.locked():
                    continue
                if _is_session_expired(session, now):
                    expired.append(session_id)

            for session_id in expired:
                # Save and remove logger before removing session
                if session_id in _session_loggers:
                    _session_loggers[session_id].save(suffix="_expired")
                    _session_loggers.pop(session_id, None)
                _sessions.pop(session_id, None)
                _session_locks.pop(session_id, None)

        _last_cleanup = now


def _get_session_with_lock(session_id: str) -> tuple[SimulatorSession, threading.Lock]:
    """Fetch session and its lock, creating the lock if needed."""
    _prune_expired_sessions()
    with _sessions_lock:
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[session_id] = lock

    return session, lock


def _get_or_create_services(request: Request) -> tuple[
    EnemySimulatorService,
    PickRecommendationEngine,
    BanRecommendationService,
    TeamEvaluationService,
    DraftRepository,
]:
    """Get or create services from app state."""
    # Use existing repository from app state
    repo = request.app.state.repository

    # Lazily create simulator-specific services
    if not hasattr(request.app.state, "enemy_simulator_service"):
        data_path = str(repo.data_path)
        request.app.state.enemy_simulator_service = EnemySimulatorService(data_path)
        request.app.state.pick_engine = PickRecommendationEngine()
        request.app.state.ban_service = BanRecommendationService(draft_repository=repo)
        request.app.state.team_eval_service = TeamEvaluationService()

    return (
        request.app.state.enemy_simulator_service,
        request.app.state.pick_engine,
        request.app.state.ban_service,
        request.app.state.team_eval_service,
        repo,
    )


class StartSimulatorRequest(BaseModel):
    blue_team_id: str
    red_team_id: str
    coaching_side: Literal["blue", "red"]
    series_length: Literal[1, 3, 5] = 1
    draft_mode: Literal["normal", "fearless"] = "normal"


class ActionRequest(BaseModel):
    champion: str


class CompleteGameRequest(BaseModel):
    winner: Literal["blue", "red"]


@router.post("/sessions", status_code=201)
async def start_simulator(request: Request, body: StartSimulatorRequest):
    """Create a new simulator session."""
    _prune_expired_sessions()
    enemy_service, pick_engine, ban_service, team_eval_service, repo = _get_or_create_services(request)

    session_id = f"sim_{uuid.uuid4().hex[:12]}"

    # Load team info using the new get_team_context method
    blue_team = repo.get_team_context(body.blue_team_id, "blue")
    red_team = repo.get_team_context(body.red_team_id, "red")

    if not blue_team or not red_team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Determine enemy team
    enemy_team_id = body.red_team_id if body.coaching_side == "blue" else body.blue_team_id

    # Initialize enemy strategy
    try:
        enemy_strategy = enemy_service.initialize_enemy_strategy(enemy_team_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create initial draft state
    draft_state = DraftState(
        game_id=f"{session_id}_g1",
        series_id=session_id,
        game_number=1,
        patch_version=DEFAULT_PATCH_VERSION,
        match_date=None,
        blue_team=blue_team,
        red_team=red_team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban",
    )

    session = SimulatorSession(
        session_id=session_id,
        blue_team=blue_team,
        red_team=red_team,
        coaching_side=body.coaching_side,
        series_length=body.series_length,
        draft_mode=body.draft_mode,
        draft_state=draft_state,
        enemy_strategy=enemy_strategy,
    )

    now = time.time()
    _touch_session(session, now)
    with _sessions_lock:
        _sessions[session_id] = session
        _session_locks[session_id] = threading.Lock()

        # Initialize diagnostic logger for this session
        logger = ScoringLogger()
        logger.start_session(
            session_id=session_id,
            mode="simulator",
            blue_team=blue_team.name,
            red_team=red_team.name,
            coaching_side=body.coaching_side,
            game_number=1,
            extra_metadata={
                "series_length": body.series_length,
                "draft_mode": body.draft_mode,
            }
        )
        _session_loggers[session_id] = logger

    is_our_turn = draft_state.next_team == body.coaching_side

    return {
        "session_id": session_id,
        "game_number": 1,
        "blue_team": _serialize_team(blue_team),
        "red_team": _serialize_team(red_team),
        "draft_state": _serialize_draft_state(draft_state),
        "is_our_turn": is_our_turn,
    }


@router.post("/sessions/{session_id}/actions")
async def submit_action(
    request: Request,
    session_id: str,
    body: ActionRequest,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
):
    """User submits their pick/ban."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state

        if draft_state.next_team != session.coaching_side:
            raise HTTPException(status_code=400, detail="Not your turn")

        # Validate champion is available
        unavailable = set(
            draft_state.blue_bans + draft_state.red_bans +
            draft_state.blue_picks + draft_state.red_picks
        ) | session.fearless_blocked_set
        if body.champion in unavailable:
            raise HTTPException(
                status_code=400,
                detail=f"Champion '{body.champion}' is not available (already picked, banned, or fearless blocked)"
            )

        # Create action
        action = DraftAction(
            sequence=len(draft_state.actions) + 1,
            action_type=draft_state.next_action,
            team_side=draft_state.next_team,
            champion_id=body.champion.lower().replace(" ", ""),
            champion_name=body.champion,
        )

        # Apply action
        _apply_action(session, action)

        return _build_response(request, session, include_recommendations, include_evaluation)


@router.post("/sessions/{session_id}/actions/enemy")
async def trigger_enemy_action(
    request: Request,
    session_id: str,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
):
    """Triggers enemy pick/ban generation."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state

        if draft_state.next_team == session.coaching_side:
            raise HTTPException(status_code=400, detail="Not enemy's turn")

        enemy_service, _, _, _, _ = _get_or_create_services(request)

        # Get unavailable champions
        unavailable = set(
            draft_state.blue_bans + draft_state.red_bans +
            draft_state.blue_picks + draft_state.red_picks
        ) | session.fearless_blocked_set

        # Generate enemy action
        champion, source = enemy_service.generate_action(
            session.enemy_strategy,
            sequence=len(draft_state.actions) + 1,
            unavailable=unavailable,
        )

        action = DraftAction(
            sequence=len(draft_state.actions) + 1,
            action_type=draft_state.next_action,
            team_side=draft_state.next_team,
            champion_id=champion.lower().replace(" ", ""),
            champion_name=champion,
        )

        _apply_action(session, action)

        response = _build_response(request, session, include_recommendations, include_evaluation)
        response["source"] = source
        return response


@router.post("/sessions/{session_id}/games/complete")
async def complete_game(request: Request, session_id: str, body: CompleteGameRequest):
    """Records winner, advances series."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state

        # Record result
        result = GameResult(
            game_number=session.current_game,
            winner=body.winner,
            blue_comp=draft_state.blue_picks,
            red_comp=draft_state.red_picks,
        )
        session.game_results.append(result)

        # Fearless blocking - store with team and game metadata for tooltips
        if session.draft_mode == "fearless":
            for champ in draft_state.blue_picks:
                session.fearless_blocked[champ] = {
                    "team": "blue",
                    "game": session.current_game,
                }
            for champ in draft_state.red_picks:
                session.fearless_blocked[champ] = {
                    "team": "red",
                    "game": session.current_game,
                }

        # Save diagnostic logs for this game
        if session_id in _session_loggers:
            _session_loggers[session_id].save(suffix=f"_g{session.current_game}")

        return {
            "series_status": {
                "blue_wins": session.series_score[0],
                "red_wins": session.series_score[1],
                "games_played": len(session.game_results),
                "series_complete": session.series_complete,
            },
            "fearless_blocked": session.fearless_blocked,
            "next_game_ready": not session.series_complete,
        }


@router.post("/sessions/{session_id}/games/next")
async def next_game(request: Request, session_id: str):
    """Starts next game in series."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        if session.series_complete:
            raise HTTPException(status_code=400, detail="Series already complete")

        enemy_service, _, _, _, _ = _get_or_create_services(request)

        session.current_game += 1

        # Reset draft state
        session.draft_state = DraftState(
            game_id=f"{session.session_id}_g{session.current_game}",
            series_id=session.session_id,
            game_number=session.current_game,
            patch_version=DEFAULT_PATCH_VERSION,
            match_date=None,
            blue_team=session.blue_team,
            red_team=session.red_team,
            actions=[],
            current_phase=DraftPhase.BAN_PHASE_1,
            next_team="blue",
            next_action="ban",
        )

        # Re-initialize enemy strategy
        enemy_team_id = session.red_team.id if session.coaching_side == "blue" else session.blue_team.id
        session.enemy_strategy = enemy_service.initialize_enemy_strategy(enemy_team_id)

        return {
            "game_number": session.current_game,
            "draft_state": _serialize_draft_state(session.draft_state),
            "fearless_blocked": session.fearless_blocked,
        }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get current session state."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        return {
            "session_id": session_id,
            "status": "drafting" if session.draft_state.current_phase != DraftPhase.COMPLETE else "game_complete",
            "game_number": session.current_game,
            "draft_state": _serialize_draft_state(session.draft_state),
            "series_status": {
                "blue_wins": session.series_score[0],
                "red_wins": session.series_score[1],
                "series_complete": session.series_complete,
            },
            "fearless_blocked": session.fearless_blocked,
        }


@router.get("/sessions/{session_id}/recommendations")
async def get_recommendations(request: Request, session_id: str):
    """Get pick/ban recommendations for current draft state."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state
        action_count = len(draft_state.actions)

        if draft_state.current_phase == DraftPhase.COMPLETE:
            return {
                "for_action_count": action_count,
                "phase": "COMPLETE",
                "recommendations": [],
            }

        _, pick_engine, ban_service, _, _ = _get_or_create_services(request)

        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        enemy_team_id = session.red_team.id if session.coaching_side == "blue" else session.blue_team.id

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks
        banned = draft_state.blue_bans + draft_state.red_bans

        recommendations = []
        role_grouped = None

        if draft_state.next_action == "ban":
            all_unavailable = list(set(banned) | session.fearless_blocked_set)
            recommendations = ban_service.get_ban_recommendations(
                enemy_team_id=enemy_team_id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_unavailable,
                phase=draft_state.current_phase.value,
                limit=5,
            )
        else:
            # For pick phase, get more recommendations for role grouping
            all_picks = pick_engine.get_recommendations(
                team_players=[{"name": p.name, "role": p.role} for p in our_team.players],
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=list(set(banned) | session.fearless_blocked_set),
                limit=20,  # Get more for role grouping
            )

            # PRIMARY: Top 5 overall recommendations (phase-optimized)
            recommendations = all_picks[:5]

            # SUPPLEMENTAL: Alternative view grouped by role
            # Use case: late draft role filling, draft planning
            pick_objects = [
                PickRecommendation(
                    champion_name=p["champion_name"],
                    confidence=p.get("confidence", 0.0),
                    suggested_role=p.get("suggested_role"),
                    flag=p.get("flag"),
                    reasons=p.get("reasons", []),
                    score=p.get("score", 0.0),
                    base_score=p.get("base_score"),
                    synergy_multiplier=p.get("synergy_multiplier"),
                    components=p.get("components", {}),
                    proficiency_source=p.get("proficiency_source"),
                    proficiency_player=p.get("proficiency_player"),
                )
                for p in all_picks
            ]
            grouped = RoleGroupedRecommendations.from_picks(pick_objects, limit_per_role=2)
            role_grouped = {
                "view_type": "supplemental",
                "description": "Alternative view: top picks per unfilled role",
                **grouped.to_dict()
            }

        response = {
            "for_action_count": action_count,
            "phase": draft_state.current_phase.value,
            "recommendations": recommendations,
        }

        # Only include role_grouped for pick phases
        if role_grouped is not None:
            response["role_grouped"] = role_grouped

        return response


@router.get("/sessions/{session_id}/evaluation")
async def get_evaluation(request: Request, session_id: str):
    """Get team composition evaluation for current draft state."""
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state
        action_count = len(draft_state.actions)

        _, _, _, team_eval_service, _ = _get_or_create_services(request)

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks

        if not our_picks and not enemy_picks:
            return {
                "for_action_count": action_count,
                "our_evaluation": None,
                "enemy_evaluation": None,
                "matchup_advantage": 1.0,
                "matchup_description": "No picks yet",
            }

        evaluation = team_eval_service.evaluate_vs_enemy(our_picks, enemy_picks)

        return {
            "for_action_count": action_count,
            "our_evaluation": evaluation["our_evaluation"],
            "enemy_evaluation": evaluation["enemy_evaluation"],
            "matchup_advantage": evaluation["matchup_advantage"],
            "matchup_description": evaluation["matchup_description"],
        }


@router.get("/teams")
async def list_teams(request: Request, limit: int = 50):
    """Get list of available teams for simulator setup."""
    _prune_expired_sessions()
    _, _, _, _, repo = _get_or_create_services(request)

    # Clamp limit to reasonable range to prevent abuse
    safe_limit = max(1, min(limit, MAX_TEAMS_LIMIT))

    # Query teams from database
    teams = repo._query(f"""
        SELECT DISTINCT id, name
        FROM teams
        ORDER BY name
        LIMIT {safe_limit}
    """)

    return {"teams": teams}


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str):
    """End session early."""
    with _sessions_lock:
        # Save diagnostic logs before ending
        if session_id in _session_loggers:
            _session_loggers[session_id].save(suffix="_ended")
            _session_loggers.pop(session_id, None)
        if session_id in _sessions:
            del _sessions[session_id]
            _session_locks.pop(session_id, None)
    return {"status": "ended"}


# Helper functions

def _apply_action(session: SimulatorSession, action: DraftAction):
    """Apply an action to the session's draft state."""
    draft_state = session.draft_state
    draft_state.actions.append(action)

    # Update phase
    action_count = len(draft_state.actions)
    if action_count >= 20:
        draft_state.current_phase = DraftPhase.COMPLETE
        draft_state.next_team = None
        draft_state.next_action = None
    else:
        if action_count < 6:
            draft_state.current_phase = DraftPhase.BAN_PHASE_1
        elif action_count < 12:
            draft_state.current_phase = DraftPhase.PICK_PHASE_1
        elif action_count < 16:
            draft_state.current_phase = DraftPhase.BAN_PHASE_2
        else:
            draft_state.current_phase = DraftPhase.PICK_PHASE_2

        # Standard draft order
        draft_order = _get_draft_order()
        if action_count < len(draft_order):
            next_team, next_action = draft_order[action_count]
            draft_state.next_team = next_team
            draft_state.next_action = next_action


def _get_draft_order() -> list[tuple[str, str]]:
    """Return standard LoL draft order."""
    return [
        ("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"),
        ("blue", "pick"), ("red", "pick"), ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick"),
        ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"),
        ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick"),
    ]


def _build_response(
    request: Request,
    session: SimulatorSession,
    include_recommendations: bool = False,
    include_evaluation: bool = False,
) -> dict:
    """Build response after an action, optionally including computed data."""
    draft_state = session.draft_state
    is_our_turn = draft_state.next_team == session.coaching_side
    action_count = len(draft_state.actions)

    # Get logger for this session
    logger = _session_loggers.get(session.session_id)

    # Log the action that just occurred
    if draft_state.actions and logger:
        last_action = draft_state.actions[-1]
        # We'll log actual action with empty recommendations for now
        # Real recommendations are logged below when generated
        logger.log_draft_state(
            action_count=action_count,
            phase=draft_state.current_phase.value,
            blue_picks=draft_state.blue_picks,
            red_picks=draft_state.red_picks,
            blue_bans=draft_state.blue_bans,
            red_bans=draft_state.red_bans,
        )

    response = {
        "action": _serialize_action(draft_state.actions[-1]) if draft_state.actions else None,
        "draft_state": _serialize_draft_state(draft_state),
        "is_our_turn": is_our_turn,
    }

    # Optionally include recommendations (to avoid extra round trip)
    if include_recommendations and draft_state.current_phase != DraftPhase.COMPLETE:
        _, pick_engine, ban_service, _, _ = _get_or_create_services(request)

        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        enemy_team_id = session.red_team.id if session.coaching_side == "blue" else session.blue_team.id

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks
        banned = draft_state.blue_bans + draft_state.red_bans
        team_players = [{"name": p.name, "role": p.role} for p in our_team.players]
        enemy_players = [{"name": p.name, "role": p.role} for p in
                         (session.red_team if session.coaching_side == "blue" else session.blue_team).players]

        if draft_state.next_action == "ban":
            all_unavailable = list(set(banned) | session.fearless_blocked_set)
            response["recommendations"] = ban_service.get_ban_recommendations(
                enemy_team_id=enemy_team_id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_unavailable,
                phase=draft_state.current_phase.value,
                limit=5,
            )
            # Log ban recommendations
            if logger:
                logger.log_ban_recommendations(
                    action_count=action_count,
                    phase=draft_state.current_phase.value,
                    for_team=session.coaching_side,
                    our_picks=our_picks,
                    enemy_picks=enemy_picks,
                    banned=all_unavailable,
                    enemy_players=enemy_players,
                    recommendations=response["recommendations"],
                )
        else:
            response["recommendations"] = pick_engine.get_recommendations(
                team_players=team_players,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=list(set(banned) | session.fearless_blocked_set),
                limit=5,
            )
            # Log pick recommendations
            if logger:
                logger.log_pick_recommendations(
                    action_count=action_count,
                    phase=draft_state.current_phase.value,
                    for_team=session.coaching_side,
                    our_picks=our_picks,
                    enemy_picks=enemy_picks,
                    banned=banned,
                    team_players=team_players,
                    candidates_count=len(response["recommendations"]),
                    filled_roles=[],  # Would need pick_engine internals
                    unfilled_roles=[],
                    recommendations=response["recommendations"],
                )

    # Optionally include evaluation (to avoid extra round trip)
    if include_evaluation:
        _, _, _, team_eval_service, _ = _get_or_create_services(request)

        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks

        if our_picks or enemy_picks:
            evaluation = team_eval_service.evaluate_vs_enemy(our_picks, enemy_picks)
            response["evaluation"] = evaluation

    return response


def _serialize_team(team: TeamContext) -> dict:
    """Serialize TeamContext to dict."""
    return {
        "id": team.id,
        "name": team.name,
        "side": team.side,
        "players": [{"id": p.id, "name": p.name, "role": p.role} for p in team.players],
    }


def _serialize_draft_state(state: DraftState) -> dict:
    """Serialize DraftState to dict."""
    return {
        "phase": state.current_phase.value if hasattr(state.current_phase, "value") else state.current_phase,
        "next_team": state.next_team,
        "next_action": state.next_action,
        "blue_bans": state.blue_bans,
        "red_bans": state.red_bans,
        "blue_picks": state.blue_picks,
        "red_picks": state.red_picks,
        "action_count": len(state.actions),
    }


def _serialize_action(action: DraftAction) -> dict:
    """Serialize DraftAction to dict."""
    return {
        "sequence": action.sequence,
        "action_type": action.action_type,
        "team_side": action.team_side,
        "champion_id": action.champion_id,
        "champion_name": action.champion_name,
    }
