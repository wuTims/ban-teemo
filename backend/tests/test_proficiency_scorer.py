"""Tests for player proficiency scoring."""
import json
import pytest
from ban_teemo.services.scorers.proficiency_scorer import ProficiencyScorer


@pytest.fixture
def scorer():
    return ProficiencyScorer()


def _write_proficiency_data(tmp_path, proficiencies, role_history=None):
    """Helper to create test knowledge files."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)
    (knowledge_dir / "player_proficiency.json").write_text(
        json.dumps({"proficiencies": proficiencies})
    )
    if role_history:
        (knowledge_dir / "champion_role_history.json").write_text(
            json.dumps({"champions": role_history})
        )
    # Create empty skill_transfers.json to avoid load errors
    (knowledge_dir / "skill_transfers.json").write_text(
        json.dumps({"transfers": {}})
    )
    return knowledge_dir


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


# ======================================================================
# Role Strength Calculation Tests
# ======================================================================


def test_calculate_role_strength_weighted_average(tmp_path):
    """Role strength is weighted average of player's role champions (win_rate based)."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "MidPlayer": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.7},
                "Syndra": {"games_weighted": 5, "win_rate_weighted": 0.6},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
            "Syndra": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    strength = scorer.calculate_role_strength("MidPlayer", "mid")

    # Expected strength uses win_rate only:
    # (0.7*10 + 0.6*5) / (10 + 5) = 0.667
    assert strength is not None
    assert 0.64 <= strength <= 0.7


def test_calculate_role_strength_no_role_data(tmp_path):
    """Returns None when player has no champions in role."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "TopPlayer": {
                "Aatrox": {"games_weighted": 12, "win_rate_weighted": 0.7},
            },
        },
        role_history={
            "Aatrox": {"canonical_role": "TOP"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    # TopPlayer has no mid champions
    strength = scorer.calculate_role_strength("TopPlayer", "mid")
    assert strength is None


def test_calculate_role_strength_unknown_player(tmp_path):
    """Returns None for unknown player."""
    knowledge_dir = _write_proficiency_data(tmp_path, proficiencies={})
    scorer = ProficiencyScorer(knowledge_dir)
    strength = scorer.calculate_role_strength("UnknownPlayer", "mid")
    assert strength is None


def test_calculate_role_strength_filters_by_role(tmp_path):
    """Only includes champions that match the requested role."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "FlexPlayer": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.8},
                "Aatrox": {"games_weighted": 12, "win_rate_weighted": 0.5},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
            "Aatrox": {"canonical_role": "TOP"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)

    mid_strength = scorer.calculate_role_strength("FlexPlayer", "mid")
    top_strength = scorer.calculate_role_strength("FlexPlayer", "top")

    # Mid strength should only use Azir (high win rate)
    # Top strength should only use Aatrox (low win rate)
    assert mid_strength is not None
    assert top_strength is not None
    assert mid_strength > top_strength


def test_calculate_role_strength_uses_win_rate_only(tmp_path):
    """Verify strength changes with win_rate, not double-counted by games."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "PlayerA": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.8},
            },
            "PlayerB": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.5},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)

    strength_a = scorer.calculate_role_strength("PlayerA", "mid")
    strength_b = scorer.calculate_role_strength("PlayerB", "mid")

    # Same games, different win_rate -> different strength
    assert strength_a > strength_b
    assert abs(strength_a - 0.8) < 0.01
    assert abs(strength_b - 0.5) < 0.01


# ======================================================================
# Champion Proficiency (Comfort + Role Strength) Tests
# ======================================================================


def test_get_champion_proficiency_comfort_scales_with_games(tmp_path):
    """Champion comfort scales from 0.5 baseline based on games played."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "MidPlayer": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.7},
                "Syndra": {"games_weighted": 8, "win_rate_weighted": 0.65},
                "Viktor": {"games_weighted": 2, "win_rate_weighted": 0.5},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
            "Syndra": {"canonical_role": "MID"},
            "Viktor": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    team_players = [{"name": "MidPlayer", "role": "mid"}]

    # Azir: 12 games (>= G_FULL=10) -> full comfort scaling
    azir_score, azir_conf, _, _ = scorer.get_champion_proficiency(
        "Azir", "mid", team_players
    )

    # Viktor: 2 games -> partial comfort scaling
    viktor_score, viktor_conf, _, _ = scorer.get_champion_proficiency(
        "Viktor", "mid", team_players
    )

    assert azir_score > viktor_score
    assert azir_conf == "HIGH"
    assert viktor_conf == "LOW"


def test_get_champion_proficiency_unplayed_uses_comfort_baseline(tmp_path):
    """Unplayed champion starts at 0.5 comfort baseline with role strength bonus."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "MidPlayer": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.7},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
            "Syndra": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    team_players = [{"name": "MidPlayer", "role": "mid"}]

    # Syndra: no games -> 0.5 comfort + role strength bonus
    syndra_score, syndra_conf, player, source = scorer.get_champion_proficiency(
        "Syndra", "mid", team_players
    )

    # With role_strength ~0.7 and ROLE_STRENGTH_BONUS=0.3:
    # comfort = 0.5, proficiency = 0.5 * (1 + 0.7 * 0.3) = 0.5 * 1.21 = 0.605
    assert syndra_score > 0.5  # Should have role strength bonus
    assert syndra_score < 0.7  # But not too high without games
    assert syndra_conf == "LOW"
    assert player == "MidPlayer"
    assert source == "comfort_only"


def test_get_champion_proficiency_no_role_strength_comfort_only(tmp_path):
    """Player with no role data gets comfort-only score (no role bonus), still capped."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "TopPlayer": {
                "Aatrox": {"games_weighted": 12, "win_rate_weighted": 0.7},
            },
        },
        role_history={
            "Aatrox": {"canonical_role": "TOP"},
            "Azir": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    # TopPlayer is assigned mid but has no mid data (no role strength)
    team_players = [{"name": "TopPlayer", "role": "mid"}]

    score, conf, player, source = scorer.get_champion_proficiency(
        "Azir", "mid", team_players
    )

    # Comfort baseline only (0.5), no role strength bonus, no games on Azir
    assert score == 0.5
    assert conf == "LOW"
    assert source == "comfort_only"


def test_get_champion_proficiency_comfort_only_capped(tmp_path):
    """Comfort-only score is still capped at PROFICIENCY_CAP even without role strength."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "TopPlayer": {
                "Aatrox": {"games_weighted": 12, "win_rate_weighted": 0.7},
                "Azir": {"games_weighted": 120, "win_rate_weighted": 0.8},  # Many games on Azir
            },
        },
        role_history={
            "Aatrox": {"canonical_role": "TOP"},
            # Azir deliberately NOT in role_history, so no role_strength for mid
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    # TopPlayer is assigned mid but has no mid champions in role data (Aatrox=TOP, Azir has no role)
    # This means role_strength for mid is None (comfort_only mode)
    team_players = [{"name": "TopPlayer", "role": "mid"}]

    score, conf, player, source = scorer.get_champion_proficiency(
        "Azir", "mid", team_players
    )

    # Comfort would be 1.0 (100 games >> G_FULL), but should be capped at PROFICIENCY_CAP
    assert score <= ProficiencyScorer.PROFICIENCY_CAP
    assert source == "comfort_only"


def test_get_champion_proficiency_no_player_data_returns_no_data(tmp_path):
    """Unknown player returns NO_DATA."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={},
        role_history={"Azir": {"canonical_role": "MID"}},
    )
    scorer = ProficiencyScorer(knowledge_dir)
    team_players = [{"name": "UnknownPlayer", "role": "mid"}]

    score, conf, player, source = scorer.get_champion_proficiency(
        "Azir", "mid", team_players
    )

    assert score == 0.5
    assert conf == "NO_DATA"
    assert source == "none"


def test_get_champion_proficiency_monotonic_with_games(tmp_path):
    """More games always produces higher or equal proficiency."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "MidPlayer": {
                "Azir": {"games_weighted": 12, "win_rate_weighted": 0.7},
                "Syndra": {"games_weighted": 8, "win_rate_weighted": 0.6},
                "Viktor": {"games_weighted": 4, "win_rate_weighted": 0.6},
                "Orianna": {"games_weighted": 1, "win_rate_weighted": 0.6},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
            "Syndra": {"canonical_role": "MID"},
            "Viktor": {"canonical_role": "MID"},
            "Orianna": {"canonical_role": "MID"},
            "Ahri": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    team_players = [{"name": "MidPlayer", "role": "mid"}]

    # Test with a champion not in player data (uses comfort baseline)
    ahri_score, _, _, _ = scorer.get_champion_proficiency(
        "Ahri", "mid", team_players
    )

    orianna_score, _, _, _ = scorer.get_champion_proficiency(
        "Orianna", "mid", team_players
    )
    viktor_score, _, _, _ = scorer.get_champion_proficiency(
        "Viktor", "mid", team_players
    )
    syndra_score, _, _, _ = scorer.get_champion_proficiency(
        "Syndra", "mid", team_players
    )

    # More games should mean higher score (monotonic)
    assert ahri_score <= orianna_score
    assert orianna_score <= viktor_score
    assert viktor_score <= syndra_score


def test_get_champion_proficiency_cap_respected(tmp_path):
    """Proficiency never exceeds PROFICIENCY_CAP."""
    knowledge_dir = _write_proficiency_data(
        tmp_path,
        proficiencies={
            "ElitePlayer": {
                "Azir": {"games_weighted": 100, "win_rate_weighted": 0.9},
                "Syndra": {"games_weighted": 100, "win_rate_weighted": 0.9},
            },
        },
        role_history={
            "Azir": {"canonical_role": "MID"},
            "Syndra": {"canonical_role": "MID"},
        },
    )
    scorer = ProficiencyScorer(knowledge_dir)
    team_players = [{"name": "ElitePlayer", "role": "mid"}]

    score, _, _, _ = scorer.get_champion_proficiency(
        "Azir", "mid", team_players
    )

    assert score <= ProficiencyScorer.PROFICIENCY_CAP


