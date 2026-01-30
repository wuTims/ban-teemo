"""Tests for recommendation models."""

import pytest
from ban_teemo.models.recommendations import RoleGroupedRecommendations, PickRecommendation


def test_role_grouped_recommendations_structure():
    """RoleGroupedRecommendations groups picks by role."""
    pick1 = PickRecommendation(
        champion_name="Vi",
        confidence=0.9,
        suggested_role="jungle",
        flag=None,
        reasons=["Strong engage"],
        score=0.75,
        base_score=0.70,
        synergy_multiplier=1.07,
        components={"meta": 0.6, "proficiency": 0.8},
        proficiency_source="direct",
        proficiency_player="Canyon",
    )
    pick2 = PickRecommendation(
        champion_name="Xin Zhao",
        confidence=0.9,
        suggested_role="jungle",
        flag=None,
        reasons=["Comfort pick"],
        score=0.72,
        base_score=0.68,
        synergy_multiplier=1.06,
        components={"meta": 0.55, "proficiency": 0.9},
        proficiency_source="direct",
        proficiency_player="Canyon",
    )
    pick3 = PickRecommendation(
        champion_name="Rumble",
        confidence=0.85,
        suggested_role="top",
        flag=None,
        reasons=["Strong laner"],
        score=0.70,
        base_score=0.65,
        synergy_multiplier=1.08,
        components={"meta": 0.6, "proficiency": 0.7},
        proficiency_source="direct",
        proficiency_player="Kiin",
    )

    grouped = RoleGroupedRecommendations.from_picks([pick1, pick2, pick3], limit_per_role=2)

    assert "jungle" in grouped.by_role
    assert len(grouped.by_role["jungle"]) == 2
    assert grouped.by_role["jungle"][0].champion_name == "Vi"  # Higher score first
    assert grouped.by_role["jungle"][1].champion_name == "Xin Zhao"
    assert "top" in grouped.by_role
    assert len(grouped.by_role["top"]) == 1


def test_role_grouped_recommendations_to_dict():
    """RoleGroupedRecommendations serializes correctly."""
    pick = PickRecommendation(
        champion_name="Vi",
        confidence=0.9,
        suggested_role="jungle",
        flag=None,
        reasons=["Strong engage"],
        score=0.75,
        base_score=0.70,
        synergy_multiplier=1.07,
        components={"meta": 0.6},
        proficiency_source="direct",
        proficiency_player="Canyon",
    )

    grouped = RoleGroupedRecommendations.from_picks([pick], limit_per_role=2)
    result = grouped.to_dict()

    assert "by_role" in result
    assert "jungle" in result["by_role"]
    assert result["by_role"]["jungle"][0]["champion_name"] == "Vi"


def test_role_grouped_recommendations_respects_limit():
    """RoleGroupedRecommendations respects limit_per_role."""
    picks = [
        PickRecommendation(
            champion_name=f"Champ{i}",
            confidence=0.9,
            suggested_role="mid",
            score=0.9 - i * 0.1,
        )
        for i in range(5)
    ]

    grouped = RoleGroupedRecommendations.from_picks(picks, limit_per_role=3)

    assert len(grouped.by_role["mid"]) == 3
    # Should be top 3 by score
    assert grouped.by_role["mid"][0].champion_name == "Champ0"
    assert grouped.by_role["mid"][1].champion_name == "Champ1"
    assert grouped.by_role["mid"][2].champion_name == "Champ2"


def test_role_grouped_recommendations_handles_none_role():
    """RoleGroupedRecommendations handles picks with no suggested_role."""
    pick = PickRecommendation(
        champion_name="Mystery",
        confidence=0.5,
        suggested_role=None,
        score=0.5,
    )

    grouped = RoleGroupedRecommendations.from_picks([pick], limit_per_role=2)

    assert "unknown" in grouped.by_role
    assert grouped.by_role["unknown"][0].champion_name == "Mystery"


def test_role_grouped_recommendations_empty_list():
    """RoleGroupedRecommendations handles empty input."""
    grouped = RoleGroupedRecommendations.from_picks([], limit_per_role=2)

    assert grouped.by_role == {}
