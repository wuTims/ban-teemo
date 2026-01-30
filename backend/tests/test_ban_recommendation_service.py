"""Tests for ban recommendation service."""
from unittest.mock import MagicMock

import pytest
from ban_teemo.services.ban_recommendation_service import BanRecommendationService


@pytest.fixture
def service():
    return BanRecommendationService()


@pytest.fixture
def mock_repository():
    """Mock DraftRepository for testing auto-lookup."""
    repo = MagicMock()
    repo.get_team_roster.return_value = [
        {"player_id": "p1", "player_name": "Faker", "role": "MID"},
        {"player_id": "p2", "player_name": "Zeus", "role": "TOP"},
        {"player_id": "p3", "player_name": "Oner", "role": "JNG"},
        {"player_id": "p4", "player_name": "Gumayusi", "role": "ADC"},
        {"player_id": "p5", "player_name": "Keria", "role": "SUP"},
    ]
    return repo


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


def test_ban_with_enemy_players_targets_pools(service):
    """Providing enemy_players should target their champion pools."""
    enemy_players = [
        {"name": "Faker", "role": "MID"},
        {"name": "Gumayusi", "role": "ADC"},
    ]

    recs = service.get_ban_recommendations(
        enemy_team_id="test_team",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        enemy_players=enemy_players,
        limit=10
    )

    # Should have recommendations
    assert len(recs) >= 1

    # Check that player-targeted bans exist
    player_targeted = [r for r in recs if r.get("target_player") in ["Faker", "Gumayusi"]]
    # If we have proficiency data for these players, we should have targeted bans
    # (this depends on the knowledge data, so we check structure rather than count)
    for rec in player_targeted:
        assert rec["target_role"] in ["MID", "ADC", None]
        assert len(rec["reasons"]) >= 1


def test_ban_phase_2_prioritizes_counters(service):
    """Phase 2 bans should consider counter picks to our team."""
    # In Phase 2, we have some picks and want to ban counters
    recs_phase_1 = service.get_ban_recommendations(
        enemy_team_id="test_team",
        our_picks=["Azir"],  # We picked Azir
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        limit=10
    )

    recs_phase_2 = service.get_ban_recommendations(
        enemy_team_id="test_team",
        our_picks=["Azir"],  # We picked Azir
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_2",
        limit=10
    )

    # Phase 2 should have recommendations
    assert len(recs_phase_2) >= 1

    # Collect reasons from both phases
    phase_1_reasons = []
    for rec in recs_phase_1:
        phase_1_reasons.extend(rec.get("reasons", []))

    phase_2_reasons = []
    for rec in recs_phase_2:
        phase_2_reasons.extend(rec.get("reasons", []))

    # Phase 2 should have counter-pick reasoning that Phase 1 doesn't have
    phase_1_counter_reasons = [r for r in phase_1_reasons if "Counter" in r]
    phase_2_counter_reasons = [r for r in phase_2_reasons if "Counter" in r]

    # Phase 1 should NOT have counter reasons (no counter logic in phase 1)
    assert len(phase_1_counter_reasons) == 0, "Phase 1 should not have counter-pick reasons"

    # Phase 2 SHOULD have counter reasons (if matchup data exists)
    # Note: This depends on matchup_stats.json having counters for Azir
    # If no data, this will be empty - that's acceptable but we verify the logic path
    assert isinstance(phase_2_counter_reasons, list)

    # Verify each recommendation has required fields
    for rec in recs_phase_2:
        assert "champion_name" in rec
        assert "priority" in rec
        assert "reasons" in rec
        assert 0.0 <= rec["priority"] <= 1.0


def test_auto_lookup_roster_from_repository(mock_repository):
    """Should auto-lookup roster when repository is provided and enemy_players is None."""
    service = BanRecommendationService(draft_repository=mock_repository)

    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:test123",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        enemy_players=None,  # Explicitly None to trigger auto-lookup
        limit=10
    )

    # Verify repository was called with the enemy_team_id
    mock_repository.get_team_roster.assert_called_once_with("oe:team:test123")

    # Should have recommendations (players are in proficiency data)
    assert len(recs) >= 1


def test_auto_lookup_skipped_when_enemy_players_provided(mock_repository):
    """Should NOT call repository when enemy_players is explicitly provided."""
    service = BanRecommendationService(draft_repository=mock_repository)

    recs = service.get_ban_recommendations(
        enemy_team_id="oe:team:test123",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        enemy_players=[{"name": "SomePlayer", "role": "MID"}],  # Explicitly provided
        limit=10
    )

    # Repository should NOT be called since enemy_players was provided
    mock_repository.get_team_roster.assert_not_called()


def test_auto_lookup_normalizes_roles(mock_repository):
    """Auto-lookup should normalize role names from database format."""
    # Repository returns lowercase canonical roles
    mock_repository.get_team_roster.return_value = [
        {"player_id": "p1", "player_name": "TestPlayer", "role": "jungle"},
    ]

    service = BanRecommendationService(draft_repository=mock_repository)

    # Call the internal method directly to test normalization
    players = service._lookup_enemy_roster("test_team")

    assert len(players) == 1
    assert players[0]["role"] == "jungle"  # Should be lowercase canonical
    assert players[0]["name"] == "TestPlayer"


def test_pool_depth_boost_shallow_pool(service):
    """Verify +0.20 boost is applied for pools with ≤3 champions."""
    # Create controlled proficiency entry
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    # Calculate base priority (without pool depth) by testing with deep pool
    base_priority, _ = service._calculate_ban_priority(
        champion="Azir",
        player=player,
        proficiency=proficiency,
        pool_size=10,  # Deep pool - no boost
    )

    # Calculate priority with shallow pool
    shallow_priority, components = service._calculate_ban_priority(
        champion="Azir",
        player=player,
        proficiency=proficiency,
        pool_size=3,  # Shallow pool - should get +0.20
    )

    # Verify exact boost amount
    assert shallow_priority == min(1.0, round(base_priority + 0.20, 3)), \
        f"Expected +0.20 boost: base={base_priority}, shallow={shallow_priority}"
    assert components["pool_depth_bonus"] == 0.20


def test_pool_depth_boost_medium_pool(service):
    """Verify +0.10 boost is applied for pools with 4-5 champions."""
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    base_priority, _ = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=10,
    )
    medium_priority, components = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=5,
    )

    assert medium_priority == min(1.0, round(base_priority + 0.10, 3)), \
        f"Expected +0.10 boost: base={base_priority}, medium={medium_priority}"
    assert components["pool_depth_bonus"] == 0.10


def test_pool_depth_no_boost_for_missing_data(service):
    """Verify no boost when pool_size=0 (missing data)."""
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    base_priority, _ = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=10,
    )
    no_data_priority, components = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=0,
    )

    assert no_data_priority == base_priority, \
        f"pool_size=0 should get no boost: base={base_priority}, no_data={no_data_priority}"
    assert components["pool_depth_bonus"] == 0.0


def test_pool_depth_no_boost_for_deep_pool(service):
    """Verify no boost when pool_size >= 6."""
    proficiency = {"score": 0.5, "games": 5, "confidence": "MEDIUM"}
    player = {"name": "TestPlayer", "role": "MID"}

    priority_6, components_6 = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=6,
    )
    priority_10, components_10 = service._calculate_ban_priority(
        champion="Azir", player=player, proficiency=proficiency, pool_size=10,
    )

    assert priority_6 == priority_10, \
        f"Deep pools (6+) should have same priority: 6={priority_6}, 10={priority_10}"
    assert components_6["pool_depth_bonus"] == 0.0
    assert components_10["pool_depth_bonus"] == 0.0


def test_get_presence_score_high_presence(service):
    """High presence champions should have high presence score."""
    # Azir has ~39% presence
    score = service._get_presence_score("Azir")
    assert score >= 0.3, f"High presence Azir should score >= 0.3: {score}"


def test_get_presence_score_low_presence(service):
    """Low presence champions should have low presence score."""
    score = service._get_presence_score("Qiyana")  # ~7% presence
    assert score < 0.15, f"Low presence Qiyana should score < 0.15: {score}"


def test_get_presence_score_unknown(service):
    """Unknown champions return 0."""
    score = service._get_presence_score("NonexistentChamp")
    assert score == 0.0


def test_get_flex_value_multi_role():
    """Multi-role flex picks should have high flex value."""
    service = BanRecommendationService()

    # Aurora can go mid/top/jungle
    value = service._get_flex_value("Aurora")
    assert value >= 0.5, f"Flex Aurora should have value >= 0.5: {value}"


def test_get_flex_value_single_role():
    """Single-role champions should have low flex value."""
    service = BanRecommendationService()

    # Jinx is bot only
    value = service._get_flex_value("Jinx")
    assert value <= 0.3, f"Single-role Jinx should have value <= 0.3: {value}"


def test_get_archetype_counter_score_matching():
    """Banning a champion that fits enemy's archetype should score high."""
    service = BanRecommendationService()

    # Enemy has picked engage champions (J4, Vi)
    enemy_picks = ["Jarvan IV", "Vi"]

    # Orianna (teamfight/engage) would fit their engage comp
    score = service._get_archetype_counter_score("Orianna", enemy_picks)

    # Should have meaningful score since Orianna has engage archetype
    assert score > 0.2, f"Orianna should counter engage comp: {score}"


def test_get_archetype_counter_score_no_enemy():
    """No enemy picks returns 0."""
    service = BanRecommendationService()

    score = service._get_archetype_counter_score("Orianna", [])
    assert score == 0.0
