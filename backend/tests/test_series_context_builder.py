"""Tests for SeriesContextBuilder."""

import pytest

from ban_teemo.models.series_context import (
    PreviousGameSummary,
    SeriesContext,
    TeamTendencies,
)
from ban_teemo.services.series_context_builder import SeriesContextBuilder


class TestFromGameResults:
    """Tests for building context from game results."""

    def test_empty_results_returns_minimal_context(self):
        """Should return minimal context for empty results."""
        context = SeriesContextBuilder.from_game_results(
            game_number=1,
            previous_results=[],
            our_side="blue",
        )

        assert context.game_number == 1
        assert context.series_score == (0, 0)
        assert context.previous_games == []
        assert not context.is_series_context_available

    def test_single_game_result(self):
        """Should build context from single previous game."""
        previous_results = [
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
                "red_comp": ["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
                "blue_bans": ["Azir", "Wukong", "Pantheon"],
                "red_bans": ["KSante", "Yone", "Aurora"],
            }
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=2,
            previous_results=previous_results,
            our_side="blue",
        )

        assert context.game_number == 2
        assert context.series_score == (1, 0)  # Blue won 1 game
        assert len(context.previous_games) == 1
        assert context.is_series_context_available

    def test_multiple_game_results(self):
        """Should build context from multiple previous games."""
        previous_results = [
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
                "red_comp": ["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
                "blue_bans": ["Azir"],
                "red_bans": ["KSante"],
            },
            {
                "winner": "red",
                "blue_comp": ["Aatrox", "Elise", "Syndra", "Aphelios", "Thresh"],
                "red_comp": ["Renekton", "Lee Sin", "Ahri", "Varus", "Braum"],
                "blue_bans": ["Azir"],
                "red_bans": ["KSante"],
            },
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=3,
            previous_results=previous_results,
            our_side="blue",
        )

        assert context.game_number == 3
        assert context.series_score == (1, 1)  # 1-1 series
        assert len(context.previous_games) == 2
        assert context.previous_games[0].winner == "blue"
        assert context.previous_games[1].winner == "red"

    def test_series_score_all_blue_wins(self):
        """Should correctly calculate series score when blue wins all."""
        previous_results = [
            {"winner": "blue", "blue_comp": [], "red_comp": [], "blue_bans": [], "red_bans": []},
            {"winner": "blue", "blue_comp": [], "red_comp": [], "blue_bans": [], "red_bans": []},
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=3,
            previous_results=previous_results,
            our_side="blue",
        )

        assert context.series_score == (2, 0)

    def test_series_score_all_red_wins(self):
        """Should correctly calculate series score when red wins all."""
        previous_results = [
            {"winner": "red", "blue_comp": [], "red_comp": [], "blue_bans": [], "red_bans": []},
            {"winner": "red", "blue_comp": [], "red_comp": [], "blue_bans": [], "red_bans": []},
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=3,
            previous_results=previous_results,
            our_side="red",
        )

        assert context.series_score == (0, 2)


class TestTendencyExtraction:
    """Tests for tendency extraction logic."""

    def test_prioritized_champions_identified(self):
        """Should identify champions picked in multiple games."""
        previous_results = [
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
                "red_comp": ["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
                "blue_bans": [],
                "red_bans": [],
            },
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Elise", "Ahri", "Aphelios", "Thresh"],  # Aatrox, Ahri repeat
                "red_comp": ["Renekton", "Lee Sin", "Syndra", "Varus", "Braum"],  # Renekton repeats
                "blue_bans": [],
                "red_bans": [],
            },
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=3,
            previous_results=previous_results,
            our_side="blue",
        )

        # Blue (our) tendencies
        assert context.our_tendencies is not None
        assert "Aatrox" in context.our_tendencies.prioritized_champions
        assert "Ahri" in context.our_tendencies.prioritized_champions

        # Red (enemy) tendencies
        assert context.enemy_tendencies is not None
        assert "Renekton" in context.enemy_tendencies.prioritized_champions

    def test_first_pick_patterns_identified(self):
        """Should identify consistent first picks."""
        previous_results = [
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
                "red_comp": ["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
                "blue_bans": [],
                "red_bans": [],
            },
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Elise", "Syndra", "Aphelios", "Thresh"],  # Aatrox first again
                "red_comp": ["Renekton", "Lee Sin", "Ahri", "Varus", "Braum"],  # Renekton first again
                "blue_bans": [],
                "red_bans": [],
            },
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=3,
            previous_results=previous_results,
            our_side="blue",
        )

        # First pick patterns (picked first in 2+ games)
        assert context.our_tendencies is not None
        assert "Aatrox" in context.our_tendencies.first_pick_patterns

        assert context.enemy_tendencies is not None
        assert "Renekton" in context.enemy_tendencies.first_pick_patterns

    def test_bans_against_identified(self):
        """Should identify champions repeatedly banned against a team."""
        previous_results = [
            {
                "winner": "blue",
                "blue_comp": [],
                "red_comp": [],
                "blue_bans": ["Azir", "Wukong"],  # Blue bans against red
                "red_bans": ["KSante", "Aurora"],  # Red bans against blue
            },
            {
                "winner": "blue",
                "blue_comp": [],
                "red_comp": [],
                "blue_bans": ["Azir", "Pantheon"],  # Azir banned again
                "red_bans": ["KSante", "Yone"],  # KSante banned again
            },
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=3,
            previous_results=previous_results,
            our_side="blue",
        )

        # Bans received by blue (from red)
        assert context.our_tendencies is not None
        assert "KSante" in context.our_tendencies.banned_against_them

        # Bans received by red (from blue)
        assert context.enemy_tendencies is not None
        assert "Azir" in context.enemy_tendencies.banned_against_them

    def test_no_tendencies_for_single_game(self):
        """Single game shouldn't produce repeat-based tendencies."""
        previous_results = [
            {
                "winner": "blue",
                "blue_comp": ["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
                "red_comp": ["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
                "blue_bans": ["Azir"],
                "red_bans": ["KSante"],
            },
        ]

        context = SeriesContextBuilder.from_game_results(
            game_number=2,
            previous_results=previous_results,
            our_side="blue",
        )

        # No champion picked multiple times -> empty priorities
        assert context.our_tendencies is not None
        assert context.our_tendencies.prioritized_champions == []


class TestFromReplayLogs:
    """Tests for building context from replay logs."""

    def test_first_game_returns_minimal_context(self):
        """First game (index 0) should return minimal context."""
        replay_logs = [{"metadata": {}, "entries": []}]

        context = SeriesContextBuilder.from_replay_logs(
            replay_logs=replay_logs,
            current_game_index=0,
            our_side="blue",
        )

        assert context.game_number == 1
        assert not context.is_series_context_available

    def test_extracts_picks_from_entries(self):
        """Should extract picks from actual_action entries."""
        game1_log = {
            "metadata": {"winner": "blue"},
            "entries": [
                {"event": "actual_action", "champion": "Aatrox", "team": "blue", "action_type": "pick"},
                {"event": "actual_action", "champion": "Renekton", "team": "red", "action_type": "pick"},
                {"event": "actual_action", "champion": "Graves", "team": "blue", "action_type": "pick"},
                {"event": "actual_action", "champion": "Viego", "team": "red", "action_type": "pick"},
            ],
        }
        game2_log = {
            "metadata": {},
            "entries": [],
        }

        context = SeriesContextBuilder.from_replay_logs(
            replay_logs=[game1_log, game2_log],
            current_game_index=1,
            our_side="blue",
        )

        assert context.game_number == 2
        assert len(context.previous_games) == 1
        assert "Aatrox" in context.previous_games[0].blue_comp
        assert "Graves" in context.previous_games[0].blue_comp
        assert "Renekton" in context.previous_games[0].red_comp
        assert "Viego" in context.previous_games[0].red_comp

    def test_extracts_bans_from_entries(self):
        """Should extract bans from actual_action entries."""
        game1_log = {
            "metadata": {"winner": "blue"},
            "entries": [
                {"event": "actual_action", "champion": "Azir", "team": "blue", "action_type": "ban"},
                {"event": "actual_action", "champion": "KSante", "team": "red", "action_type": "ban"},
            ],
        }

        context = SeriesContextBuilder.from_replay_logs(
            replay_logs=[game1_log],
            current_game_index=1,
            our_side="blue",
        )

        # When current_game_index=1, it looks at logs[0] as previous game
        # But we only have 1 log, so previous_results will be empty
        # Let's fix the test to have 2 logs
        game2_log = {"metadata": {}, "entries": []}
        context = SeriesContextBuilder.from_replay_logs(
            replay_logs=[game1_log, game2_log],
            current_game_index=1,
            our_side="blue",
        )

        assert len(context.previous_games) == 1
        assert "Azir" in context.previous_games[0].blue_bans
        assert "KSante" in context.previous_games[0].red_bans


class TestFromDatabase:
    """Tests for database loading (placeholder implementation)."""

    def test_returns_empty_context(self):
        """Should return empty context (not fully implemented)."""
        context = SeriesContextBuilder.from_database(
            series_id="test_series",
            game_number=2,
            our_side="blue",
        )

        # Currently returns empty context
        assert context.game_number == 2
        assert context.series_score == (0, 0)
        assert context.previous_games == []
