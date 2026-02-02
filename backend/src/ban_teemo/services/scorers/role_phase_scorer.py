"""Role-phase prior scorer based on pro pick order data."""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RolePhaseScorer:
    """Applies role-phase prior multipliers based on pro pick order data.

    Pro teams have empirical patterns for when they pick each role:
    - Support: Typically picked late (phase 2) - 32% vs 8% in early P1
    - Jungle/Mid: Often picked early when high priority
    - Top/Bot: More evenly distributed across phases

    This scorer applies penalty multipliers (capped at 1.0) to recommendations
    based on these empirical probabilities. Champions in roles that are
    atypical for the current phase get penalized.
    """

    UNIFORM_PROB = 0.20  # 1/5 roles - expected if all roles equally likely

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self.distribution: dict[str, dict[str, float]] = {}
        self._load_distribution()

    def _load_distribution(self) -> None:
        """Load role pick phase distribution from knowledge file."""
        dist_path = self.knowledge_dir / "role_pick_phase.json"
        if dist_path.exists():
            try:
                with open(dist_path) as f:
                    self.distribution = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load role_pick_phase.json: {e}")
                self.distribution = {}
        else:
            logger.warning(f"role_pick_phase.json not found at {dist_path}")
            self.distribution = {}

    def get_multiplier(self, role: str, total_picks: int) -> float:
        """Get penalty multiplier for role at current draft phase.

        Args:
            role: The role being considered (top, jungle, mid, bot, support)
            total_picks: Total picks made by both teams (0-9)

        Returns:
            Multiplier between 0.4 and 1.0 (penalty-only, no boost)

        Phase mapping:
            - early_p1: picks 0-2 (first 3 picks)
            - late_p1: picks 3-5 (picks 4-6)
            - p2: picks 6-9 (phase 2)
        """
        if not self.distribution:
            return 1.0  # No data - no penalty

        phase = self._get_phase(total_picks)
        role_lower = role.lower() if role else ""

        role_data = self.distribution.get(role_lower, {})
        empirical = role_data.get(phase, self.UNIFORM_PROB)

        # Penalty-only: cap at 1.0 (no boost for above-average phases)
        return min(1.0, empirical / self.UNIFORM_PROB)

    def _get_phase(self, total_picks: int) -> str:
        """Map total picks to draft phase.

        Args:
            total_picks: Total picks made by both teams (0-9)

        Returns:
            Phase string: "early_p1", "late_p1", or "p2"
        """
        if total_picks <= 2:
            return "early_p1"
        elif total_picks <= 5:
            return "late_p1"
        return "p2"

    def get_distribution(self, role: str) -> dict[str, float]:
        """Get full distribution for a role (for debugging/display).

        Args:
            role: The role to get distribution for

        Returns:
            Dict mapping phase -> probability
        """
        role_lower = role.lower() if role else ""
        return self.distribution.get(role_lower, {})
