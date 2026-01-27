"""Tests for player proficiency scoring."""
import pytest
from ban_teemo.services.scorers.proficiency_scorer import ProficiencyScorer


@pytest.fixture
def scorer():
    return ProficiencyScorer()


def test_get_proficiency_score_known_player(scorer):
    """Test proficiency for known player."""
    score, confidence = scorer.get_proficiency_score("Faker", "Azir")
    assert 0.0 <= score <= 1.0
    assert confidence in ["HIGH", "MEDIUM", "LOW", "NO_DATA"]


def test_get_proficiency_unknown_player(scorer):
    """Unknown player returns neutral score."""
    score, confidence = scorer.get_proficiency_score("UnknownPlayer123", "Azir")
    assert score == 0.5
    assert confidence == "NO_DATA"


def test_get_player_champion_pool(scorer):
    """Test getting player's champion pool."""
    pool = scorer.get_player_champion_pool("Faker", min_games=1)
    assert isinstance(pool, list)
    if pool:
        assert "champion" in pool[0]
        assert "score" in pool[0]
