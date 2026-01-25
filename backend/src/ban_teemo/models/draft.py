"""Draft state and action models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ban_teemo.models.team import TeamContext


class DraftPhase(str, Enum):
    """Phases of a professional LoL draft."""

    BAN_PHASE_1 = "BAN_PHASE_1"  # Bans 1-6
    PICK_PHASE_1 = "PICK_PHASE_1"  # Picks 1-6
    BAN_PHASE_2 = "BAN_PHASE_2"  # Bans 7-10
    PICK_PHASE_2 = "PICK_PHASE_2"  # Picks 7-10
    COMPLETE = "COMPLETE"


@dataclass
class DraftAction:
    """A single ban or pick action in a draft."""

    sequence: int  # 1-20
    action_type: str  # "ban" or "pick"
    team_side: str  # "blue" or "red"
    champion_id: str
    champion_name: str


@dataclass
class DraftState:
    """Complete state of a draft at a point in time."""

    game_id: str
    series_id: str
    game_number: int
    patch_version: str
    match_date: datetime
    blue_team: TeamContext
    red_team: TeamContext
    actions: list[DraftAction] = field(default_factory=list)
    current_phase: DraftPhase = DraftPhase.BAN_PHASE_1
    next_team: str | None = "blue"
    next_action: str | None = "ban"

    @property
    def blue_bans(self) -> list[str]:
        """Champion names banned by blue team."""
        return [
            a.champion_name
            for a in self.actions
            if a.team_side == "blue" and a.action_type == "ban"
        ]

    @property
    def red_bans(self) -> list[str]:
        """Champion names banned by red team."""
        return [
            a.champion_name
            for a in self.actions
            if a.team_side == "red" and a.action_type == "ban"
        ]

    @property
    def blue_picks(self) -> list[str]:
        """Champion names picked by blue team."""
        return [
            a.champion_name
            for a in self.actions
            if a.team_side == "blue" and a.action_type == "pick"
        ]

    @property
    def red_picks(self) -> list[str]:
        """Champion names picked by red team."""
        return [
            a.champion_name
            for a in self.actions
            if a.team_side == "red" and a.action_type == "pick"
        ]
