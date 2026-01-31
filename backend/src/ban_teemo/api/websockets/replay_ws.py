"""WebSocket handler for draft replay streaming."""

import asyncio
import traceback

from fastapi import WebSocket, WebSocketDisconnect

from ban_teemo.models.draft import DraftPhase, DraftState
from ban_teemo.models.recommendations import Recommendations, RoleGroupedRecommendations
from ban_teemo.models.team import TeamContext
from ban_teemo.services.draft_service import DraftService
from ban_teemo.services.replay_manager import ReplayManager, ReplaySession, ReplayStatus
from ban_teemo.services.scoring_logger import ScoringLogger


async def replay_websocket(
    websocket: WebSocket,
    session_id: str,
    manager: ReplayManager,
    service: DraftService,
):
    """Handle WebSocket connection for draft replay.

    Streams draft actions at configured intervals with recommendations.

    Args:
        websocket: The WebSocket connection
        session_id: ID of the replay session
        manager: ReplayManager instance
        service: DraftService instance
    """
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    session.websocket = websocket

    # Initialize diagnostic logger for this replay
    logger = ScoringLogger()
    logger.start_session(
        session_id=session_id,
        mode="replay",
        blue_team=session.draft_state.blue_team.name,
        red_team=session.draft_state.red_team.name,
        series_id=session.draft_state.series_id,
        game_number=session.draft_state.game_number,
        extra_metadata={
            "patch": session.draft_state.patch_version,
            "total_actions": len(session.all_actions),
        }
    )

    try:
        # Send initial state
        await websocket.send_json({
            "type": "session_start",
            "session_id": session_id,
            "series_id": session.series_id,
            "game_number": session.game_number,
            "blue_team": _serialize_team(session.draft_state.blue_team),
            "red_team": _serialize_team(session.draft_state.red_team),
            "total_actions": len(session.all_actions),
            "patch": session.draft_state.patch_version,
            "series_score_before": session.series_score_before,
            "series_score_after": session.series_score_after,
            "winner_team_id": session.winner_team_id,
            "winner_side": session.winner_side,
        })

        # Start the replay loop
        session.status = ReplayStatus.PLAYING
        await _run_replay_loop(session, service, websocket, logger)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Log the full error with traceback
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.log_error(error_msg)
        # Send error before closing
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "traceback": traceback.format_exc(),
            })
        except Exception:
            pass
    finally:
        # Save diagnostic logs
        logger.save()
        session.websocket = None
        manager.remove_session(session_id)


async def _run_replay_loop(
    session: ReplaySession,
    service: DraftService,
    websocket: WebSocket,
    logger: ScoringLogger,
):
    """Main replay loop - sends actions with delays.

    Args:
        session: The replay session
        service: DraftService for building state and recommendations
        websocket: WebSocket to send messages on
        logger: ScoringLogger for diagnostic capture
    """
    # Generate recommendations for the FIRST action before loop starts
    # These are what we recommended before any action was taken
    initial_state = service.build_draft_state_at(
        session.draft_state,
        session.all_actions,
        0,  # Empty state - no actions yet
    )
    pending_recommendations = None
    if initial_state.next_team:
        pending_recommendations = service.get_recommendations(
            initial_state,
            for_team=initial_state.next_team,
        )

    while session.current_index < len(session.all_actions):
        if session.status == ReplayStatus.PAUSED:
            await asyncio.sleep(0.1)
            continue

        # Get current action
        action = session.all_actions[session.current_index]

        # The recommendations to send WITH this action are the ones we generated
        # BEFORE this action (what we recommended for this action)
        recommendations = pending_recommendations

        # Build draft state up to this point (including this action)
        current_state = service.build_draft_state_at(
            session.draft_state,
            session.all_actions,
            session.current_index + 1,
        )

        # Generate recommendations for the NEXT action (to be sent with next action)
        pending_recommendations = None
        if current_state.next_team:
            pending_recommendations = service.get_recommendations(
                current_state,
                for_team=current_state.next_team,
            )

        # Log draft state
        logger.log_draft_state(
            action_count=session.current_index + 1,
            phase=current_state.current_phase.value,
            blue_picks=current_state.blue_picks,
            red_picks=current_state.red_picks,
            blue_bans=current_state.blue_bans,
            red_bans=current_state.red_bans,
        )

        # Log recommendations (if any)
        # Note: recommendations are what we recommended FOR this action (generated before it)
        # Use recommendations.for_team to get the correct team context
        if recommendations:
            rec_team = recommendations.for_team
            if recommendations.picks:
                our_team = current_state.blue_team if rec_team == "blue" else current_state.red_team
                our_picks = current_state.blue_picks if rec_team == "blue" else current_state.red_picks
                enemy_picks = current_state.red_picks if rec_team == "blue" else current_state.blue_picks
                logger.log_pick_recommendations(
                    action_count=session.current_index + 1,
                    phase=current_state.current_phase.value,
                    for_team=rec_team,
                    our_picks=our_picks,
                    enemy_picks=enemy_picks,
                    banned=current_state.blue_bans + current_state.red_bans,
                    team_players=[{"name": p.name, "role": p.role} for p in our_team.players],
                    candidates_count=len(recommendations.picks),
                    filled_roles=[],  # TODO: Get from pick engine
                    unfilled_roles=[],  # TODO: Get from pick engine
                    recommendations=[
                        {
                            "champion_name": p.champion_name,
                            "suggested_role": p.suggested_role,
                            "confidence": p.confidence,
                            "score": p.score,
                            "base_score": p.base_score,
                            "synergy_multiplier": p.synergy_multiplier,
                            "components": p.components,
                            "flag": p.flag,
                            "reasons": p.reasons,
                            "proficiency_source": p.proficiency_source,
                            "proficiency_player": p.proficiency_player,
                        }
                        for p in recommendations.picks
                    ],
                )
            elif recommendations.bans:
                enemy_team = current_state.red_team if rec_team == "blue" else current_state.blue_team
                our_picks = current_state.blue_picks if rec_team == "blue" else current_state.red_picks
                enemy_picks = current_state.red_picks if rec_team == "blue" else current_state.blue_picks
                logger.log_ban_recommendations(
                    action_count=session.current_index + 1,
                    phase=current_state.current_phase.value,
                    for_team=rec_team,
                    our_picks=our_picks,
                    enemy_picks=enemy_picks,
                    banned=current_state.blue_bans + current_state.red_bans,
                    enemy_players=[{"name": p.name, "role": p.role} for p in enemy_team.players],
                    recommendations=[
                        {
                            "champion_name": b.champion_name,
                            "priority": b.priority,
                            "target_player": b.target_player,
                            "reasons": b.reasons,
                            "components": b.components,
                        }
                        for b in recommendations.bans
                    ],
                )

        # Log the actual action that happened
        rec_list = []
        if recommendations:
            if recommendations.picks:
                rec_list = [{"champion_name": p.champion_name, "score": p.confidence} for p in recommendations.picks]
            elif recommendations.bans:
                rec_list = [{"champion_name": b.champion_name, "priority": b.priority} for b in recommendations.bans]
        logger.log_actual_action(
            action_count=session.current_index + 1,
            action_type=action.action_type,
            team=action.team_side,
            champion=action.champion_name,
            recommendations=rec_list,
        )

        # Send action + updated state + recommendations
        await websocket.send_json({
            "type": "draft_action",
            "action": {
                "sequence": action.sequence,
                "action_type": action.action_type,
                "team_side": action.team_side,
                "champion_name": action.champion_name,
                "champion_id": action.champion_id,
            },
            "draft_state": _serialize_draft_state(current_state),
            "recommendations": _serialize_recommendations(recommendations),
        })

        session.current_index += 1

        # Delay before next action (adjusted by speed)
        delay = session.delay_seconds / session.speed
        await asyncio.sleep(delay)

    # Draft complete
    session.status = ReplayStatus.COMPLETE

    # Build final state
    final_state = service.build_draft_state_at(
        session.draft_state,
        session.all_actions,
        len(session.all_actions),
    )

    await websocket.send_json({
        "type": "draft_complete",
        "draft_state": _serialize_draft_state(final_state),
        "blue_comp": final_state.blue_picks,
        "red_comp": final_state.red_picks,
    })


def _serialize_team(team: TeamContext) -> dict:
    """Serialize TeamContext to JSON-compatible dict."""
    return {
        "id": team.id,
        "name": team.name,
        "side": team.side,
        "players": [
            {"id": p.id, "name": p.name, "role": p.role}
            for p in team.players
        ],
    }


def _serialize_draft_state(state: DraftState) -> dict:
    """Serialize DraftState to JSON-compatible dict."""
    return {
        "phase": state.current_phase.value,
        "next_team": state.next_team,
        "next_action": state.next_action,
        "blue_bans": state.blue_bans,
        "red_bans": state.red_bans,
        "blue_picks": state.blue_picks,
        "red_picks": state.red_picks,
        "action_count": len(state.actions),
    }


def _serialize_recommendations(recs: Recommendations | None) -> dict | None:
    """Serialize Recommendations to JSON-compatible dict."""
    if not recs:
        return None

    result = {
        "for_team": recs.for_team,
        "picks": [
            {
                "champion_name": p.champion_name,
                "confidence": p.confidence,
                "suggested_role": p.suggested_role,
                "flag": p.flag,
                "reasons": p.reasons,
                "score": p.score,
                "base_score": p.base_score,
                "synergy_multiplier": p.synergy_multiplier,
                "components": p.components,
                "proficiency_source": p.proficiency_source,
                "proficiency_player": p.proficiency_player,
            }
            for p in recs.picks
        ],
        "bans": [
            {
                "champion_name": b.champion_name,
                "priority": b.priority,
                "target_player": b.target_player,
                "reasons": b.reasons,
                "components": b.components,
            }
            for b in recs.bans
        ],
    }

    # Add supplemental role_grouped view when picks are present
    if recs.picks:
        role_grouped = RoleGroupedRecommendations.from_picks(recs.picks, limit_per_role=2)
        result["role_grouped"] = role_grouped.to_dict()

    return result
