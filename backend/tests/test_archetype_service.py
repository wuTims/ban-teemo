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
