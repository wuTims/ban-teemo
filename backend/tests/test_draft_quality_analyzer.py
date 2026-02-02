# backend/tests/test_draft_quality_analyzer.py
import pytest


def test_analyze_returns_both_team_evaluations():
    """Analyzer returns evaluation for actual and recommended teams."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    assert "actual_draft" in result
    assert "recommended_draft" in result
    assert "comparison" in result

    # Actual draft has required fields
    assert "picks" in result["actual_draft"]
    assert "archetype" in result["actual_draft"]
    assert "composition_score" in result["actual_draft"]
    assert "vs_enemy_advantage" in result["actual_draft"]

    # Recommended draft has same fields
    assert "picks" in result["recommended_draft"]
    assert "archetype" in result["recommended_draft"]
    assert "composition_score" in result["recommended_draft"]
    assert "vs_enemy_advantage" in result["recommended_draft"]

    # Comparison has delta and insight
    assert "score_delta" in result["comparison"]
    assert "archetype_insight" in result["comparison"]


def test_analyze_with_partial_recommendations():
    """Analyzer handles case where not all 5 picks have recommendations."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Only 3 recommended picks (maybe session interrupted)
    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    assert result["recommended_draft"]["picks"] == ["Rumble", "Sejuani", "Orianna"]
    assert result["comparison"]["picks_tracked"] == 3


def test_analyze_calculates_score_delta():
    """Score delta is recommended minus actual."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    expected_delta = (
        result["recommended_draft"]["composition_score"]
        - result["actual_draft"]["composition_score"]
    )
    assert abs(result["comparison"]["score_delta"] - expected_delta) < 0.001
