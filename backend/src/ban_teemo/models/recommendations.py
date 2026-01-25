"""Recommendation models for draft suggestions."""

from dataclasses import dataclass, field


@dataclass
class PickRecommendation:
    """A recommended champion pick."""

    champion_name: str
    confidence: float  # 0.0 - 1.0
    flag: str | None = None  # "SURPRISE_PICK", "LOW_CONFIDENCE", None
    reasons: list[str] = field(default_factory=list)


@dataclass
class BanRecommendation:
    """A recommended champion ban."""

    champion_name: str
    priority: float  # 0.0 - 1.0
    target_player: str | None = None  # Who we're targeting with this ban
    reasons: list[str] = field(default_factory=list)


@dataclass
class Recommendations:
    """Collection of recommendations for a team."""

    for_team: str  # "blue" or "red"
    picks: list[PickRecommendation] = field(default_factory=list)
    bans: list[BanRecommendation] = field(default_factory=list)
