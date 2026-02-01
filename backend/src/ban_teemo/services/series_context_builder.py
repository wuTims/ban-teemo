"""Builder for constructing SeriesContext from various data sources.

Provides methods to build series context from:
- Game results (for production use with SimulatorSession)
- Database queries (for experiments against historical data)
"""

import logging
from collections import Counter
from typing import Literal, Optional

from ban_teemo.models.series_context import (
    PreviousGameSummary,
    SeriesContext,
    TeamTendencies,
)


logger = logging.getLogger(__name__)


class SeriesContextBuilder:
    """Builds SeriesContext from various data sources."""

    @staticmethod
    def from_game_results(
        game_number: int,
        previous_results: list[dict],
        our_side: Literal["blue", "red"],
    ) -> SeriesContext:
        """Build series context from completed game results.

        Args:
            game_number: Current game number (1-indexed)
            previous_results: List of game result dicts with keys:
                - winner: "blue" or "red"
                - blue_comp: list of champion names
                - red_comp: list of champion names
                - blue_bans: list of champion names
                - red_bans: list of champion names
            our_side: Which side we're playing on ("blue" or "red")

        Returns:
            SeriesContext with previous games and extracted tendencies
        """
        if not previous_results:
            return SeriesContext(
                game_number=game_number,
                series_score=(0, 0),
                previous_games=[],
            )

        # Build previous game summaries
        previous_games = []
        blue_wins = 0
        red_wins = 0

        for i, result in enumerate(previous_results, 1):
            winner = result.get("winner", "blue")
            if winner == "blue":
                blue_wins += 1
            else:
                red_wins += 1

            previous_games.append(
                PreviousGameSummary(
                    game_number=i,
                    winner=winner,
                    blue_comp=result.get("blue_comp", []),
                    red_comp=result.get("red_comp", []),
                    blue_bans=result.get("blue_bans", []),
                    red_bans=result.get("red_bans", []),
                )
            )

        # Extract tendencies
        our_tendencies = SeriesContextBuilder._extract_tendencies(
            previous_games, our_side
        )
        enemy_side: Literal["blue", "red"] = "red" if our_side == "blue" else "blue"
        enemy_tendencies = SeriesContextBuilder._extract_tendencies(
            previous_games, enemy_side
        )

        return SeriesContext(
            game_number=game_number,
            series_score=(blue_wins, red_wins),
            previous_games=previous_games,
            our_tendencies=our_tendencies,
            enemy_tendencies=enemy_tendencies,
        )

    @staticmethod
    def from_database(
        series_id: str,
        game_number: int,
        our_side: Literal["blue", "red"],
        db_connection: Optional[object] = None,
    ) -> SeriesContext:
        """Build series context by querying previous games from database.

        This is for experiment/evaluation use where we query historical
        match data to reconstruct series context.

        Args:
            series_id: Unique identifier for the series
            game_number: Current game number (1-indexed)
            our_side: Which side we're playing on
            db_connection: Database connection (currently unused, for future use)

        Returns:
            SeriesContext with previous games from database
        """
        # For now, return empty context - actual DB implementation depends on schema
        logger.warning(
            f"from_database not fully implemented. series_id={series_id}, "
            f"game_number={game_number}"
        )
        return SeriesContext(
            game_number=game_number,
            series_score=(0, 0),
            previous_games=[],
        )

    @staticmethod
    def from_replay_logs(
        replay_logs: list[dict],
        current_game_index: int,
        our_side: Literal["blue", "red"],
    ) -> SeriesContext:
        """Build series context from replay log files.

        Useful for experiments where we have multiple replay logs
        from the same series.

        Args:
            replay_logs: List of parsed replay log dicts (one per game)
            current_game_index: Index of current game (0-indexed)
            our_side: Which side we're playing on

        Returns:
            SeriesContext with previous games from replay logs
        """
        if current_game_index <= 0:
            return SeriesContext(
                game_number=1,
                series_score=(0, 0),
                previous_games=[],
            )

        previous_results = []
        for i, log in enumerate(replay_logs[:current_game_index]):
            metadata = log.get("metadata", {})
            entries = log.get("entries", [])

            # Extract final compositions from entries
            blue_comp = []
            red_comp = []
            blue_bans = []
            red_bans = []

            for entry in entries:
                if entry.get("event") == "actual_action":
                    champ = entry.get("champion", "")
                    team = entry.get("team", "")
                    action_type = entry.get("action_type", "")

                    if action_type == "pick":
                        if team == "blue":
                            blue_comp.append(champ)
                        else:
                            red_comp.append(champ)
                    elif action_type == "ban":
                        if team == "blue":
                            blue_bans.append(champ)
                        else:
                            red_bans.append(champ)

            # Winner might be in metadata or we may need to infer it
            winner = metadata.get("winner", "blue")

            previous_results.append(
                {
                    "winner": winner,
                    "blue_comp": blue_comp,
                    "red_comp": red_comp,
                    "blue_bans": blue_bans,
                    "red_bans": red_bans,
                }
            )

        return SeriesContextBuilder.from_game_results(
            game_number=current_game_index + 1,
            previous_results=previous_results,
            our_side=our_side,
        )

    @staticmethod
    def _extract_tendencies(
        games: list[PreviousGameSummary],
        side: Literal["blue", "red"],
    ) -> TeamTendencies:
        """Extract team tendencies from game history.

        Args:
            games: List of previous game summaries
            side: Which side to extract tendencies for

        Returns:
            TeamTendencies with identified patterns
        """
        if not games:
            return TeamTendencies()

        # Track champion picks across all games
        all_picks: list[str] = []
        first_picks: list[str] = []
        bans_received: list[str] = []

        opponent_side: Literal["blue", "red"] = "red" if side == "blue" else "blue"

        for game in games:
            if side == "blue":
                comp = game.blue_comp
                opponent_bans = game.red_bans
            else:
                comp = game.red_comp
                opponent_bans = game.blue_bans

            all_picks.extend(comp)
            if comp:
                first_picks.append(comp[0])
            bans_received.extend(opponent_bans)

        # Find champions picked multiple times (prioritized)
        pick_counts = Counter(all_picks)
        prioritized = [champ for champ, count in pick_counts.items() if count >= 2]

        # Find consistent first pick patterns
        first_pick_counts = Counter(first_picks)
        first_pick_patterns = [
            champ for champ, count in first_pick_counts.items() if count >= 2
        ]

        # Find champions opponents have banned multiple times
        ban_counts = Counter(bans_received)
        targeted_bans = [champ for champ, count in ban_counts.items() if count >= 2]

        return TeamTendencies(
            prioritized_champions=prioritized,
            first_pick_patterns=first_pick_patterns,
            banned_against_them=targeted_bans,
        )
