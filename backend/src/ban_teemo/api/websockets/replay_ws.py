"""WebSocket handler for draft replay streaming."""

import asyncio
import json
import logging
import traceback
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from ban_teemo.models.draft import DraftPhase, DraftState
from ban_teemo.models.recommendations import Recommendations, RoleGroupedRecommendations
from ban_teemo.models.team import TeamContext
from ban_teemo.services.draft_service import DraftService
from ban_teemo.services.llm_reranker import LLMReranker, RerankerResult
from ban_teemo.services.replay_manager import ReplayManager, ReplaySession, ReplayStatus
from ban_teemo.services.scoring_logger import ScoringLogger
from ban_teemo.services.scorers.flex_resolver import FlexResolver

logger = logging.getLogger(__name__)


async def _handle_client_messages(
    websocket: WebSocket,
    session: ReplaySession,
) -> None:
    """Listen for client commands (pause/resume) in a separate task."""
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "pause":
                    if session.status == ReplayStatus.PLAYING:
                        session.status = ReplayStatus.PAUSED
                        await websocket.send_json({"type": "paused"})
                        logger.info(f"Session {session.id} paused")

                elif msg_type == "resume":
                    if session.status == ReplayStatus.PAUSED:
                        session.status = ReplayStatus.PLAYING
                        await websocket.send_json({"type": "resumed"})
                        logger.info(f"Session {session.id} resumed")

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in client message handler: {e}")


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
        service: DraftService instance (default service, may be overridden per-session)
    """
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    session.websocket = websocket

    # Create session-specific service with tournament data file for historical accuracy
    if session.tournament_data_file:
        service = DraftService(
            database_path=service.database_path,
            tournament_data_file=session.tournament_data_file,
        )

    # Start client message handler for pause/resume commands
    client_handler_task = asyncio.create_task(
        _handle_client_messages(websocket, session)
    )

    # Create LLM reranker if enabled
    llm_reranker: Optional[LLMReranker] = None
    if session.llm_enabled and session.llm_api_key:
        llm_reranker = LLMReranker(api_key=session.llm_api_key)
        logger.info(f"LLM reranker enabled for session {session_id}")

    # Initialize diagnostic logger for this replay
    scoring_logger = ScoringLogger()
    scoring_logger.start_session(
        session_id=session_id,
        mode="replay",
        blue_team=session.draft_state.blue_team.name,
        red_team=session.draft_state.red_team.name,
        series_id=session.draft_state.series_id,
        game_number=session.draft_state.game_number,
        extra_metadata={
            "patch": session.draft_state.patch_version,
            "total_actions": len(session.all_actions),
            "llm_enabled": session.llm_enabled,
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
        await _run_replay_loop(session, service, websocket, scoring_logger, llm_reranker)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Log the full error with traceback
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        scoring_logger.log_error(error_msg)
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
        # Cancel client message handler
        client_handler_task.cancel()
        try:
            await client_handler_task
        except asyncio.CancelledError:
            pass
        # Clean up LLM reranker
        if llm_reranker:
            await llm_reranker.close()
        # Save diagnostic logs
        scoring_logger.save()
        session.websocket = None
        manager.remove_session(session_id)


async def _run_replay_loop(
    session: ReplaySession,
    service: DraftService,
    websocket: WebSocket,
    scoring_logger: ScoringLogger,
    llm_reranker: Optional[LLMReranker] = None,
):
    """Main replay loop - sends actions with delays.

    Args:
        session: The replay session
        service: DraftService for building state and recommendations
        websocket: WebSocket to send messages on
        scoring_logger: ScoringLogger for diagnostic capture
        llm_reranker: Optional LLM reranker for enhanced recommendations
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
        scoring_logger.log_draft_state(
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
                scoring_logger.log_pick_recommendations(
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
                scoring_logger.log_ban_recommendations(
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
        scoring_logger.log_actual_action(
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

        # LLM enhancement - blocking or fire-and-forget based on session settings
        # Note: recommendations exist even for the last action (phase COMPLETE)
        has_recs = bool(recommendations and (recommendations.picks or recommendations.bans))
        if llm_reranker and has_recs and _should_run_llm(current_state.current_phase, has_recs):
            action_count = session.current_index + 1
            if session.wait_for_llm:
                # Send waiting notification
                await websocket.send_json({
                    "type": "waiting_for_llm",
                    "action_count": action_count,
                })
                # Await LLM with timeout
                try:
                    await asyncio.wait_for(
                        _enhance_and_send(
                            websocket=websocket,
                            reranker=llm_reranker,
                            recommendations=recommendations,
                            draft_state=current_state,
                            action_count=action_count,
                        ),
                        timeout=session.llm_timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"LLM timed out for action {action_count}")
                    await websocket.send_json({
                        "type": "llm_timeout",
                        "action_count": action_count,
                    })
            else:
                # Fire-and-forget mode
                asyncio.create_task(
                    _enhance_and_send(
                        websocket=websocket,
                        reranker=llm_reranker,
                        recommendations=recommendations,
                        draft_state=current_state,
                        action_count=action_count,
                    )
                )

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

    # Finalize role assignments for both teams
    flex_resolver = FlexResolver()
    blue_with_roles = flex_resolver.finalize_role_assignments(final_state.blue_picks)
    red_with_roles = flex_resolver.finalize_role_assignments(final_state.red_picks)

    await websocket.send_json({
        "type": "draft_complete",
        "draft_state": _serialize_draft_state(final_state),
        "blue_comp": final_state.blue_picks,
        "red_comp": final_state.red_picks,
        "blue_comp_with_roles": blue_with_roles,
        "red_comp_with_roles": red_with_roles,
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


def _should_run_llm(phase: DraftPhase, has_recommendations: bool = True) -> bool:
    """Check if LLM should run for this action.

    Runs for all phases when enabled. For the last action, the phase will be
    COMPLETE but we still want to show insights if recommendations were generated.
    """
    # Always run if there are recommendations to analyze
    # The phase check is now secondary - we run even for COMPLETE phase
    # as long as there are recommendations (which means it's the final pick)
    return has_recommendations


async def _enhance_and_send(
    websocket: WebSocket,
    reranker: LLMReranker,
    recommendations: Recommendations,
    draft_state: DraftState,
    action_count: int,
) -> None:
    """Run LLM reranking and send enhanced_recommendations message.

    This is a fire-and-forget task - errors are logged but don't affect the replay.
    """
    try:
        for_team = recommendations.for_team
        our_team = draft_state.blue_team if for_team == "blue" else draft_state.red_team
        enemy_team = draft_state.red_team if for_team == "blue" else draft_state.blue_team
        our_picks = draft_state.blue_picks if for_team == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if for_team == "blue" else draft_state.blue_picks

        # Build draft context for LLM
        draft_context = {
            "phase": draft_state.current_phase.value,
            "patch": draft_state.patch_version,
            "our_team": our_team.name,
            "enemy_team": enemy_team.name,
            "our_picks": our_picks,
            "enemy_picks": enemy_picks,
            "banned": draft_state.blue_bans + draft_state.red_bans,
        }

        team_players = [{"name": p.name, "role": p.role} for p in our_team.players]
        enemy_players = [{"name": p.name, "role": p.role} for p in enemy_team.players]

        # Call appropriate rerank method based on action type
        result: RerankerResult
        if recommendations.picks:
            candidates = [
                {
                    "champion_name": p.champion_name,
                    "score": p.score or p.confidence,
                    "suggested_role": p.suggested_role,
                    "components": p.components or {},
                    "reasons": p.reasons,
                    "proficiency_player": p.proficiency_player,
                }
                for p in recommendations.picks[:15]
            ]
            result = await reranker.rerank_picks(
                candidates=candidates,
                draft_context=draft_context,
                team_players=team_players,
                enemy_players=enemy_players,
                limit=5,
            )
        elif recommendations.bans:
            candidates = [
                {
                    "champion_name": b.champion_name,
                    "priority": b.priority,
                    "target_player": b.target_player,
                    "components": b.components or {},
                    "reasons": b.reasons,
                }
                for b in recommendations.bans[:15]
            ]
            result = await reranker.rerank_bans(
                candidates=candidates,
                draft_context=draft_context,
                our_players=team_players,
                enemy_players=enemy_players,
                limit=5,
            )
        else:
            return  # No recommendations to enhance

        # Build and send enhanced_recommendations message
        await websocket.send_json({
            "type": "enhanced_recommendations",
            "action_count": action_count,
            "for_team": for_team,
            "draft_analysis": result.draft_analysis,
            "reranked": [
                {
                    "champion_name": r.champion,
                    "original_rank": r.original_rank,
                    "new_rank": r.new_rank,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "strategic_factors": r.strategic_factors,
                }
                for r in result.reranked
            ],
            "additional_suggestions": [
                {
                    "champion_name": s.champion,
                    "reasoning": s.reasoning,
                    "confidence": s.confidence,
                    "role": s.role,
                }
                for s in result.additional_suggestions
            ],
        })

        logger.info(f"Sent enhanced recommendations for action {action_count}")

    except Exception as e:
        logger.error(f"LLM enhancement failed for action {action_count}: {e}")
        # Don't re-raise - this is fire-and-forget
