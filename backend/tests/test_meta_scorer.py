"""Tests for meta scorer."""
import pytest
from ban_teemo.services.scorers.meta_scorer import MetaScorer


@pytest.fixture
def scorer():
    return MetaScorer()


def test_get_meta_score_high_tier(scorer):
    """High-tier champion should have high meta score."""
    score = scorer.get_meta_score("Azir")
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
