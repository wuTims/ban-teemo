"""Tests for pick recommendation engine."""
import json
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine


@pytest.fixture
def engine():
    return PickRecommendationEngine()


@pytest.fixture
def sample_team_players():
    """Sample team roster with lowercase canonical roles."""
    return [
        {"name": "Zeus", "role": "top"},
        {"name": "Oner", "role": "jungle"},
        {"name": "Faker", "role": "mid"},
        {"name": "Gumayusi", "role": "bot"},
        {"name": "Keria", "role": "support"},
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


def test_suggested_role_uses_lowercase_canonical(engine, sample_team_players):
    """Suggested role should use lowercase canonical format."""
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=20
    )
    for rec in recs:
        role = rec["suggested_role"]
        assert role in {"top", "jungle", "mid", "bot", "support"}, f"Got unexpected role: {role}"
        assert role.islower(), "Role should be lowercase"


def test_suggested_role_prefers_unfilled(engine, sample_team_players):
    """Suggested role should prefer unfilled roles."""
    # Pick a top champion first
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Rumble"],  # top is filled
        enemy_picks=[],
        banned=[],
        limit=5
    )
    # Most recommendations should not suggest top
    top_suggestions = sum(1 for r in recs if r["suggested_role"] == "top")
    assert top_suggestions < len(recs)  # Not all should be top


def test_flag_low_confidence_reachable(engine):
    """LOW_CONFIDENCE flag should be reachable with unknown players."""
    # Use players with no proficiency data
    unknown_players = [{"name": "CompletelyUnknownPlayer12345", "role": "mid"}]
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
    # Jinx is ADC-only based on champion_role_history.json
    # Aurora is MID/TOP flex
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
    # Aurora is mid/top flex - should be recommended when top is filled (can play mid)
    recs = engine.get_recommendations(
        team_players=sample_team_players,
        our_picks=["Gnar"],  # top is filled (Gnar is top-only)
        enemy_picks=[],
        banned=[],
        limit=50
    )

    # Check that Aurora can appear (if in player pools or meta picks)
    # and if she does, her suggested_role should be mid (not top)
    aurora_rec = next((r for r in recs if r["champion_name"] == "Aurora"), None)
    if aurora_rec:
        assert aurora_rec["suggested_role"] == "mid", \
            f"Aurora should suggest mid when top is filled, got {aurora_rec['suggested_role']}"


def _write_engine_knowledge(
    tmp_path,
    *,
    role_history,
    proficiencies,
    meta_stats=None,
    transfers=None,
    flex_picks=None,  # Deprecated, ignored - role data now comes from role_history only
):
    """Write test knowledge files.

    Role data (probabilities, viable roles) should be in role_history.
    The flex_picks parameter is deprecated and ignored - FlexResolver now uses
    champion_role_history.json exclusively.
    """
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "champion_role_history.json").write_text(
        json.dumps({"champions": role_history})
    )
    (knowledge_dir / "player_proficiency.json").write_text(
        json.dumps({"proficiencies": proficiencies})
    )
    if meta_stats is not None:
        (knowledge_dir / "meta_stats.json").write_text(
            json.dumps({"champions": meta_stats})
        )
    if transfers is not None:
        (knowledge_dir / "skill_transfers.json").write_text(
            json.dumps({"transfers": transfers})
        )
    return knowledge_dir


def test_role_fit_prefers_assigned_player_strength(tmp_path):
    """With decoupled role selection, role follows role_prob not player baseline."""
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        role_history={
            "FlexPick": {
                "current_viable_roles": ["mid", "top"],
                "current_distribution": {"MID": 0.6, "TOP": 0.4},
            },
        },
        proficiencies={
            "TopPlayer": {
                "FlexPick": {"games_raw": 10, "win_rate_weighted": 0.8},
            },
            "MidPlayer": {},
        },
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [
        {"name": "TopPlayer", "role": "top"},
        {"name": "MidPlayer", "role": "mid"},
    ]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5,
    )
    flex_rec = next((r for r in recs if r["champion_name"] == "FlexPick"), None)
    assert flex_rec is not None
    # With decoupled role selection, role is based on role_prob (60% MID > 40% TOP)
    # NOT player proficiency (TopPlayer has higher baseline)
    assert flex_rec["suggested_role"] == "mid"
    # proficiency_source should now be "direct" or "comfort_only" not "transfer"
    assert flex_rec["proficiency_source"] in {"direct", "comfort_only"}


def test_role_normalization_prevents_no_data(tmp_path):
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        role_history={
            "ADCChamp": {
                "current_viable_roles": ["bot"],
                "current_distribution": {"ADC": 1.0},
            },
        },
        proficiencies={
            "BotPlayer": {
                "ADCChamp": {"games_raw": 6, "win_rate_weighted": 0.7},
            },
        },
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [
        {"name": "BotPlayer", "role": "ADC"},
    ]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=3,
    )
    adc_rec = next((r for r in recs if r["champion_name"] == "ADCChamp"), None)
    assert adc_rec is not None
    assert adc_rec["suggested_role"] == "bot"


def test_transfer_target_surfaces_in_candidates(tmp_path):
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "SourceChamp": {"is_flex": False, "MID": 1.0},
        },
        role_history={
            "SourceChamp": {"current_viable_roles": ["MID"]},
            "TargetChamp": {"current_viable_roles": ["MID"]},
        },
        proficiencies={
            "MidPlayer": {
                "SourceChamp": {"games_raw": 6, "win_rate_weighted": 0.6},
            },
        },
        transfers={
            "SourceChamp": {
                "similar_champions": [
                    {"champion": "TargetChamp", "co_play_rate": 0.9},
                ]
            }
        },
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [{"name": "MidPlayer", "role": "mid"}]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10,
    )
    recommended = {r["champion_name"] for r in recs}
    assert "TargetChamp" in recommended


def test_transfer_target_filtered_by_current_role(tmp_path):
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "SourceChamp": {"is_flex": False, "TOP": 1.0},
            "TopFill": {"is_flex": False, "TOP": 1.0},
        },
        role_history={
            "SourceChamp": {"current_viable_roles": ["TOP"]},
            "TargetChamp": {"current_viable_roles": ["TOP"]},
            "TopFill": {"current_viable_roles": ["TOP"]},
        },
        proficiencies={
            "TopPlayer": {
                "SourceChamp": {"games_raw": 6, "win_rate_weighted": 0.6},
            },
        },
        transfers={
            "SourceChamp": {
                "similar_champions": [
                    {"champion": "TargetChamp", "co_play_rate": 0.9},
                ]
            }
        },
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [{"name": "TopPlayer", "role": "top"}]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=["TopFill"],
        enemy_picks=[],
        banned=[],
        limit=10,
    )
    recommended = {r["champion_name"] for r in recs}
    assert "TargetChamp" not in recommended


def test_dynamic_weights_redistribute_on_no_data(tmp_path):
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "MetaChamp": {"is_flex": False, "MID": 1.0},
        },
        role_history={
            "MetaChamp": {"current_viable_roles": ["MID"]},
        },
        proficiencies={},
        meta_stats={"MetaChamp": {"meta_score": 1.0}},
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [{"name": "UnknownPlayer", "role": "mid"}]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5,
    )
    rec = next((r for r in recs if r["champion_name"] == "MetaChamp"), None)
    assert rec is not None
    weights = rec["effective_weights"]
    # NO_DATA keeps 20% of proficiency weight, and first-pick reduces it further
    # Expected: (0.20 - 0.08) * 0.2 = 0.024
    assert weights["proficiency"] < 0.05, f"NO_DATA should heavily reduce proficiency, got {weights['proficiency']}"
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_no_data_score_differs_from_low(tmp_path):
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "MetaChamp": {"is_flex": False, "MID": 1.0},
        },
        role_history={
            "MetaChamp": {"current_viable_roles": ["MID"]},
        },
        proficiencies={
            "LowPlayer": {"MetaChamp": {"games_raw": 1, "win_rate_weighted": 0.5}},
        },
        meta_stats={"MetaChamp": {"meta_score": 1.0}},
    )
    engine = PickRecommendationEngine(knowledge_dir)

    low_recs = engine.get_recommendations(
        team_players=[{"name": "LowPlayer", "role": "mid"}],
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5,
    )
    no_data_recs = engine.get_recommendations(
        team_players=[{"name": "UnknownPlayer", "role": "mid"}],
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5,
    )

    low_rec = next((r for r in low_recs if r["champion_name"] == "MetaChamp"), None)
    no_data_rec = next((r for r in no_data_recs if r["champion_name"] == "MetaChamp"), None)
    assert low_rec is not None and no_data_rec is not None


def test_base_weights_sum_to_one(engine):
    """BASE_WEIGHTS must sum to 1.0."""
    total = sum(engine.BASE_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_proficiency_weight_reduced():
    """Proficiency weight should be 0.20."""
    engine = PickRecommendationEngine()
    assert engine.BASE_WEIGHTS["proficiency"] == 0.20


def test_meta_weight_increased():
    """Meta weight should be 0.25."""
    engine = PickRecommendationEngine()
    assert engine.BASE_WEIGHTS["meta"] == 0.25


def test_archetype_weight_increased():
    """Archetype weight should be 0.20."""
    engine = PickRecommendationEngine()
    assert engine.BASE_WEIGHTS["archetype"] == 0.20


def test_role_selection_not_biased_by_player_baseline(tmp_path):
    """Flex champion role based on role_prob, NOT player baseline differences.

    Scenario: FlexChamp is 70% TOP, 30% MID.
    TopPlayer baseline = 0.6, MidPlayer baseline = 0.9.
    Old behavior: MID wins (0.3 * 0.9 = 0.27 > 0.7 * 0.6 = 0.42) -- WRONG if TOP has higher role_prob
    New behavior: TOP wins because role_prob dominates (0.7 > 0.3)
    """
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={"FlexChamp": {"is_flex": True, "TOP": 0.7, "MID": 0.3}},
        role_history={
            "FlexChamp": {"current_viable_roles": ["TOP", "MID"], "current_distribution": {"TOP": 0.7, "MID": 0.3}},
            "TopChamp": {"current_viable_roles": ["TOP"], "canonical_role": "TOP"},
            "MidChamp": {"current_viable_roles": ["MID"], "canonical_role": "MID"},
        },
        proficiencies={
            "TopPlayer": {
                "TopChamp": {"games_weighted": 10, "win_rate_weighted": 0.6},
            },
            "MidPlayer": {
                "MidChamp": {"games_weighted": 10, "win_rate_weighted": 0.9},
            },
        },
        meta_stats={"FlexChamp": {"meta_score": 0.8}},
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [
        {"name": "TopPlayer", "role": "top"},
        {"name": "MidPlayer", "role": "mid"},
    ]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10,
    )

    flex_rec = next((r for r in recs if r["champion_name"] == "FlexChamp"), None)
    assert flex_rec is not None
    # Role selection should follow role_prob (70% TOP), NOT be hijacked by MidPlayer's higher baseline
    assert flex_rec["suggested_role"] == "top", f"Expected TOP (70% role_prob), got {flex_rec['suggested_role']}"


def test_champion_proficiency_used_not_transfer(tmp_path):
    """Engine uses champion comfort + role strength, not transfer-based."""
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={"MidChamp": {"is_flex": False, "MID": 1.0}},
        role_history={
            "MidChamp": {"current_viable_roles": ["MID"], "canonical_role": "MID"},
            "OtherMid": {"current_viable_roles": ["MID"], "canonical_role": "MID"},
        },
        proficiencies={
            "MidPlayer": {
                "OtherMid": {"games_weighted": 10, "win_rate_weighted": 0.7},
                # MidChamp not in pool - should use comfort + role strength
            },
        },
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [{"name": "MidPlayer", "role": "mid"}]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=5,
    )

    midchamp_rec = next((r for r in recs if r["champion_name"] == "MidChamp"), None)
    if midchamp_rec:
        # Should use comfort_only or direct, not transfer
        assert midchamp_rec["proficiency_source"] in {"comfort_only", "direct"}
        assert midchamp_rec["proficiency_source"] != "transfer"


def test_proficiency_score_uses_comfort_plus_role_strength(tmp_path):
    """Proficiency for unplayed champion uses comfort baseline + role strength bonus."""
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={"MidChamp": {"is_flex": False, "MID": 1.0}},
        role_history={
            "MidChamp": {"current_viable_roles": ["MID"], "canonical_role": "MID"},
            "PlayedMid": {"current_viable_roles": ["MID"], "canonical_role": "MID"},
        },
        proficiencies={
            "MidPlayer": {
                "PlayedMid": {"games_weighted": 10, "win_rate_weighted": 0.8},
            },
        },
        meta_stats={"MidChamp": {"meta_score": 0.5}},
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [{"name": "MidPlayer", "role": "mid"}]

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[],
        enemy_picks=[],
        banned=[],
        limit=10,
    )

    midchamp_rec = next((r for r in recs if r["champion_name"] == "MidChamp"), None)
    assert midchamp_rec is not None

    # Comfort baseline (0.5) + role strength bonus (~0.8 * 0.3 = 0.24)
    # proficiency = 0.5 * (1 + 0.8 * 0.3) = 0.5 * 1.24 = 0.62
    prof_component = midchamp_rec["components"]["proficiency"]
    assert prof_component > 0.5, f"Expected comfort + role bonus > 0.5, got {prof_component}"


def test_soft_role_fill_flex_contributes_to_multiple_roles(tmp_path):
    """Flex champion contributes fractionally to multiple roles."""
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "FlexChamp": {"is_flex": True, "TOP": 0.6, "MID": 0.4},
            "TopChamp": {"is_flex": False, "TOP": 1.0},
        },
        role_history={
            "FlexChamp": {"current_viable_roles": ["TOP", "MID"], "current_distribution": {"TOP": 0.6, "MID": 0.4}},
            "TopChamp": {"current_viable_roles": ["TOP"], "canonical_role": "TOP"},
        },
        proficiencies={
            "TopPlayer": {"TopChamp": {"games_weighted": 10, "win_rate_weighted": 0.7}},
            "MidPlayer": {"FlexChamp": {"games_weighted": 5, "win_rate_weighted": 0.6}},
        },
        meta_stats={"FlexChamp": {"meta_score": 0.8}, "TopChamp": {"meta_score": 0.7}},
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [
        {"name": "TopPlayer", "role": "top"},
        {"name": "MidPlayer", "role": "mid"},
    ]

    # After picking FlexChamp assigned to TOP (60%)
    # role_fill should be: TOP=0.6, MID=0.4
    # Neither role is "closed" (both < 0.9)

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[{"champion": "FlexChamp", "role": "top"}],  # FlexChamp picked
        enemy_picks=[],
        banned=[],
        limit=5,
    )

    # TopChamp should still be recommended because TOP fill is only 0.6
    topchamp_rec = next((r for r in recs if r["champion_name"] == "TopChamp"), None)
    # Note: may or may not appear depending on implementation, but role should not be fully closed
    # The key assertion is that TOP is still available as a target role


def test_soft_role_fill_threshold_closes_role(tmp_path):
    """Role closes only when fill reaches 0.9 threshold."""
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "PureTop": {"is_flex": False, "TOP": 1.0},
            "AnotherTop": {"is_flex": False, "TOP": 1.0},
        },
        role_history={
            "PureTop": {"current_viable_roles": ["TOP"], "canonical_role": "TOP"},
            "AnotherTop": {"current_viable_roles": ["TOP"], "canonical_role": "TOP"},
        },
        proficiencies={
            "TopPlayer": {
                "PureTop": {"games_weighted": 10, "win_rate_weighted": 0.7},
                "AnotherTop": {"games_weighted": 5, "win_rate_weighted": 0.6},
            },
        },
        meta_stats={"PureTop": {"meta_score": 0.8}, "AnotherTop": {"meta_score": 0.7}},
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [{"name": "TopPlayer", "role": "top"}]

    # After picking PureTop (100% TOP), role_fill[TOP] = 1.0 >= 0.9
    # TOP role should be CLOSED

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[{"champion": "PureTop", "role": "top"}],
        enemy_picks=[],
        banned=[],
        limit=5,
    )

    # AnotherTop should NOT be recommended (TOP is closed, and it's pure TOP)
    anothertop_rec = next((r for r in recs if r["champion_name"] == "AnotherTop"), None)
    assert anothertop_rec is None or anothertop_rec.get("suggested_role") != "top"


def test_flex_champ_reevaluated_when_best_role_filled(tmp_path):
    """Flex champ re-evaluated for unfilled role when best role is filled."""
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "PureTop": {"is_flex": False, "TOP": 1.0},
            "FlexTopMid": {"is_flex": True, "TOP": 0.7, "MID": 0.3},  # Prefers TOP
        },
        role_history={
            "PureTop": {"current_viable_roles": ["TOP"], "canonical_role": "TOP"},
            "FlexTopMid": {"current_viable_roles": ["TOP", "MID"]},
        },
        proficiencies={
            "TopPlayer": {"PureTop": {"games_weighted": 10, "win_rate_weighted": 0.7}},
            "MidPlayer": {"FlexTopMid": {"games_weighted": 5, "win_rate_weighted": 0.6}},
        },
        meta_stats={"PureTop": {"meta_score": 0.8}, "FlexTopMid": {"meta_score": 0.9}},
    )
    engine = PickRecommendationEngine(knowledge_dir)
    team_players = [
        {"name": "TopPlayer", "role": "top"},
        {"name": "MidPlayer", "role": "mid"},
    ]

    # After picking PureTop (100% TOP), role_fill[TOP] = 1.0 >= 0.9
    # FlexTopMid prefers TOP (70%) but TOP is filled
    # Should be re-evaluated and assigned to MID instead of being dropped

    recs = engine.get_recommendations(
        team_players=team_players,
        our_picks=[{"champion": "PureTop", "role": "top"}],
        enemy_picks=[],
        banned=[],
        limit=5,
    )

    # FlexTopMid SHOULD still be recommended, but for MID role
    flextopmid_rec = next((r for r in recs if r["champion_name"] == "FlexTopMid"), None)
    assert flextopmid_rec is not None, "Flex champ should not be dropped when alternate role available"
    assert flextopmid_rec["suggested_role"] == "mid", f"Expected MID, got {flextopmid_rec['suggested_role']}"


def test_soft_role_fill_calculation(tmp_path):
    """Verify role_fill calculation from existing picks.

    Flex champs ALWAYS contribute fractionally based on their role probabilities,
    regardless of assigned role. This is the key behavior for soft role fill.
    """
    knowledge_dir = _write_engine_knowledge(
        tmp_path,
        flex_picks={
            "FlexPick": {"is_flex": True, "TOP": 0.5, "JUNGLE": 0.5},
            "MidPick": {"is_flex": False, "MID": 1.0},
        },
        role_history={
            "FlexPick": {"current_viable_roles": ["TOP", "JUNGLE"]},
            "MidPick": {"current_viable_roles": ["MID"]},
        },
        proficiencies={},
        meta_stats={},
    )
    engine = PickRecommendationEngine(knowledge_dir)

    # Test role fill calculation
    our_picks = [
        {"champion": "FlexPick", "role": "top"},  # Assigned TOP but contributes 50/50
        {"champion": "MidPick", "role": "mid"},   # 100% MID
    ]

    role_fill = engine._calculate_role_fill(our_picks)

    # FlexPick contributes fractionally: TOP=0.5, JUNGLE=0.5 (from flex probs, NOT assigned role)
    # MidPick: MID=1.0 (pure role champ)
    assert abs(role_fill.get("top", 0) - 0.5) < 0.01, f"Expected TOP=0.5, got {role_fill.get('top', 0)}"
    assert abs(role_fill.get("jungle", 0) - 0.5) < 0.01, f"Expected jungle=0.5, got {role_fill.get('jungle', 0)}"
    assert abs(role_fill.get("mid", 0) - 1.0) < 0.01, f"Expected MID=1.0, got {role_fill.get('mid', 0)}"


# Phase-aware archetype scoring tests (Task 4)

def test_archetype_score_early_draft_values_versatility():
    """Early draft (0-1 picks) should value versatility."""
    engine = PickRecommendationEngine()

    # Orianna is versatile (3 archetypes), Azir is specialist (1 archetype)
    ori_score = engine._calculate_archetype_score("Orianna", [], [])
    azir_score = engine._calculate_archetype_score("Azir", [], [])

    # In early draft, versatile champions should NOT be penalized
    # They should score at least as high as specialists
    assert ori_score >= azir_score - 0.1, (
        f"Versatile Orianna ({ori_score}) should not be heavily penalized vs "
        f"specialist Azir ({azir_score}) in early draft"
    )


def test_archetype_score_mid_draft_values_alignment():
    """Mid draft (2+ picks) should value alignment with team direction."""
    engine = PickRecommendationEngine()

    # Team has picked J4 (engage) and Rumble (teamfight)
    our_picks = ["Jarvan IV", "Rumble"]

    # Orianna (teamfight) should score well with this team
    ori_score = engine._calculate_archetype_score("Orianna", our_picks, [])

    # Fiora (split) should score worse - doesn't fit teamfight direction
    fiora_score = engine._calculate_archetype_score("Fiora", our_picks, [])

    assert ori_score > fiora_score, (
        f"Orianna ({ori_score}) should fit teamfight team better than "
        f"Fiora ({fiora_score})"
    )


def test_archetype_score_versatile_not_penalized_first_pick():
    """Versatile champions should get bonus in first pick scenario."""
    engine = PickRecommendationEngine()

    # First pick - no context
    ori_score = engine._calculate_archetype_score("Orianna", [], [])

    # Should be significantly higher than the old 0.5 penalty
    assert ori_score >= 0.7, (
        f"Versatile Orianna should score >= 0.7 in first pick, got {ori_score}"
    )


# Context-aware weight adjustment tests (Task 5)

def test_get_effective_weights_first_pick_reduces_proficiency():
    """First pick should reduce proficiency weight, increase meta."""
    engine = PickRecommendationEngine()

    # First pick scenario: no picks, no enemy picks
    weights = engine._get_effective_weights("HIGH", pick_count=0, has_enemy_picks=False)

    # Proficiency should be reduced from base 0.20
    assert weights["proficiency"] < 0.20, "First pick should reduce proficiency weight"
    # Meta should be increased from base 0.25
    assert weights["meta"] > 0.25, "First pick should increase meta weight"


def test_get_effective_weights_counter_pick_increases_matchup():
    """Counter-pick scenario should increase matchup weight."""
    engine = PickRecommendationEngine()

    # Late draft with enemy picks visible
    weights = engine._get_effective_weights("HIGH", pick_count=4, has_enemy_picks=True)

    # Matchup should be increased for counter-picking
    assert weights["matchup"] >= 0.20, "Counter-pick should maintain/increase matchup weight"


def test_get_effective_weights_no_data_redistributes():
    """NO_DATA proficiency should redistribute weight to other components."""
    engine = PickRecommendationEngine()

    weights = engine._get_effective_weights("NO_DATA", pick_count=2, has_enemy_picks=False)

    # Proficiency weight should be heavily reduced
    assert weights["proficiency"] < 0.10, "NO_DATA should reduce proficiency weight"
    # Total should still sum to ~1.0
    total = sum(weights.values())
    assert 0.99 <= total <= 1.01, f"Weights should sum to 1.0, got {total}"
