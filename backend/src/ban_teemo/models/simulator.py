"""Models for draft simulator sessions."""

import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from ban_teemo.models.draft import DraftAction, DraftState
from ban_teemo.models.team import TeamContext


@dataclass
class EnemyStrategy:
    """Enemy team's draft strategy based on historical data."""

    reference_game_id: str
    draft_script: list[DraftAction]
    fallback_game_ids: list[str]
    champion_weights: dict[str, float]
    # Maps game_id -> team_side for filtering fallback actions correctly
    game_team_sides: dict[str, str] = field(default_factory=dict)
    current_script_index: int = 0


@dataclass
class GameResult:
    """Result of a completed game in a series."""

    game_number: int
    winner: Literal["blue", "red"]
    blue_comp: list[str]
    red_comp: list[str]
    blue_bans: list[str] = field(default_factory=list)
    red_bans: list[str] = field(default_factory=list)


@dataclass
class SimulatorSession:
    """State for an active simulator session."""

    session_id: str
    blue_team: TeamContext
    red_team: TeamContext
    coaching_side: Literal["blue", "red"]
    series_length: Literal[1, 3, 5]
    draft_mode: Literal["normal", "fearless"]
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)

    # Current game state
    current_game: int = 1
    draft_state: Optional[DraftState] = None
    enemy_strategy: Optional[EnemyStrategy] = None

    # Series tracking
    game_results: list[GameResult] = field(default_factory=list)
    # Fearless tracking - preserves team and game info for UI tooltips
    # Structure: {"Azir": {"team": "blue", "game": 1}, ...}
    fearless_blocked: dict[str, dict] = field(default_factory=dict)

    @property
    def fearless_blocked_set(self) -> set[str]:
        """All fearless-blocked champion names as a set for filtering."""
        return set(self.fearless_blocked.keys())

    @property
    def enemy_side(self) -> Literal["blue", "red"]:
        return "red" if self.coaching_side == "blue" else "blue"

    @property
    def series_score(self) -> tuple[int, int]:
        blue_wins = sum(1 for r in self.game_results if r.winner == "blue")
        red_wins = sum(1 for r in self.game_results if r.winner == "red")
        return blue_wins, red_wins

    @property
    def series_complete(self) -> bool:
        blue_wins, red_wins = self.series_score
        wins_needed = (self.series_length // 2) + 1
        return blue_wins >= wins_needed or red_wins >= wins_needed
