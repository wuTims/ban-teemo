"""Meta strength scorer based on pick/ban presence and win rate."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import normalize_role


class MetaScorer:
    """Scores champions based on current meta strength."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._meta_stats: dict = {}
        self._champion_roles: dict = {}
        self._load_data()

    def _load_data(self):
        """Load meta stats and champion role data."""
        # Load meta stats
        meta_path = self.knowledge_dir / "meta_stats.json"
        if meta_path.exists():
            with open(meta_path) as f:
                data = json.load(f)
                self._meta_stats = data.get("champions", {})

        # Load champion role history for role filtering
        role_path = self.knowledge_dir / "champion_role_history.json"
        if role_path.exists():
            with open(role_path) as f:
                data = json.load(f)
                self._champion_roles = data.get("champions", {})

    def get_meta_score(self, champion_name: str) -> float:
        """Get meta strength score for a champion (0.0-1.0)."""
        if champion_name not in self._meta_stats:
            return 0.5
        score = self._meta_stats[champion_name].get("meta_score")
        return score if score is not None else 0.5

    def get_meta_tier(self, champion_name: str) -> Optional[str]:
        """Get meta tier (S/A/B/C/D) for a champion."""
        if champion_name not in self._meta_stats:
            return None
        return self._meta_stats[champion_name].get("meta_tier")

    def get_top_meta_champions(self, role: Optional[str] = None, limit: int = 10) -> list[str]:
        """Get top meta champions sorted by meta_score.

        Args:
            role: Optional role filter (top, jungle, mid, bot, support).
                  Supports aliases like JNG, ADC, SUP, JUNGLE, SUPPORT, BOT.
            limit: Maximum number of champions to return.

        Returns:
            List of champion names sorted by meta score.
        """
        # Filter by role if specified
        if role:
            normalized_role = normalize_role(role)
            if normalized_role:
                filtered_champs = [
                    (name, stats)
                    for name, stats in self._meta_stats.items()
                    if self._champion_plays_role(name, normalized_role)
                ]
            else:
                filtered_champs = list(self._meta_stats.items())
        else:
            filtered_champs = list(self._meta_stats.items())

        ranked = sorted(
            filtered_champs,
            key=lambda x: x[1].get("meta_score") or 0,
            reverse=True
        )
        return [name for name, _ in ranked[:limit]]

    # Map from canonical lowercase roles to all possible data file formats
    ROLE_DATA_FORMATS = {
        "top": ["TOP"],
        "jungle": ["JNG", "JUNGLE"],
        "mid": ["MID", "MIDDLE"],
        "bot": ["ADC", "BOT", "BOTTOM"],
        "support": ["SUP", "SUPPORT"],
    }

    def _champion_plays_role(self, champion_name: str, role: str) -> bool:
        """Check if a champion plays a specific role.

        Uses canonical_role as primary, with all_time_distribution as fallback.

        Args:
            champion_name: The champion name
            role: Canonical role (top, jungle, mid, bot, support)
        """
        if champion_name not in self._champion_roles:
            # No role data - include by default
            return True

        champ_data = self._champion_roles[champion_name]

        # Get all possible data file formats for this canonical role
        role_formats = self.ROLE_DATA_FORMATS.get(role, [role.upper()])

        # Check canonical role first
        canonical = champ_data.get("canonical_role") or ""
        if canonical and canonical.upper() in role_formats:
            return True

        # Check all canonical roles (for flex picks)
        canonical_all = champ_data.get("canonical_all", [])
        for r in canonical_all:
            if r and r.upper() in role_formats:
                return True

        # Check all-time distribution for flex picks
        # Include if played in role >= 10% of games
        distribution = champ_data.get("all_time_distribution", {})
        for role_format in role_formats:
            if distribution.get(role_format, 0) >= 0.1:
                return True

        return False
