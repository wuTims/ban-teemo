"""Tests for enemy simulator service."""

import pytest
from unittest.mock import MagicMock, patch

from ban_teemo.services.enemy_simulator_service import EnemySimulatorService
from ban_teemo.models.draft import DraftAction


@pytest.fixture
def mock_repository():
    """Mock DraftRepository for testing."""
    repo = MagicMock()

    # Mock get_team_games to return sample game data
    repo.get_team_games.return_value = [
        {
            "game_id": "game1",
            "series_id": "series1",
            "game_number": 1,
            "match_date": "2025-01-01",
            "team_side": "blue",
            "opponent_team_id": "opponent1",
            "opponent_team_name": "Opponent Team",
            "winner_team_id": "oe:team:test",
            "blue_team_id": "oe:team:test",
        },
        {
            "game_id": "game2",
            "series_id": "series2",
            "game_number": 1,
            "match_date": "2025-01-02",
            "team_side": "red",
            "opponent_team_id": "opponent2",
            "opponent_team_name": "Another Team",
            "winner_team_id": "opponent2",
            "blue_team_id": "opponent2",
        },
    ]

    # Mock get_draft_actions - return DraftAction objects
    def mock_draft_actions(game_id):
        if game_id == "game1":
            return [
                DraftAction(sequence=1, action_type="ban", team_side="blue", champion_id="azir", champion_name="Azir"),
                DraftAction(sequence=2, action_type="ban", team_side="red", champion_id="aurora", champion_name="Aurora"),
                DraftAction(sequence=3, action_type="ban", team_side="blue", champion_id="corki", champion_name="Corki"),
                DraftAction(sequence=7, action_type="pick", team_side="blue", champion_id="kaisa", champion_name="Kai'Sa"),
                DraftAction(sequence=8, action_type="pick", team_side="red", champion_id="jinx", champion_name="Jinx"),
            ]
        elif game_id == "game2":
            return [
                DraftAction(sequence=1, action_type="ban", team_side="red", champion_id="leblanc", champion_name="LeBlanc"),
                DraftAction(sequence=7, action_type="pick", team_side="red", champion_id="varus", champion_name="Varus"),
            ]
        return []

    repo.get_draft_actions.side_effect = mock_draft_actions
    return repo


@pytest.fixture
def service(mock_repository):
    """Create service with mocked repository."""
    svc = EnemySimulatorService.__new__(EnemySimulatorService)
    svc.repo = mock_repository
    return svc


def test_initialize_enemy_strategy(service, mock_repository):
    """Test initializing enemy strategy for a team."""
    strategy = service.initialize_enemy_strategy("oe:team:test")

    assert strategy is not None
    assert strategy.reference_game_id in ["game1", "game2"]
    assert len(strategy.fallback_game_ids) >= 0
    # Champion weights should be built from picks
    assert len(strategy.champion_weights) > 0


def test_generate_action_from_script(service, mock_repository):
    """Test generating action from reference script."""
    # Force game1 as reference for deterministic test
    with patch("random.choice", return_value=mock_repository.get_team_games.return_value[0]):
        strategy = service.initialize_enemy_strategy("oe:team:test")

    champion, source = service.generate_action(strategy, sequence=1, unavailable=set())
    assert champion is not None
    assert source in ["reference_game", "fallback_game", "weighted_random"]


def test_generate_action_with_unavailable(service, mock_repository):
    """Test fallback when scripted champion unavailable."""
    # Force game1 as reference
    with patch("random.choice", return_value=mock_repository.get_team_games.return_value[0]):
        strategy = service.initialize_enemy_strategy("oe:team:test")

    # Make all scripted champions unavailable
    all_scripted = {a.champion_name for a in strategy.draft_script}

    # Should still return something (from weights or fallback)
    champion, source = service.generate_action(strategy, sequence=1, unavailable=all_scripted)
    assert champion not in all_scripted
    assert source in ["fallback_game", "weighted_random"]


def test_build_champion_weights(service, mock_repository):
    """Test that champion weights are built correctly."""
    games = mock_repository.get_team_games.return_value
    weights = service._build_champion_weights("oe:team:test", games)

    # Should have weights for picked champions
    assert len(weights) > 0
    # Weights should sum close to 1.0
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_no_games_raises_error(service, mock_repository):
    """Should raise error when no games found."""
    mock_repository.get_team_games.return_value = []

    with pytest.raises(ValueError, match="No games found"):
        service.initialize_enemy_strategy("oe:team:unknown")
