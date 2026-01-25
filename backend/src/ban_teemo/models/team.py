"""Team and player models."""

from dataclasses import dataclass


@dataclass
class Player:
    """A player in a specific game."""

    id: str
    name: str
    role: str  # TOP, JNG, MID, ADC, SUP


@dataclass
class TeamContext:
    """Team information for a specific game."""

    id: str
    name: str
    side: str  # "blue" or "red"
    players: list[Player]
