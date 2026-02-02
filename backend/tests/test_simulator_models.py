"""Tests for simulator models."""

import pytest


def test_simulator_session_tracks_recommended_picks():
    """SimulatorSession should have recommended_picks list."""
    from ban_teemo.models.simulator import SimulatorSession
    from ban_teemo.models.team import TeamContext, Player
    from ban_teemo.models.draft import DraftState, DraftPhase

    # Minimal setup
    players = [Player(id="p1", name="Player1", role="top")]
    team = TeamContext(id="t1", name="Team1", side="blue", players=players)
    draft = DraftState(
        game_id="g1",
        series_id="s1",
        game_number=1,
        patch_version="15.18",
        match_date=None,
        blue_team=team,
        red_team=team,
        actions=[],
        current_phase=DraftPhase.BAN_PHASE_1,
        next_team="blue",
        next_action="ban",
    )

    session = SimulatorSession(
        session_id="test",
        blue_team=team,
        red_team=team,
        coaching_side="blue",
        series_length=1,
        draft_mode="normal",
        draft_state=draft,
        enemy_strategy={"team_id": "t2", "team_name": "Enemy"},
    )

    assert hasattr(session, "recommended_picks")
    assert session.recommended_picks == []
