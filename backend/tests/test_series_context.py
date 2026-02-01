"""Tests for SeriesContext dataclasses."""

import pytest

from ban_teemo.models.series_context import (
    PreviousGameSummary,
    SeriesContext,
    TeamTendencies,
)


class TestPreviousGameSummary:
    """Tests for PreviousGameSummary dataclass."""

    def test_create_summary(self):
        """Should create a valid game summary."""
        summary = PreviousGameSummary(
            game_number=1,
            winner="blue",
            blue_comp=["Aatrox", "Graves", "Ahri", "Jinx", "Nautilus"],
            red_comp=["Renekton", "Viego", "Orianna", "Ezreal", "Leona"],
            blue_bans=["Azir", "Wukong", "Pantheon"],
            red_bans=["KSante", "Yone", "Aurora"],
        )

        assert summary.game_number == 1
        assert summary.winner == "blue"
        assert len(summary.blue_comp) == 5
        assert len(summary.red_comp) == 5
        assert "Aatrox" in summary.blue_comp
        assert "Renekton" in summary.red_comp

    def test_winner_type(self):
        """Winner should be 'blue' or 'red'."""
        summary_blue = PreviousGameSummary(
            game_number=1,
            winner="blue",
            blue_comp=[],
            red_comp=[],
            blue_bans=[],
            red_bans=[],
        )
        summary_red = PreviousGameSummary(
            game_number=2,
            winner="red",
            blue_comp=[],
            red_comp=[],
            blue_bans=[],
            red_bans=[],
        )

        assert summary_blue.winner == "blue"
        assert summary_red.winner == "red"


class TestTeamTendencies:
    """Tests for TeamTendencies dataclass."""

    def test_default_empty_lists(self):
        """Should have empty lists by default."""
        tendencies = TeamTendencies()

        assert tendencies.prioritized_champions == []
        assert tendencies.first_pick_patterns == []
        assert tendencies.banned_against_them == []

    def test_create_with_data(self):
        """Should store tendency data correctly."""
        tendencies = TeamTendencies(
            prioritized_champions=["Aatrox", "Orianna"],
            first_pick_patterns=["Aatrox"],
            banned_against_them=["Azir", "Aurora"],
        )

        assert "Aatrox" in tendencies.prioritized_champions
        assert "Orianna" in tendencies.prioritized_champions
        assert tendencies.first_pick_patterns == ["Aatrox"]
        assert len(tendencies.banned_against_them) == 2


class TestSeriesContext:
    """Tests for SeriesContext dataclass."""

    def test_game_1_has_no_series_context(self):
        """Game 1 should report no series context available."""
        context = SeriesContext(
            game_number=1,
            series_score=(0, 0),
            previous_games=[],
        )

        assert context.is_series_context_available is False

    def test_game_2_with_previous_games_has_context(self):
        """Game 2+ with previous games should report context available."""
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
        )

        assert context.is_series_context_available is True

    def test_game_2_without_previous_games_no_context(self):
        """Game 2+ without previous games should report no context."""
        context = SeriesContext(
            game_number=2,
            series_score=(1, 0),
            previous_games=[],  # Empty!
        )

        assert context.is_series_context_available is False

    def test_series_score_tracking(self):
        """Should track series score correctly."""
        context = SeriesContext(
            game_number=3,
            series_score=(1, 1),
            previous_games=[],
        )

        assert context.series_score == (1, 1)
        assert context.series_score[0] == 1  # Blue wins
        assert context.series_score[1] == 1  # Red wins

    def test_tendencies_optional(self):
        """Tendencies should be optional."""
        context = SeriesContext(
            game_number=2,
            series_score=(1, 0),
            previous_games=[
                PreviousGameSummary(
                    game_number=1,
                    winner="blue",
                    blue_comp=[],
                    red_comp=[],
                    blue_bans=[],
                    red_bans=[],
                )
            ],
        )

        assert context.our_tendencies is None
        assert context.enemy_tendencies is None

    def test_full_context_with_tendencies(self):
        """Should store full context with tendencies."""
        our_tendencies = TeamTendencies(
            prioritized_champions=["Aatrox", "Orianna"],
            first_pick_patterns=["Aatrox"],
            banned_against_them=["Azir"],
        )
        enemy_tendencies = TeamTendencies(
            prioritized_champions=["Renekton"],
            first_pick_patterns=["Renekton"],
            banned_against_them=["KSante"],
        )

        context = SeriesContext(
            game_number=3,
            series_score=(2, 0),
            previous_games=[
                PreviousGameSummary(
                    game_number=1,
                    winner="blue",
                    blue_comp=["Aatrox", "Graves", "Orianna", "Jinx", "Nautilus"],
                    red_comp=["Renekton", "Viego", "Ahri", "Ezreal", "Leona"],
                    blue_bans=["KSante"],
                    red_bans=["Azir"],
                ),
                PreviousGameSummary(
                    game_number=2,
                    winner="blue",
                    blue_comp=["Aatrox", "Elise", "Orianna", "Aphelios", "Thresh"],
                    red_comp=["Renekton", "Lee Sin", "Syndra", "Varus", "Braum"],
                    blue_bans=["KSante"],
                    red_bans=["Azir"],
                ),
            ],
            our_tendencies=our_tendencies,
            enemy_tendencies=enemy_tendencies,
        )

        assert context.is_series_context_available is True
        assert context.our_tendencies is not None
        assert context.enemy_tendencies is not None
        assert "Aatrox" in context.our_tendencies.prioritized_champions
        assert "Renekton" in context.enemy_tendencies.prioritized_champions
