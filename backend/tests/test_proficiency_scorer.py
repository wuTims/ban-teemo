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
                "Azir": {"games_weighted": 10, "win_rate_weighted": 0.7},
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
                "Aatrox": {"games_weighted": 10, "win_rate_weighted": 0.7},
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
                "Azir": {"games_weighted": 10, "win_rate_weighted": 0.8},
                "Aatrox": {"games_weighted": 10, "win_rate_weighted": 0.5},
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
                "Azir": {"games_weighted": 10, "win_rate_weighted": 0.8},
            },
            "PlayerB": {
                "Azir": {"games_weighted": 10, "win_rate_weighted": 0.5},
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
