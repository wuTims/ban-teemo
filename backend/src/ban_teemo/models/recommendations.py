"""Recommendation models for draft suggestions."""

from collections import defaultdict
from dataclasses import asdict, dataclass, field


@dataclass
class PickRecommendation:
    """A recommended champion pick."""

    champion_name: str
    confidence: float  # 0.0 - 1.0
    suggested_role: str | None = None  # Lowercase canonical: top/jungle/mid/bot/support
    flag: str | None = None  # "SURPRISE_PICK", "LOW_CONFIDENCE", None
    reasons: list[str] = field(default_factory=list)
    # Score breakdown fields
    score: float = 0.0  # Final combined score
    base_score: float | None = None  # Pre-synergy score
    synergy_multiplier: float | None = None  # Synergy factor applied
    components: dict[str, float] = field(default_factory=dict)  # Individual score components
    # Proficiency tracking
    proficiency_source: str | None = None  # "direct", "comfort_only", "none"
    proficiency_player: str | None = None  # Player name for this role


@dataclass
class BanRecommendation:
    """A recommended champion ban."""

    champion_name: str
    priority: float  # 0.0 - 1.0
    target_player: str | None = None  # Who we're targeting with this ban
    reasons: list[str] = field(default_factory=list)
    # Score breakdown fields
    components: dict[str, float] = field(default_factory=dict)  # Individual priority components


@dataclass
class Recommendations:
    """Collection of recommendations for a team."""

    for_team: str  # "blue" or "red"
    picks: list[PickRecommendation] = field(default_factory=list)
    bans: list[BanRecommendation] = field(default_factory=list)


@dataclass
class RoleGroupedRecommendations:
    """Recommendations grouped by role for display.

    This is a SUPPLEMENTAL view alongside the primary top-5 recommendations.
    Use cases:
    - Late draft when a specific role must be filled
    - Draft planning to compare options across roles
    - 'What if' analysis for alternative picks
    """

    by_role: dict[str, list[PickRecommendation]] = field(default_factory=dict)

    @classmethod
    def from_picks(
        cls,
        picks: list[PickRecommendation],
        limit_per_role: int = 2,
    ) -> "RoleGroupedRecommendations":
        """Group picks by suggested_role, keeping top N per role."""
        by_role: dict[str, list[PickRecommendation]] = defaultdict(list)

        # Sort by score descending
        sorted_picks = sorted(picks, key=lambda p: p.score, reverse=True)

        for pick in sorted_picks:
            role = pick.suggested_role or "unknown"
            if len(by_role[role]) < limit_per_role:
                by_role[role].append(pick)

        return cls(by_role=dict(by_role))

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON response."""
        return {
            "by_role": {
                role: [asdict(pick) for pick in picks]
                for role, picks in self.by_role.items()
            }
        }
