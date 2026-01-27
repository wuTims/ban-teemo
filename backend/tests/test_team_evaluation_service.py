"""Tests for team evaluation service."""
import pytest
from ban_teemo.services.team_evaluation_service import TeamEvaluationService


@pytest.fixture
def service():
    return TeamEvaluationService()


def test_evaluate_team_draft(service):
    """Test evaluating a team's draft."""
    result = service.evaluate_team_draft(["Malphite", "Orianna", "Jarvan IV"])
    assert "archetype" in result
    assert "synergy_score" in result
    assert "composition_score" in result
    assert "strengths" in result
    assert "weaknesses" in result


def test_evaluate_vs_enemy(service):
    """Test head-to-head evaluation."""
    result = service.evaluate_vs_enemy(
        our_picks=["Malphite", "Orianna"],
        enemy_picks=["Fiora", "Camille"]
    )
    assert "our_evaluation" in result
    assert "enemy_evaluation" in result
    assert "matchup_advantage" in result


def test_empty_picks(service):
    """Empty picks returns neutral evaluation."""
    result = service.evaluate_team_draft([])
    assert result["composition_score"] == 0.5
