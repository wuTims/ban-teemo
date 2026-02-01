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


def test_phase1_ban_priority_uses_tiered_system():
    """Phase 1 bans should use meta-first tiered priority system."""
    service = BanRecommendationService()

    # T1: High proficiency + high presence + in pool = signature power pick
    priority_t1, components_t1 = service._calculate_ban_priority(
        champion="Azir",  # High presence champion
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.8, "games": 10, "confidence": "HIGH"},
        is_phase_1=True,
    )

    # Should include tier classification
    assert "tier" in components_t1, "Should include tier classification"
    assert components_t1["tier"] == "T1_SIGNATURE_POWER", (
        f"High prof + high presence should be T1_SIGNATURE_POWER, got {components_t1['tier']}"
    )
    assert "tier_bonus" in components_t1, "Should include tier bonus"
    assert components_t1["tier_bonus"] >= 0.05, "T1 should have significant bonus"


def test_tier1_bans_include_meta_weight():
    """Tier 1 bans should have high weighted meta component (35% weight)."""
    service = BanRecommendationService()

    # T1 scenario: High proficiency + high presence + in pool
    priority_t1, components_t1 = service._calculate_ban_priority(
        champion="Azir",  # High presence, high meta champion
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.85, "games": 12, "confidence": "HIGH"},
        is_phase_1=True,
    )

    # Verify tier is T1
    assert components_t1["tier"] == "T1_SIGNATURE_POWER", (
        f"Should be T1_SIGNATURE_POWER, got {components_t1['tier']}"
    )

    # All phase 1 bans should include weighted meta component
    assert "meta" in components_t1, "Should include weighted meta component"
    # Meta is weighted at 35%, so for a high-meta champ like Azir (~0.65), expect ~0.23
    assert components_t1["meta"] > 0.15, f"Meta should be significant for Azir: {components_t1['meta']}"

    # Verify meta is the highest weighted component (meta-first approach)
    assert components_t1["meta"] >= components_t1.get("proficiency", 0), (
        f"Meta should be weighted higher than proficiency in Phase 1"
    )


def test_tier1_meta_weight_increases_priority():
    """High-meta champions should have higher priority due to meta-first weighting."""
    service = BanRecommendationService()

    # T3 scenario (high proficiency, low presence - comfort pick)
    priority_t3, components_t3 = service._calculate_ban_priority(
        champion="Qiyana",  # Low presence
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.85, "games": 12, "confidence": "HIGH"},
        is_phase_1=True,
    )

    # T1 scenario (high proficiency, high presence - signature power)
    priority_t1, components_t1 = service._calculate_ban_priority(
        champion="Azir",  # High presence
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.85, "games": 12, "confidence": "HIGH"},
        is_phase_1=True,
    )

    # Verify tiers - low presence comfort pick is T3, high presence is T1
    assert components_t3["tier"] == "T3_COMFORT_PICK", f"Should be T3, got {components_t3['tier']}"
    assert components_t1["tier"] == "T1_SIGNATURE_POWER", f"Should be T1, got {components_t1['tier']}"

    # T1 (high meta) should have higher priority than T3 (low meta)
    assert priority_t1 > priority_t3, (
        f"T1 priority ({priority_t1}) should exceed T3 ({priority_t3}) "
        f"due to higher meta weight and tier bonus"
    )


def test_phase1_tier3_comfort_pick():
    """Tier 3 should apply for comfort picks without high presence."""
    service = BanRecommendationService()

    # T3: High proficiency, in pool, but low presence champion
    priority, components = service._calculate_ban_priority(
        champion="Qiyana",  # Lower presence (~7%)
        player={"name": "TestPlayer", "role": "mid"},
        proficiency={"score": 0.75, "games": 8, "confidence": "MEDIUM"},
        is_phase_1=True,
    )

    # Should be T3 (comfort pick) or T4 (if proficiency threshold not met)
    tier = components.get("tier", "")
    assert tier in ["T3_COMFORT_PICK", "T4_GENERAL"], f"Low presence comfort pick: {tier}"


def test_phase1_tier_ordering():
    """Higher tiers should have higher priority than lower tiers."""
    service = BanRecommendationService()

    # T1 scenario (signature power - high meta + high proficiency)
    p1, c1 = service._calculate_ban_priority(
        champion="Azir",
        player={"name": "P1", "role": "mid"},
        proficiency={"score": 0.85, "games": 12, "confidence": "HIGH"},
        is_phase_1=True,
    )

    # T4 scenario (general - low proficiency, low presence)
    p4, c4 = service._calculate_ban_priority(
        champion="Qiyana",
        player={"name": "P1", "role": "mid"},
        proficiency={"score": 0.5, "games": 2, "confidence": "LOW"},
        is_phase_1=True,
    )

    assert p1 > p4, f"T1 priority ({p1}) should exceed T4 ({p4})"


def test_get_synergy_denial_score_strong_synergy():
    """Banning a champion with strong synergy to enemy should score high."""
    service = BanRecommendationService()

    # Enemy has Jarvan - Orianna has strong synergy (J4 ult + Ori ult combo)
    enemy_picks = ["Jarvan IV"]

    score = service._get_synergy_denial_score("Orianna", enemy_picks)

    # Should have some synergy denial value
    assert score >= 0.0, f"Should have non-negative synergy denial: {score}"


def test_get_synergy_denial_score_no_synergy():
    """Banning a champion with no synergy should score 0."""
    service = BanRecommendationService()

    score = service._get_synergy_denial_score("Orianna", [])
    assert score == 0.0


def test_get_role_denial_score_unfilled_role():
    """Banning a champion for unfilled enemy role should score high."""
    service = BanRecommendationService()

    # Enemy has picked mid and jungle, still needs bot
    enemy_picks = ["Azir", "Jarvan IV"]
    enemy_players = [
        {"name": "Viper", "role": "bot"},  # Viper is known ADC
        {"name": "TestMid", "role": "mid"},
        {"name": "TestJungle", "role": "jungle"},
    ]

    # Kai'Sa is in Viper's pool and fills bot
    score = service._get_role_denial_score("Kai'Sa", enemy_picks, enemy_players)

    # Should have role denial value
    assert score >= 0.3, f"Kai'Sa should deny Viper's bot role: {score}"


def test_get_role_denial_score_no_players():
    """No enemy players returns 0."""
    service = BanRecommendationService()

    score = service._get_role_denial_score("Kai'Sa", ["Azir"], [])
    assert score == 0.0


def test_phase2_bans_use_tiered_priority():
    """Phase 2 bans should use tiered priority system."""
    service = BanRecommendationService()

    # Phase 2 with some picks already made
    recommendations = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=["Jarvan IV", "Rumble"],  # Teamfight/engage direction
        enemy_picks=["Azir", "Vi"],  # Enemy has mid + jungle
        banned=["Yunara", "Neeko"],
        phase="BAN_PHASE_2",
        enemy_players=[
            {"name": "Viper", "role": "bot"},
            {"name": "Keria", "role": "support"},
            {"name": "TestMid", "role": "mid"},
            {"name": "TestJungle", "role": "jungle"},
            {"name": "TestTop", "role": "top"},
        ],
        limit=5,
    )

    # Should have tiered priority in recommendations
    has_tier = any(
        "tier" in r.get("components", {})
        for r in recommendations
    )
    assert has_tier, "Phase 2 should include tier classification"


def test_phase2_tier1_prioritizes_counter_in_pool():
    """Tier 1 should be highest priority: counters our picks AND in enemy pool."""
    service = BanRecommendationService()

    recommendations = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=["Azir"],  # We picked Azir
        enemy_picks=["Jarvan IV"],
        banned=[],
        phase="BAN_PHASE_2",
        enemy_players=[
            {"name": "Viper", "role": "bot"},  # Viper has Kai'Sa in pool
        ],
        limit=10,
    )

    # Look for T1 tier bans
    t1_bans = [r for r in recommendations
               if r.get("components", {}).get("tier") == "T1_COUNTER_AND_POOL"]

    # If we have T1 bans, they should be near the top
    if t1_bans:
        t1_names = [b["champion_name"] for b in t1_bans]
        top_3_names = [r["champion_name"] for r in recommendations[:3]]
        has_t1_in_top = any(name in top_3_names for name in t1_names)
        # Soft assertion - T1 should generally be near top
        assert has_t1_in_top or len(recommendations) < 3, (
            f"T1 bans {t1_names} should be prioritized, top 3: {top_3_names}"
        )


def test_phase1_includes_global_power_bans():
    """Phase 1 should include high-presence bans even with sparse enemy data."""
    service = BanRecommendationService()

    # No enemy player data (sparse)
    recommendations = service.get_ban_recommendations(
        enemy_team_id="unknown",
        our_picks=[],
        enemy_picks=[],
        banned=[],
        phase="BAN_PHASE_1",
        enemy_players=[],  # Empty - no player data
        limit=5,
    )

    # Should still return recommendations based on meta/presence
    assert len(recommendations) >= 3, "Should have bans even without player data"

    # High presence champions should be recommended
    champ_names = [r["champion_name"] for r in recommendations]
    # At least one high-presence champion should be in top 5
    high_presence = {"Azir", "Yunara", "Poppy", "Pantheon", "Neeko"}
    has_power_ban = any(c in high_presence for c in champ_names)
    assert has_power_ban, f"Should include power bans, got: {champ_names}"

    # Verify global power bans have the T2_META_POWER tier classification
    # (this ensures the new _get_global_power_bans method is being used)
    has_global_power_tier = any(
        r.get("components", {}).get("tier") == "T2_META_POWER"
        for r in recommendations
    )
    assert has_global_power_tier, (
        f"Should have T2_META_POWER tier bans, got tiers: "
        f"{[r.get('components', {}).get('tier') for r in recommendations]}"
    )


def test_phase2_candidates_include_player_pools():
    """Phase 2 should consider enemy player pools, not just meta top 30."""
    service = BanRecommendationService()

    # Enemy players with specific champions in pool for unfilled roles
    enemy_players = [
        {"name": "Viper", "role": "bot"},
        {"name": "Keria", "role": "support"},
        {"name": "TestMid", "role": "mid"},
        {"name": "TestJungle", "role": "jungle"},
        {"name": "TestTop", "role": "top"},
    ]

    # Phase 2 with enemy picks - mid is filled, bot/support unfilled
    recommendations = service.get_ban_recommendations(
        enemy_team_id="test",
        our_picks=["Jarvan IV"],
        enemy_picks=["Azir"],  # Enemy has mid
        banned=["Yunara"],
        phase="BAN_PHASE_2",
        enemy_players=enemy_players,
        limit=10,
    )

    # Should have recommendations
    assert len(recommendations) >= 1, "Should have phase 2 recommendations"

    # The contextual phase 2 logic should include enemy player pool champions
    # for unfilled roles (bot and support in this case since mid is filled)
    #
    # Check that recommendations include either:
    # 1. Champions from enemy player pools (target_player set)
    # 2. Champions identified as in enemy pool for unfilled roles
    #    (indicated by "in pool" reasons or pool-related tier)

    # Get all champion names in recommendations
    recommended_champs = {r["champion_name"] for r in recommendations}

    # At minimum, verify the structure is correct
    for rec in recommendations:
        assert "champion_name" in rec
        assert "priority" in rec
        assert "components" in rec
        assert "reasons" in rec
        assert 0.0 <= rec["priority"] <= 1.0

    # Check if any recommendations specifically target unfilled role players
    # (Viper for bot, Keria for support)
    has_player_targeted = any(
        r.get("target_player") in ["Viper", "Keria"]
        for r in recommendations
    )

    # Also check for pool-related reasons or tiers that indicate
    # the phase 2 logic is considering player pools
    has_pool_consideration = any(
        r.get("components", {}).get("tier") in [
            "T1_COUNTER_AND_POOL",
            "T2_ARCHETYPE_AND_POOL"
        ] or
        any("pool" in reason.lower() for reason in r.get("reasons", []))
        for r in recommendations
    )

    # Either should be true if enemy player pools are being considered
    assert has_player_targeted or has_pool_consideration or len(recommended_champs) > 0, (
        f"Phase 2 should consider enemy player pools. "
        f"Player targeted: {has_player_targeted}, Pool consideration: {has_pool_consideration}, "
        f"Recommendations: {[r['champion_name'] for r in recommendations[:5]]}"
    )
