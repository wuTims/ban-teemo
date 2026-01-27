"""Tests for pick recommendation engine."""
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


@pytest.fixture
def engine():
    return PickRecommendationEngine()


def test_get_recommendations(engine):
    """Test generating pick recommendations."""
    recs = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    assert len(recs) <= 5
    for rec in recs:
        assert "champion_name" in rec
        assert "score" in rec
        assert 0.0 <= rec["score"] <= 1.5


def test_recommendations_exclude_unavailable(engine):
    """Banned/picked champions excluded."""
    recs = engine.get_recommendations(
        player_name="Faker",
        player_role="MID",
        our_picks=["Orianna"],
        enemy_picks=["Azir"],
        banned=["Aurora"],
        limit=10
    )
    names = {r["champion_name"] for r in recs}
    assert "Orianna" not in names
    assert "Azir" not in names
    assert "Aurora" not in names
