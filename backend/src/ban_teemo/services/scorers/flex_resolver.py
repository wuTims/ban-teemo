"""Flex pick role resolution with probability estimation."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import (
    normalize_role as util_normalize_role,
    CANONICAL_ROLES,
    ROLE_ORDER,
)


class FlexResolver:
    """Resolves flex pick role probabilities."""

    # Canonical output roles - lowercase: top, jungle, mid, bot, support
    VALID_ROLES = CANONICAL_ROLES

    # Minimum probability threshold to consider a role viable (>5%)
    # Filters out noise like Viego's 2% support or Rumble's 2% support
    # Using 0.051 to ensure exact 5% (like Nocturne SUP) is filtered out
    MIN_ROLE_PROBABILITY = 0.051

    # Map data file formats (from knowledge files) to canonical lowercase format
    DATA_TO_CANONICAL = {
        "JUNGLE": "jungle",
        "jungle": "jungle",
        "JNG": "jungle",
        "TOP": "top",
        "top": "top",
        "MID": "mid",
        "mid": "mid",
        "MIDDLE": "mid",
        "ADC": "bot",
        "adc": "bot",
        "BOT": "bot",
        "bot": "bot",
        "BOTTOM": "bot",
        "SUP": "support",
        "sup": "support",
        "SUPPORT": "support",
        "support": "support",
    }

    # Default role order for deterministic fallback (most common roles first)
    DEFAULT_ROLE_ORDER = ["mid", "bot", "top", "jungle", "support"]

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._flex_data: dict = {}
        self._role_history: dict = {}
        self._load_data()

    def _load_data(self):
        """Load flex champion data and role history for fallback."""
        # Primary: flex_champions.json
        flex_path = self.knowledge_dir / "flex_champions.json"
        if flex_path.exists():
            with open(flex_path) as f:
                data = json.load(f)
                self._flex_data = data.get("flex_picks", {})

        # Fallback: champion_role_history.json for unknown champions
        # Schema: {"champions": {"Aatrox": {"canonical_role": "TOP", ...}, ...}}
        history_path = self.knowledge_dir / "champion_role_history.json"
        if history_path.exists():
            with open(history_path) as f:
                data = json.load(f)
                for champ, champ_data in data.get("champions", {}).items():
                    if isinstance(champ_data, dict):
                        # Use canonical_role field directly
                        role = champ_data.get("canonical_role") or champ_data.get("pro_play_primary_role")
                        if role:
                            canonical = self.DATA_TO_CANONICAL.get(role, role)
                            if canonical in self.VALID_ROLES:
                                self._role_history[champ] = canonical

    def get_role_probabilities(
        self, champion_name: str, filled_roles: Optional[set[str]] = None
    ) -> dict[str, float]:
        """Get role probability distribution for a champion.

        Returns probabilities using canonical role names (top, jungle, mid, bot, support).
        For unknown champions, uses champion_role_history.json as fallback.
        """
        # Normalize filled_roles to canonical lowercase
        filled = set()
        if filled_roles:
            for role in filled_roles:
                normalized = util_normalize_role(role)
                if normalized:
                    filled.add(normalized)

        if champion_name in self._flex_data:
            data = self._flex_data[champion_name]
            probs = {}
            # Map from data file keys (uppercase) to canonical lowercase
            data_key_map = {
                "top": "TOP",
                "jungle": "JUNGLE",
                "mid": "MID",
                "bot": "ADC",
                "support": "SUP",
            }
            for role in self.VALID_ROLES:
                if role not in filled:
                    data_key = data_key_map.get(role, role.upper())
                    raw_prob = data.get(data_key, 0)
                    # Filter out roles below minimum threshold to avoid suggesting
                    # champions for roles they rarely/never play (e.g., Viego support at 2%)
                    if raw_prob >= self.MIN_ROLE_PROBABILITY:
                        probs[role] = raw_prob

            total = sum(probs.values())
            if total > 0:
                probs = {role: p / total for role, p in probs.items()}
                return probs
            # All unfilled roles have probability below threshold - champion can't fit
            return {}

        # Fallback: use role history if available
        if champion_name in self._role_history:
            primary_role = self._role_history[champion_name]
            if primary_role not in filled:
                return {primary_role: 1.0}
            # Primary role is filled - champion can't play other roles unless we have
            # explicit flex data (which we don't since we're in the fallback path).
            # Return empty dict to prevent suggesting champions for impossible roles.
            return {}

        # Ultimate fallback: deterministic assignment based on DEFAULT_ROLE_ORDER
        # This ensures consistent behavior for completely unknown champions
        for role in self.DEFAULT_ROLE_ORDER:
            if role not in filled:
                return {role: 1.0}
        return {}

    def is_flex_pick(self, champion_name: str) -> bool:
        """Check if champion is a flex pick."""
        if champion_name not in self._flex_data:
            return False
        return self._flex_data[champion_name].get("is_flex", False)

    def normalize_role(self, role: str) -> str:
        """Normalize role name to canonical form (top, jungle, mid, bot, support)."""
        return util_normalize_role(role) or role.lower()
