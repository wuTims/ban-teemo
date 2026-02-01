"""Series context models for multi-game series awareness.

These models capture information about previous games in a series,
enabling the LLM reranker to make more strategic recommendations
based on observed patterns and tendencies.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class PreviousGameSummary:
    """Summary of a completed game in the series."""

    game_number: int
    winner: Literal["blue", "red"]
    blue_comp: list[str]
    red_comp: list[str]
    blue_bans: list[str]
    red_bans: list[str]


@dataclass
class TeamTendencies:
    """Observed tendencies for a team across the series.

    Identifies patterns that can inform draft strategy for subsequent games.
    """

    prioritized_champions: list[str] = field(default_factory=list)
    """Champions picked in multiple games - high priority for the team."""

    first_pick_patterns: list[str] = field(default_factory=list)
    """Champions frequently used as first picks."""

    banned_against_them: list[str] = field(default_factory=list)
    """Champions opponents have banned against this team."""


@dataclass
class SeriesContext:
    """Context for the current game within a series.

    Provides historical information about previous games in the series,
    including team compositions, bans, and identified tendencies.
    """

    game_number: int
    """Current game number (1-indexed)."""

    series_score: tuple[int, int]
    """Current series score as (blue_wins, red_wins)."""

    previous_games: list[PreviousGameSummary] = field(default_factory=list)
    """Summaries of all previous games in the series."""

    our_tendencies: Optional[TeamTendencies] = None
    """Our observed tendencies across the series."""

    enemy_tendencies: Optional[TeamTendencies] = None
    """Enemy's observed tendencies across the series."""

    @property
    def is_series_context_available(self) -> bool:
        """Check if there's meaningful series context to use.

        Returns True if this is game 2+ and we have previous game data.
        """
        return self.game_number > 1 and len(self.previous_games) > 0
