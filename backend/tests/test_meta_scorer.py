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
