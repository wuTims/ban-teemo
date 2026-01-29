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
    assert result["primary"] == "engage"


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
