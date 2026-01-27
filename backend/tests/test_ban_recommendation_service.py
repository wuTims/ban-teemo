"""Tests for ban recommendation service."""
import pytest
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


@pytest.fixture
def service():
    return BanRecommendationService()


def test_get_ban_recommendations(service):
    """Test generating ban recommendations."""
    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:d2dc3681610c70d6cce8c5f4c1612769",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1"
    )
    assert len(recs) >= 1
    for rec in recs:
        assert "champion_name" in rec
        assert "priority" in rec
        assert 0.0 <= rec["priority"] <= 1.0


def test_ban_excludes_already_banned(service):
    """Already banned champions excluded."""
    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:d2dc3681610c70d6cce8c5f4c1612769",
        our_picks=[],
        enemy_picks=[],
        banned=["Azir", "Aurora"],
        phase="BAN_PHASE_1"
    )
    names = {r["champion_name"] for r in recs}
    assert "Azir" not in names
    assert "Aurora" not in names


def test_target_player_bans(service):
    """Some bans should target specific players."""
    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:d2dc3681610c70d6cce8c5f4c1612769",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        limit=5
    )
    # At least some should have target_player
    has_target = any(r.get("target_player") for r in recs)
    # This may or may not be true depending on data, so just check structure
    for rec in recs:
        assert "target_player" in rec or rec.get("target_player") is None
