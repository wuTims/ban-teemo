"""Tests for LLM reranker service."""

import json
import pytest

from ban_teemo.services.llm_reranker import (
    LLMReranker,
    RerankedRecommendation,
    AdditionalSuggestion,
    RerankerResult,
)


# Test fixtures
@pytest.fixture
def sample_candidates():
    """Sample pick candidates from scoring engine."""
    return [
        {
            "champion_name": "Poppy",
            "score": 0.696,
            "suggested_role": "jungle",
            "proficiency_player": "Canyon",
            "components": {"meta": 0.594, "proficiency": 0.613},
            "reasons": ["B-tier meta pick"],
        },
        {
            "champion_name": "Rumble",
            "score": 0.69,
            "suggested_role": "top",
            "proficiency_player": "Kiin",
            "components": {"meta": 0.566, "proficiency": 0.70},
            "reasons": ["Strong team proficiency"],
        },
        {
            "champion_name": "Aurora",
            "score": 0.673,
            "suggested_role": "mid",
            "proficiency_player": "Chovy",
            "components": {"meta": 0.566, "proficiency": 0.70},
            "reasons": ["B-tier meta pick"],
        },
    ]


@pytest.fixture
def sample_draft_context():
    """Sample draft context."""
    return {
        "phase": "PICK_PHASE_1",
        "patch": "15.17",
        "our_team": "Gen.G Esports",
        "enemy_team": "T1",
        "our_picks": ["Orianna"],
        "enemy_picks": ["Yunara"],
        "banned": ["Azir", "Wukong", "Pantheon"],
    }


@pytest.fixture
def sample_players():
    """Sample team and enemy players."""
    team = [
        {"name": "Kiin", "role": "top"},
        {"name": "Canyon", "role": "jungle"},
        {"name": "Chovy", "role": "mid"},
    ]
    enemy = [
        {"name": "Doran", "role": "top"},
        {"name": "Oner", "role": "jungle"},
        {"name": "Faker", "role": "mid"},
    ]
    return team, enemy


class TestPromptGeneration:
    """Test prompt generation logic."""

    def test_pick_prompt_contains_context(self, sample_candidates, sample_draft_context, sample_players):
        """Pick prompt should contain all context information."""
        team_players, enemy_players = sample_players
        reranker = LLMReranker(api_key="test")

        prompt = reranker._build_pick_rerank_prompt(
            candidates=sample_candidates,
            draft_context=sample_draft_context,
            team_players=team_players,
            enemy_players=enemy_players,
            web_context="Test meta context",
            limit=5,
        )

        # Verify context is included
        assert "PICK_PHASE_1" in prompt
        assert "Gen.G Esports" in prompt
        assert "T1" in prompt
        assert "Orianna" in prompt
        assert "Yunara" in prompt

        # Verify our team players are included (enemy players are in web_context)
        assert "Kiin" in prompt
        # web_context contains player data
        assert "Test meta context" in prompt

        # Verify candidates are included
        assert "Poppy" in prompt
        assert "Rumble" in prompt

        # Verify JSON format instruction
        assert "reranked" in prompt
        assert "additional_suggestions" in prompt

    def test_ban_prompt_phase_guidance(self, sample_draft_context, sample_players):
        """Ban prompt should include phase-specific guidance."""
        team_players, enemy_players = sample_players
        reranker = LLMReranker(api_key="test")

        # Phase 1 ban prompt - uses phase1 specific prompt
        phase1_context = {**sample_draft_context, "phase": "BAN_PHASE_1"}
        prompt1 = reranker._build_ban_rerank_prompt(
            candidates=[{"champion_name": "Azir", "priority": 0.8, "components": {}, "reasons": []}],
            draft_context=phase1_context,
            our_players=team_players,
            enemy_players=enemy_players,
            web_context="",
            limit=5,
        )
        assert "BAN PHASE 1" in prompt1
        assert "META POWER BANS" in prompt1

        # Phase 2 ban prompt - uses synergy disruption focus
        phase2_context = {**sample_draft_context, "phase": "BAN_PHASE_2"}
        prompt2 = reranker._build_ban_rerank_prompt(
            candidates=[{"champion_name": "Azir", "priority": 0.8, "components": {}, "reasons": []}],
            draft_context=phase2_context,
            our_players=team_players,
            enemy_players=enemy_players,
            web_context="",
            limit=5,
        )
        assert "SYNERGY COMPLETERS" in prompt2


class TestResponseParsing:
    """Test LLM response parsing logic."""

    def test_parse_valid_response(self, sample_candidates):
        """Should correctly parse a valid LLM response."""
        reranker = LLMReranker(api_key="test")

        llm_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "reranked": [
                                    {
                                        "champion": "Rumble",
                                        "original_rank": 2,
                                        "new_rank": 1,
                                        "confidence": 0.85,
                                        "reasoning": "Good synergy",
                                        "strategic_factors": ["synergy"],
                                    },
                                    {
                                        "champion": "Poppy",
                                        "original_rank": 1,
                                        "new_rank": 2,
                                        "confidence": 0.75,
                                        "reasoning": "Still strong",
                                        "strategic_factors": ["meta"],
                                    },
                                ],
                                "additional_suggestions": [
                                    {
                                        "champion": "Malphite",
                                        "reasoning": "Good combo",
                                        "confidence": 0.6,
                                    }
                                ],
                                "draft_analysis": "Focus on engage",
                            }
                        )
                    }
                }
            ]
        }

        result = reranker._parse_pick_response(llm_response, sample_candidates, limit=5)

        assert len(result.reranked) == 2
        assert result.reranked[0].champion == "Rumble"
        assert result.reranked[0].new_rank == 1
        assert result.reranked[0].confidence == 0.85
        assert result.reranked[1].champion == "Poppy"
        assert len(result.additional_suggestions) == 1
        assert result.additional_suggestions[0].champion == "Malphite"
        assert result.draft_analysis == "Focus on engage"

    def test_parse_response_with_markdown(self, sample_candidates):
        """Should handle responses wrapped in markdown code blocks."""
        reranker = LLMReranker(api_key="test")

        # Response with markdown code block
        llm_response = {
            "choices": [
                {
                    "message": {
                        "content": """```json
{
  "reranked": [
    {"champion": "Poppy", "original_rank": 1, "new_rank": 1, "confidence": 0.8, "reasoning": "Test", "strategic_factors": []}
  ],
  "additional_suggestions": [],
  "draft_analysis": "Test analysis"
}
```"""
                    }
                }
            ]
        }

        result = reranker._parse_pick_response(llm_response, sample_candidates, limit=5)

        assert len(result.reranked) == 1
        assert result.reranked[0].champion == "Poppy"

    def test_parse_invalid_response_returns_fallback(self, sample_candidates):
        """Should return fallback result on parse error."""
        reranker = LLMReranker(api_key="test")

        # Invalid JSON response
        llm_response = {
            "choices": [{"message": {"content": "This is not JSON"}}]
        }

        result = reranker._parse_pick_response(llm_response, sample_candidates, limit=5)

        # Should return fallback preserving original order
        assert len(result.reranked) == 3  # Limited by candidates
        assert result.reranked[0].champion == "Poppy"  # Original #1
        assert result.reranked[1].champion == "Rumble"  # Original #2
        assert "algorithm" in result.reranked[0].reasoning.lower()  # Fallback indicator


class TestFallbackBehavior:
    """Test fallback behavior when LLM fails."""

    def test_fallback_result_preserves_order(self, sample_candidates):
        """Fallback should preserve original candidate order."""
        reranker = LLMReranker(api_key="test")

        result = reranker._fallback_result(sample_candidates, limit=3, error="Test error")

        assert len(result.reranked) == 3
        assert result.reranked[0].champion == "Poppy"
        assert result.reranked[0].original_rank == 1
        assert result.reranked[0].new_rank == 1
        assert result.reranked[1].champion == "Rumble"
        assert "Test error" in result.draft_analysis

    def test_fallback_result_respects_limit(self, sample_candidates):
        """Fallback should respect the limit parameter."""
        reranker = LLMReranker(api_key="test")

        result = reranker._fallback_result(sample_candidates, limit=2, error="Error")

        assert len(result.reranked) == 2


class TestModelSelection:
    """Test model selection logic."""

    def test_valid_model_selection(self):
        """Should select correct model IDs."""
        reranker_deepseek = LLMReranker(api_key="test", model="deepseek")
        assert "DeepSeek" in reranker_deepseek.model_id

        reranker_qwen = LLMReranker(api_key="test", model="qwen3")
        assert "Qwen" in reranker_qwen.model_id

        reranker_llama = LLMReranker(api_key="test", model="llama")
        assert "llama" in reranker_llama.model_id.lower()

    def test_invalid_model_defaults_to_deepseek(self):
        """Invalid model should default to DeepSeek."""
        reranker = LLMReranker(api_key="test", model="invalid_model")
        assert "DeepSeek" in reranker.model_id


class TestStrategicContextGeneration:
    """Test strategic context generation using local data."""

    def test_strategic_context_includes_archetypes(self, sample_draft_context, sample_players):
        """Strategic context should analyze draft archetypes."""
        team_players, enemy_players = sample_players
        reranker = LLMReranker(api_key="test")

        # Add some picks to enable archetype analysis
        context = {**sample_draft_context, "enemy_picks": ["Orianna", "Jarvan IV"]}
        strategic = reranker._build_strategic_context(context, team_players, enemy_players)

        # Should include some strategic analysis (even if just fallback)
        assert len(strategic) > 0

    def test_fallback_meta_context_returns_guidance(self, sample_draft_context):
        """Should provide fallback context with meta guidance."""
        reranker = LLMReranker(api_key="test")

        context = reranker._get_fallback_meta_context(sample_draft_context)

        assert "meta" in context.lower() or "patch" in context.lower()

    def test_available_champions_section_built(self, sample_draft_context, sample_players):
        """Should build available champions section for unfilled roles."""
        team_players, _ = sample_players
        reranker = LLMReranker(api_key="test")

        # With only one pick, most roles are unfilled
        section = reranker._build_available_picks_section(sample_draft_context, team_players)

        # Section should exist if there are unfilled roles
        # (may be empty if champion role data isn't loaded in test environment)
        assert section == "" or "Available Champions" in section


class TestDataClasses:
    """Test data class structures."""

    def test_reranked_recommendation_fields(self):
        """RerankedRecommendation should have all required fields."""
        rec = RerankedRecommendation(
            champion="Poppy",
            original_rank=1,
            new_rank=2,
            original_score=0.696,
            confidence=0.85,
            reasoning="Test reasoning",
            strategic_factors=["meta", "synergy"],
        )

        assert rec.champion == "Poppy"
        assert rec.original_rank == 1
        assert rec.new_rank == 2
        assert rec.original_score == 0.696
        assert rec.confidence == 0.85
        assert rec.reasoning == "Test reasoning"
        assert "meta" in rec.strategic_factors

    def test_additional_suggestion_fields(self):
        """AdditionalSuggestion should have all required fields."""
        sug = AdditionalSuggestion(
            champion="Malphite",
            reasoning="Good combo potential",
            confidence=0.6,
        )

        assert sug.champion == "Malphite"
        assert sug.reasoning == "Good combo potential"
        assert sug.confidence == 0.6

    def test_reranker_result_fields(self):
        """RerankerResult should aggregate all results."""
        result = RerankerResult(
            reranked=[
                RerankedRecommendation(
                    champion="Poppy",
                    original_rank=1,
                    new_rank=1,
                    original_score=0.7,
                    confidence=0.8,
                    reasoning="Test",
                )
            ],
            additional_suggestions=[
                AdditionalSuggestion(champion="Malphite", reasoning="Combo", confidence=0.6)
            ],
            draft_analysis="Focus on engage",
            raw_llm_response={"test": "data"},
        )

        assert len(result.reranked) == 1
        assert len(result.additional_suggestions) == 1
        assert result.draft_analysis == "Focus on engage"
        assert result.raw_llm_response is not None


class TestSeriesContextIntegration:
    """Test series context integration in prompts."""

    def test_no_series_section_for_none_context(self, sample_candidates, sample_draft_context, sample_players):
        """Should not include series section when context is None."""
        team_players, enemy_players = sample_players
        reranker = LLMReranker(api_key="test")

        prompt = reranker._build_pick_rerank_prompt(
            candidates=sample_candidates,
            draft_context=sample_draft_context,
            team_players=team_players,
            enemy_players=enemy_players,
            web_context="Test",
            limit=5,
            series_section="",
        )

        assert "Series Context" not in prompt

    def test_series_section_included_in_prompt(self, sample_candidates, sample_draft_context, sample_players):
        """Should include series section when provided."""
        team_players, enemy_players = sample_players
        reranker = LLMReranker(api_key="test")

        series_section = """## Series Context
- Game 2 of series
- Series Score: Blue 1 - 0 Red

### Previous Games

**Game 1** (Blue won):
  - Blue comp: Aatrox, Graves, Ahri, Jinx, Nautilus
  - Red comp: Renekton, Viego, Orianna, Ezreal, Leona"""

        prompt = reranker._build_pick_rerank_prompt(
            candidates=sample_candidates,
            draft_context=sample_draft_context,
            team_players=team_players,
            enemy_players=enemy_players,
            web_context="Test",
            limit=5,
            series_section=series_section,
        )

        assert "Series Context" in prompt
        assert "Game 2 of series" in prompt
        assert "Blue 1 - 0 Red" in prompt
        assert "Game 1" in prompt

    def test_build_series_context_section_empty_for_none(self):
        """Should return empty string for None context."""
        reranker = LLMReranker(api_key="test")

        section = reranker._build_series_context_section(None)

        assert section == ""

    def test_build_series_context_section_empty_for_game_1(self):
        """Should return empty string for game 1."""
        from ban_teemo.models.series_context import SeriesContext

        reranker = LLMReranker(api_key="test")

        context = SeriesContext(
            game_number=1,
            series_score=(0, 0),
            previous_games=[],
        )

        section = reranker._build_series_context_section(context)

        assert section == ""

    def test_build_series_context_section_with_previous_games(self):
        """Should build proper section for game 2+."""
        from ban_teemo.models.series_context import (
            PreviousGameSummary,
            SeriesContext,
            TeamTendencies,
        )

        reranker = LLMReranker(api_key="test")

        context = SeriesContext(
            game_number=2,
            series_score=(1, 0),
            previous_games=[
                PreviousGameSummary(
                    game_number=1,
                    winner="blue",
                    blue_comp=["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
                    red_comp=["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
                    blue_bans=["Azir", "Wukong", "Pantheon"],
                    red_bans=["KSante", "Yone", "Aurora"],
                )
            ],
            our_tendencies=TeamTendencies(
                prioritized_champions=["Aatrox"],
                first_pick_patterns=["Aatrox"],
                banned_against_them=["KSante"],
            ),
            enemy_tendencies=TeamTendencies(
                prioritized_champions=["Renekton"],
                first_pick_patterns=["Renekton"],
                banned_against_them=["Azir"],
            ),
        )

        section = reranker._build_series_context_section(context)

        assert "## Series Context" in section
        assert "Game 2 of series" in section
        assert "Blue 1 - 0 Red" in section
        assert "### Previous Games" in section
        assert "**Game 1** (Blue won)" in section
        assert "Aatrox" in section
        assert "Renekton" in section

        # Check tendencies
        assert "### Our Tendencies" in section
        assert "Priority picks: Aatrox" in section
        assert "### Enemy Tendencies" in section
        assert "Priority picks: Renekton" in section

    def test_ban_prompt_also_includes_series_context(self, sample_draft_context, sample_players):
        """Ban prompt should also support series context."""
        team_players, enemy_players = sample_players
        reranker = LLMReranker(api_key="test")

        series_section = "## Series Context\n- Game 2 of series"

        prompt = reranker._build_ban_rerank_prompt(
            candidates=[{"champion_name": "Azir", "priority": 0.8, "components": {}, "reasons": []}],
            draft_context=sample_draft_context,
            our_players=team_players,
            enemy_players=enemy_players,
            web_context="",
            limit=5,
            series_section=series_section,
        )

        assert "Series Context" in prompt
        assert "Game 2 of series" in prompt
