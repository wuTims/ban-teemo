"""WebSocket handler for draft replay streaming."""

import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from ban_teemo.models.draft import DraftPhase, DraftState
from ban_teemo.models.recommendations import Recommendations
from ban_teemo.models.team import TeamContext
from ban_teemo.services.draft_service import DraftService
from ban_teemo.services.replay_manager import ReplayManager, ReplaySession, ReplayStatus


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

    try:
        # Send initial state
        await websocket.send_json({
            "type": "session_start",
            "session_id": session_id,
            "blue_team": _serialize_team(session.draft_state.blue_team),
            "red_team": _serialize_team(session.draft_state.red_team),
            "total_actions": len(session.all_actions),
            "patch": session.draft_state.patch_version,
        })

        # Start the replay loop
        session.status = ReplayStatus.PLAYING
        await _run_replay_loop(session, service, websocket)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Send error before closing
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass
    finally:
        session.websocket = None
        manager.remove_session(session_id)


async def _run_replay_loop(
    session: ReplaySession,
    service: DraftService,
    websocket: WebSocket,
):
    """Main replay loop - sends actions with delays.

    Args:
        session: The replay session
        service: DraftService for building state and recommendations
        websocket: WebSocket to send messages on
    """
    while session.current_index < len(session.all_actions):
        if session.status == ReplayStatus.PAUSED:
            await asyncio.sleep(0.1)
            continue

        # Get current action
        action = session.all_actions[session.current_index]

        # Build draft state up to this point (including this action)
        current_state = service.build_draft_state_at(
            session.draft_state,
            session.all_actions,
            session.current_index + 1,
        )

        # Get recommendations for next move (if draft not complete)
        recommendations = None
        if current_state.next_team:
            recommendations = service.get_recommendations(
                current_state,
                for_team=current_state.next_team,
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
    return {
        "for_team": recs.for_team,
        "picks": [
            {
                "champion_name": p.champion_name,
                "confidence": p.confidence,
                "flag": p.flag,
                "reasons": p.reasons,
            }
            for p in recs.picks
        ],
        "bans": [
            {
                "champion_name": b.champion_name,
                "priority": b.priority,
                "target_player": b.target_player,
                "reasons": b.reasons,
            }
            for b in recs.bans
        ],
    }
