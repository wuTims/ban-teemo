"""Tests for meta scorer."""
import json
import pytest
from ban_teemo.services.scorers.meta_scorer import MetaScorer


@pytest.fixture
def scorer():
    return MetaScorer()


def test_get_meta_score_high_tier(scorer):
    """High-tier champion should have high meta score."""
    # Use "default" method to get raw meta_score (hybrid averages with presence)
    score = scorer.get_meta_score("Azir", method="default")
    assert 0.7 <= score <= 1.0


def test_get_meta_score_unknown(scorer):
    """Unknown champion returns neutral score."""
    score = scorer.get_meta_score("NonexistentChamp")
    assert score == 0.5


def test_get_meta_tier(scorer):
    """Test meta tier retrieval."""
    tier = scorer.get_meta_tier("Azir")
    assert tier in ["S", "A", "B", "C", "D", None]


def test_get_top_meta_champions(scorer):
    """Test getting top meta champions."""
    top = scorer.get_top_meta_champions(limit=5)
    assert len(top) <= 5
    assert all(isinstance(name, str) for name in top)


def test_get_top_meta_champions_filters_by_role(scorer):
    """Test that role parameter filters champions correctly."""
    # Get champions for different roles
    mid_champs = scorer.get_top_meta_champions(role="MID", limit=10)
    adc_champs = scorer.get_top_meta_champions(role="ADC", limit=10)
    jng_champs = scorer.get_top_meta_champions(role="JNG", limit=10)
    all_champs = scorer.get_top_meta_champions(limit=30)

    # Each list should return champions
    assert len(mid_champs) >= 1
    assert len(adc_champs) >= 1
    assert len(jng_champs) >= 1

    # Role-filtered lists should be subsets (or have significant overlap with) all champs
    # (some champions might be in multiple roles as flex picks)
    assert all(c in all_champs for c in mid_champs[:5])

    # Different roles should have different top champions
    # (at least some difference expected)
    mid_set = set(mid_champs[:5])
    adc_set = set(adc_champs[:5])
    # They shouldn't be identical (unless data is very limited)
    # This is a soft check - in edge cases they could overlap
    if len(mid_champs) >= 3 and len(adc_champs) >= 3:
        # At least some difference expected between roles
        assert mid_set != adc_set or len(mid_set) < 3


def test_get_top_meta_champions_role_aliases(scorer):
    """Test that role aliases work correctly."""
    # JNG and JUNGLE should return the same results
    jng_champs = scorer.get_top_meta_champions(role="JNG", limit=5)
    jungle_champs = scorer.get_top_meta_champions(role="JUNGLE", limit=5)
    assert jng_champs == jungle_champs

    # SUP and SUPPORT should return the same results
    sup_champs = scorer.get_top_meta_champions(role="SUP", limit=5)
    support_champs = scorer.get_top_meta_champions(role="SUPPORT", limit=5)
    assert sup_champs == support_champs


def _write_meta_knowledge(tmp_path, meta_stats, role_history):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "meta_stats.json").write_text(
        json.dumps({"champions": meta_stats})
    )
    (knowledge_dir / "champion_role_history.json").write_text(
        json.dumps({"champions": role_history})
    )
    return knowledge_dir


def test_current_viable_roles_override_all_time(tmp_path):
    meta_stats = {"RoleChamp": {"meta_score": 0.9}}
    role_history = {
        "RoleChamp": {
            "canonical_role": "TOP",
            "all_time_distribution": {"TOP": 1.0},
            "current_viable_roles": ["MID"],
        },
    }
    knowledge_dir = _write_meta_knowledge(tmp_path, meta_stats, role_history)
    scorer = MetaScorer(knowledge_dir)

    assert scorer.get_top_meta_champions(role="top", limit=5) == []
    assert scorer.get_top_meta_champions(role="mid", limit=5) == ["RoleChamp"]


def test_current_distribution_threshold_blocks_old_role(tmp_path):
    meta_stats = {"RoleChamp2": {"meta_score": 0.9}}
    role_history = {
        "RoleChamp2": {
            "current_distribution": {"TOP": 0.04, "MID": 0.96},
        },
    }
    knowledge_dir = _write_meta_knowledge(tmp_path, meta_stats, role_history)
    scorer = MetaScorer(knowledge_dir)

    assert scorer.get_top_meta_champions(role="top", limit=5) == []
    assert scorer.get_top_meta_champions(role="mid", limit=5) == ["RoleChamp2"]


def test_get_blind_pick_safety_counter_dependent_penalized():
    """Counter-pick dependent champions should have lower blind safety."""
    scorer = MetaScorer()

    # Neeko is flagged as counter_pick_dependent in meta_stats
    safety = scorer.get_blind_pick_safety("Neeko")

    # Should be penalized for blind picking
    assert safety < 0.9, f"Counter-dependent Neeko should have low blind safety: {safety}"


def test_get_blind_pick_safety_blind_safe_rewarded():
    """Champions with high blind win rate should have good safety."""
    scorer = MetaScorer()

    # Azir has high blind_early_win_rate
    safety = scorer.get_blind_pick_safety("Azir")

    assert safety >= 0.9, f"Blind-safe Azir should have high safety: {safety}"


def test_get_blind_pick_safety_unknown_neutral():
    """Unknown champions return neutral safety."""
    scorer = MetaScorer()

    safety = scorer.get_blind_pick_safety("NonexistentChamp")
    assert safety == 1.0, "Unknown should return neutral 1.0"


def test_get_presence_high_presence_champion():
    """High presence champion should return high score."""
    scorer = MetaScorer()
    presence = scorer.get_presence("Azir")
    assert presence >= 0.30, f"Azir should have presence >= 0.30: {presence}"


def test_get_presence_low_presence_champion():
    """Low presence champion should return low score."""
    scorer = MetaScorer()
    presence = scorer.get_presence("Qiyana")
    assert presence < 0.15, f"Qiyana should have presence < 0.15: {presence}"


def test_get_presence_unknown_champion():
    """Unknown champion returns 0."""
    scorer = MetaScorer()
    presence = scorer.get_presence("NonexistentChamp")
    assert presence == 0.0
