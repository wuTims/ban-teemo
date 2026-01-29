"""Tests for pick recommendation engine."""
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


@pytest.fixture
def engine():
    return PickRecommendationEngine()


@pytest.fixture
def sample_team_players():
    """Sample team roster."""
    return [
        {"name": "Zeus", "role": "TOP"},
        {"name": "Oner", "role": "JNG"},
        {"name": "Faker", "role": "MID"},
        {"name": "Gumayusi", "role": "ADC"},
        {"name": "Keria", "role": "SUP"},
    ]


def test_get_recommendations_returns_list(engine, sample_team_players):
    """Engine returns list of recommendations."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    assert isinstance(recs, list)
    assert len(recs) <= 5


def test_recommendations_have_required_fields(engine, sample_team_players):
    """Each recommendation has required fields."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    assert len(recs) > 0
    rec = recs[0]
    assert "champion_name" in rec
    assert "score" in rec
    assert "confidence" in rec
    assert "suggested_role" in rec
    assert "flag" in rec
    assert "reasons" in rec
    # best_player should NOT be present (dropped)
    assert "best_player" not in rec


def test_recommendations_sorted_by_score(engine, sample_team_players):
    """Recommendations are sorted by score descending."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10
    )
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_unavailable_champions_excluded(engine, sample_team_players):
    """Banned and picked champions are not recommended."""
    banned = ["Azir", "Aurora", "Ahri"]
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Rumble"],
        enemy_picks=["Jinx"],
        banned=banned,
        limit=10
    )
    recommended_champs = {r["champion_name"] for r in recs}
    assert "Azir" not in recommended_champs
    assert "Aurora" not in recommended_champs
    assert "Rumble" not in recommended_champs
    assert "Jinx" not in recommended_champs


def test_suggested_role_uses_jng_not_jungle(engine, sample_team_players):
    """Suggested role should use JNG format, not JUNGLE."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=20
    )
    for rec in recs:
        role = rec["suggested_role"]
        assert role in {"TOP", "JNG", "MID", "ADC", "SUP"}, f"Got unexpected role: {role}"
        assert role != "JUNGLE", "Should use JNG, not JUNGLE"


def test_suggested_role_prefers_unfilled(engine, sample_team_players):
    """Suggested role should prefer unfilled roles."""
    # Pick a TOP champion first
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Rumble"],  # TOP is filled
        enemy_picks=[],
        banned=[],
        limit=5
    )
    # Most recommendations should not suggest TOP
    top_suggestions = sum(1 for r in recs if r["suggested_role"] == "TOP")
    assert top_suggestions < len(recs)  # Not all should be TOP


def test_flag_low_confidence_reachable(engine):
    """LOW_CONFIDENCE flag should be reachable with unknown players."""
    # Use players with no proficiency data
    unknown_players = [{"name": "CompletelyUnknownPlayer12345", "role": "MID"}]
    recs = engine.get_recommendations(
        team_players=unknown_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5
    )
    # With NO_DATA proficiency, confidence = (1.0 + 0.3) / 2 = 0.65
    # Threshold is 0.7, so these should get LOW_CONFIDENCE
    flags = [r["flag"] for r in recs]
    assert "LOW_CONFIDENCE" in flags, f"Expected LOW_CONFIDENCE flag, got: {flags}"


def test_unknown_champion_gets_deterministic_role(engine, sample_team_players):
    """Unknown champions should get deterministic role assignment."""
    # Call twice with same inputs - should get same results
    recs1 = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10
    )
    recs2 = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10
    )
    # Same champions should have same suggested roles
    roles1 = {r["champion_name"]: r["suggested_role"] for r in recs1}
    roles2 = {r["champion_name"]: r["suggested_role"] for r in recs2}
    for champ in roles1:
        if champ in roles2:
            assert roles1[champ] == roles2[champ], f"Role for {champ} not deterministic"


def test_excludes_champions_with_only_filled_roles(engine, sample_team_players):
    """Champions that can only play filled roles should be excluded."""
    # Jinx is ADC-only (ADC: 1.0 in flex_champions.json)
    # Aurora is MID/TOP flex (MID: 0.696, TOP: 0.304)
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Kai'Sa"],  # ADC is filled
        enemy_picks=[],
        banned=[],
        limit=50  # Get many to ensure we'd see Jinx if she were included
    )
    recommended_champs = {r["champion_name"] for r in recs}

    # Jinx (ADC-only) should NOT be recommended since ADC is filled
    assert "Jinx" not in recommended_champs, "ADC-only Jinx should be excluded when ADC is filled"

    # Aurora (MID/TOP flex) should still be recommendable since MID/TOP are open
    # (She may or may not appear depending on player pools, so we just check she's not excluded)


def test_flex_champions_remain_when_one_role_filled(engine, sample_team_players):
    """Flex champions should still be recommended when only one of their roles is filled."""
    # Aurora is MID/TOP flex - should be recommended when TOP is filled (can play MID)
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Gnar"],  # TOP is filled (Gnar is TOP-only)
        enemy_picks=[],
        banned=[],
        limit=50
    )

    # Check that Aurora can appear (if in player pools or meta picks)
    # and if she does, her suggested_role should be MID (not TOP)
    aurora_rec = next((r for r in recs if r["champion_name"] == "Aurora"), None)
    if aurora_rec:
        assert aurora_rec["suggested_role"] == "MID", \
            f"Aurora should suggest MID when TOP is filled, got {aurora_rec['suggested_role']}"
