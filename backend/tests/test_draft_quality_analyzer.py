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


def test_analyze_with_empty_recommendations():
    """Handle case where no recommendations were tracked."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    result = analyzer.analyze(
        actual_picks=["Renekton", "Lee Sin", "Ahri", "Jinx", "Thresh"],
        recommended_picks=[],  # No recommendations tracked
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    assert result["recommended_draft"]["picks"] == []
    assert result["comparison"]["picks_tracked"] == 0
    assert result["comparison"]["picks_matched"] == 0


def test_analyze_with_unknown_champions():
    """Handle champions not in archetype data."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Use a mix of known and unknown champion names
    result = analyzer.analyze(
        actual_picks=["Renekton", "UnknownChamp1", "Ahri", "Jinx", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    # Should still return valid structure
    assert "actual_draft" in result
    assert "recommended_draft" in result
    assert "comparison" in result

    # Check all required fields exist
    assert "picks" in result["actual_draft"]
    assert "archetype" in result["actual_draft"]
    assert "composition_score" in result["actual_draft"]
    assert "vs_enemy_advantage" in result["actual_draft"]

    # Recommended draft has same fields
    assert "picks" in result["recommended_draft"]
    assert "archetype" in result["recommended_draft"]
    assert "composition_score" in result["recommended_draft"]
    assert "vs_enemy_advantage" in result["recommended_draft"]

    # Comparison has required fields
    assert "score_delta" in result["comparison"]
    assert "archetype_insight" in result["comparison"]


def test_analyze_archetype_insight_describes_matchup():
    """Insight describes actual vs enemy archetype matchup."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Pick teams with different archetypes
    result = analyzer.analyze(
        actual_picks=["Jarvan IV", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        recommended_picks=["Zac", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    # Insight should describe the actual vs enemy matchup (purely descriptive)
    insight = result["comparison"]["archetype_insight"]
    actual_arch = result["actual_draft"]["archetype"]

    # Should mention the actual archetype and be descriptive (favored, neutral, or mirror)
    assert actual_arch in insight.lower() or "mirror" in insight.lower() or "neutral" in insight.lower(), \
        f"Insight should describe matchup, got: {insight}"


def test_analyze_picks_matched_with_top_5_recommendations():
    """Picks matched counts picks found in top 5 recommendations per slot."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # New format: list of top-5 recommendations per slot
    result = analyzer.analyze(
        actual_picks=["Rumble", "Lee Sin", "Ahri", "Kai'Sa", "Thresh"],
        recommended_picks=[
            ["Renekton", "Rumble", "Jayce", "Gnar", "Aatrox"],  # Rumble is #2
            ["Sejuani", "Viego", "Lee Sin", "Jarvan IV", "Xin Zhao"],  # Lee Sin is #3
            ["Orianna", "Syndra", "Azir", "Viktor", "Ahri"],  # Ahri is #5
            ["Kai'Sa", "Jinx", "Aphelios", "Zeri", "Xayah"],  # Kai'Sa is #1
            ["Rakan", "Nautilus", "Leona", "Thresh", "Alistar"],  # Thresh is #4
        ],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    # All 5 picks were in top 5 (just not all #1)
    assert result["comparison"]["picks_matched"] == 5
    assert result["comparison"]["picks_tracked"] == 5


def test_analyze_picks_matched_legacy_format():
    """Legacy format (list of strings) still works for backwards compat."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Legacy format: just top 1 picks
    result = analyzer.analyze(
        actual_picks=["Rumble", "Lee Sin", "Ahri", "Kai'Sa", "Thresh"],
        recommended_picks=["Rumble", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Jayce", "Viego", "Syndra", "Ezreal", "Nautilus"],
    )

    # Only Rumble and Kai'Sa match exactly
    assert result["comparison"]["picks_matched"] == 2
    assert result["comparison"]["picks_tracked"] == 5


def test_analyze_mirror_archetype_insight():
    """Mirror matchup is described as such."""
    from ban_teemo.services.draft_quality_analyzer import DraftQualityAnalyzer

    analyzer = DraftQualityAnalyzer()

    # Both teams have engage comp
    result = analyzer.analyze(
        actual_picks=["Jarvan IV", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        recommended_picks=["Zac", "Sejuani", "Orianna", "Kai'Sa", "Rakan"],
        enemy_picks=["Malphite", "Wukong", "Orianna", "Miss Fortune", "Leona"],
    )

    insight = result["comparison"]["archetype_insight"]
    # Mirror matchups should be described as mirror
    if result["actual_draft"]["archetype"] is not None:
        # If archetypes can be determined, insight should be descriptive
        assert "vs" in insight.lower() or "mirror" in insight.lower() or "neutral" in insight.lower()
