"""Meta strength scorer based on pick/ban presence and win rate."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import normalize_role
from ban_teemo.utils.role_viability import extract_current_role_viability, CURRENT_ROLE_THRESHOLD


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

    def get_meta_score(self, champion_name: str, method: str = "hybrid") -> float:
        """Get meta strength score for a champion (0.0-1.0).

        Args:
            champion_name: Champion to score
            method: Scoring method
                - "default": Original tier-based score (penalizes low win rate)
                - "presence": Pure presence-based (0.3 + presence * 0.7)
                - "hybrid": Average of default and presence (best accuracy)

        Returns:
            Float 0.0-1.0 representing meta strength
        """
        if champion_name not in self._meta_stats:
            return 0.5

        stats = self._meta_stats[champion_name]

        if method == "default":
            score = stats.get("meta_score")
            return score if score is not None else 0.5

        elif method == "presence":
            presence = stats.get("presence", 0)
            # Scale presence (0-1) to meta score (0.3-1.0)
            return 0.3 + presence * 0.7

        else:  # "hybrid" - default
            # Average of original tier-based score and presence-based score
            # This balances win rate signal with pick frequency signal
            original_score = stats.get("meta_score")
            if original_score is None:
                original_score = 0.5

            presence = stats.get("presence", 0)
            presence_score = 0.3 + presence * 0.7

            return (original_score + presence_score) / 2

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

        Uses current viable roles when available, with all-time data as fallback.

        Args:
            champion_name: The champion name
            role: Canonical role (top, jungle, mid, bot, support)
        """
        if champion_name not in self._champion_roles:
            # No role data - include by default
            return True

        champ_data = self._champion_roles[champion_name]
        current_roles, has_current = extract_current_role_viability(
            champ_data, threshold=CURRENT_ROLE_THRESHOLD
        )
        if has_current:
            return role in (current_roles or set())

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

    def get_presence(self, champion_name: str) -> float:
        """Get champion's presence rate (pick_rate + ban_rate).

        Presence indicates how contested a champion is in the meta.

        Returns:
            Float 0.0-1.0 representing presence rate
        """
        if champion_name not in self._meta_stats:
            return 0.0
        return self._meta_stats[champion_name].get("presence", 0.0)

    def get_blind_pick_safety(self, champion_name: str) -> float:
        """Get blind pick safety factor for a champion.

        Based on pick_context data:
        - Counter-pick dependent champions are penalized for blind picking
        - Champions with high blind_early_win_rate are rewarded

        Returns:
            Float 0.7-1.1 as a multiplier (1.0 = neutral)
        """
        if champion_name not in self._meta_stats:
            return 1.0  # Neutral for unknown

        meta_data = self._meta_stats[champion_name]
        pick_context = meta_data.get("pick_context", {})

        if not pick_context:
            return 1.0

        # Check if counter-pick dependent
        is_counter_dependent = pick_context.get("is_counter_pick_dependent", False)
        if is_counter_dependent:
            return 0.85  # Penalty for blind picking counter-dependent champs

        # Use blind early win rate to determine safety
        blind_wr = pick_context.get("blind_early_win_rate")
        if blind_wr is not None:
            # Scale 0.7-1.1 based on win rate (0.4-0.6 range)
            # 0.5 WR = 1.0 safety, 0.6 WR = 1.1, 0.4 WR = 0.9
            return 0.9 + (blind_wr - 0.5) * 0.4

        return 1.0
