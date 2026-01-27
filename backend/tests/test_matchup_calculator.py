"""Tests for matchup calculation."""
import pytest
from ban_teemo.services.scorers.matchup_calculator import MatchupCalculator


@pytest.fixture
def calculator():
    return MatchupCalculator()


def test_get_lane_matchup_direct(calculator):
    """Test lane matchup with direct data lookup."""
    result = calculator.get_lane_matchup("Maokai", "Sejuani", "JUNGLE")
    assert 0.0 <= result["score"] <= 1.0
    assert result["confidence"] in ["HIGH", "MEDIUM", "LOW", "NO_DATA"]


def test_get_team_matchup(calculator):
    """Test team-level matchup."""
    result = calculator.get_team_matchup("Maokai", "Sejuani")
    assert 0.0 <= result["score"] <= 1.0


def test_matchup_unknown_returns_neutral(calculator):
    """Unknown matchup returns 0.5."""
    result = calculator.get_lane_matchup("FakeChamp1", "FakeChamp2", "MID")
    assert result["score"] == 0.5
    assert result["confidence"] == "NO_DATA"
