"""Tests for archetype service."""
import pytest
from ban_teemo.services.archetype_service import ArchetypeService


@pytest.fixture
def service():
    return ArchetypeService()


def test_get_champion_archetypes(service):
    """Test getting archetypes for a champion."""
    result = service.get_champion_archetypes("Malphite")
    assert "primary" in result
    assert "scores" in result
    assert result["primary"] in service.ARCHETYPES
    if result["scores"]:
        top_score = max(result["scores"].values())
        assert result["scores"][result["primary"]] == top_score


def test_get_champion_archetypes_unknown(service):
    """Unknown champion returns neutral scores."""
    result = service.get_champion_archetypes("FakeChamp")
    assert result["primary"] is None


def test_calculate_team_archetype(service):
    """Test calculating team archetype from picks."""
    result = service.calculate_team_archetype(["Malphite", "Orianna", "Jarvan IV"])
    assert "primary" in result
    assert "scores" in result
    assert result["primary"] in ["engage", "teamfight", "split", "protect", "pick"]


def test_get_archetype_effectiveness(service):
    """Test RPS effectiveness lookup."""
    # Engage beats split
    eff = service.get_archetype_effectiveness("engage", "split")
    assert eff >= 1.0


def test_calculate_comp_advantage(service):
    """Test composition advantage calculation."""
    result = service.calculate_comp_advantage(
        our_picks=["Malphite", "Orianna"],
        enemy_picks=["Fiora", "Camille"]
    )
    assert "advantage" in result
    assert "our_archetype" in result
    assert "enemy_archetype" in result


def test_calculate_team_archetype_unknown_champions(service):
    """Team with all unknown champions should return primary=None."""
    result = service.calculate_team_archetype(["FakeChamp1", "FakeChamp2", "FakeChamp3"])
    assert result["primary"] is None
    assert result["secondary"] is None
    assert result["alignment"] == 0.0
    # Scores should all be zero
    assert sum(result["scores"].values()) == 0.0


def test_calculate_comp_advantage_unknown_champions(service):
    """Comp advantage with unknown champions should handle gracefully."""
    result = service.calculate_comp_advantage(
        our_picks=["UnknownChamp1"],
        enemy_picks=["UnknownChamp2"]
    )
    # Both should be None, advantage should be neutral (1.0)
    assert result["our_archetype"] is None
    assert result["enemy_archetype"] is None
    assert result["advantage"] == 1.0


def test_get_versatility_score_single_archetype():
    """Single-archetype champions have low versatility."""
    service = ArchetypeService()
    # Azir has only teamfight: 0.6
    score = service.get_versatility_score("Azir")
    assert score < 0.3, "Single archetype should have low versatility"


def test_get_versatility_score_multi_archetype():
    """Multi-archetype champions have high versatility."""
    service = ArchetypeService()
    # Orianna has engage: 0.5, protect: 0.5, teamfight: 1.0
    score = service.get_versatility_score("Orianna")
    assert score >= 0.5, "Multi-archetype should have high versatility"


def test_get_versatility_score_unknown_champion():
    """Unknown champions return neutral versatility."""
    service = ArchetypeService()
    score = service.get_versatility_score("NonexistentChamp")
    assert score == 0.0


def test_get_contribution_to_archetype_matching():
    """Champion contributes to team's primary archetype."""
    service = ArchetypeService()
    # Orianna has teamfight: 1.0, adding to teamfight team should score high
    score = service.get_contribution_to_archetype("Orianna", "teamfight")
    assert score >= 0.8, "Orianna should contribute highly to teamfight"


def test_get_contribution_to_archetype_mismatched():
    """Champion doesn't contribute to unrelated archetype."""
    service = ArchetypeService()
    # Orianna has no split archetype
    score = service.get_contribution_to_archetype("Orianna", "split")
    assert score == 0.0, "Orianna should not contribute to split"


def test_get_contribution_to_archetype_partial():
    """Champion partially contributes to secondary archetype."""
    service = ArchetypeService()
    # Orianna has engage: 0.5
    score = service.get_contribution_to_archetype("Orianna", "engage")
    assert 0.3 <= score <= 0.7, "Orianna should partially contribute to engage"


def test_get_raw_strength_returns_max_score():
    """Raw strength is the maximum archetype score."""
    service = ArchetypeService()
    # Orianna has engage: 0.5, protect: 0.5, teamfight: 1.0
    strength = service.get_raw_strength("Orianna")
    assert strength == 1.0, "Should return max archetype score"


def test_get_raw_strength_single_archetype():
    """Single archetype champion returns that score."""
    service = ArchetypeService()
    # Azir has teamfight: 0.6
    strength = service.get_raw_strength("Azir")
    assert strength == 0.6


def test_get_raw_strength_unknown():
    """Unknown champion returns 0.5 neutral."""
    service = ArchetypeService()
    strength = service.get_raw_strength("NonexistentChamp")
    assert strength == 0.5
