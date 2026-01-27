"""Tests for synergy service."""
import pytest
from ban_teemo.services.synergy_service import SynergyService


@pytest.fixture
def service():
    return SynergyService()


def test_get_synergy_score_curated(service):
    """Curated synergy should return high score."""
    score = service.get_synergy_score("Orianna", "Nocturne")
    assert score >= 0.7


def test_get_synergy_score_unknown(service):
    """Unknown pair returns neutral 0.5."""
    score = service.get_synergy_score("FakeChamp1", "FakeChamp2")
    assert score == 0.5


def test_calculate_team_synergy(service):
    """Test team synergy aggregation."""
    result = service.calculate_team_synergy(["Orianna", "Nocturne", "Malphite"])
    assert "total_score" in result
    assert 0.0 <= result["total_score"] <= 1.0
