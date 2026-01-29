"""Flex pick role resolution with probability estimation."""
import json
from pathlib import Path
from typing import Optional


class FlexResolver:
    """Resolves flex pick role probabilities."""

    # Canonical output roles (what the app uses)
    VALID_ROLES = {"TOP", "JNG", "MID", "ADC", "SUP"}

    # Map data file formats to canonical format
    DATA_TO_CANONICAL = {
        "JUNGLE": "JNG",
        "jungle": "JNG",
        "TOP": "TOP",
        "top": "TOP",
        "MID": "MID",
        "mid": "MID",
        "MIDDLE": "MID",
        "ADC": "ADC",
        "adc": "ADC",
        "BOT": "ADC",
        "bot": "ADC",
        "BOTTOM": "ADC",
        "SUP": "SUP",
        "sup": "SUP",
        "SUPPORT": "SUP",
        "support": "SUP",
    }

    # For normalize_role() - accepts various inputs, outputs canonical
    ROLE_ALIASES = {
        "JNG": "JNG",
        "JUNGLE": "JNG",
        "jungle": "JNG",
        "JG": "JNG",
        "TOP": "TOP",
        "top": "TOP",
        "MID": "MID",
        "mid": "MID",
        "MIDDLE": "MID",
        "ADC": "ADC",
        "adc": "ADC",
        "BOT": "ADC",
        "bot": "ADC",
        "BOTTOM": "ADC",
        "SUP": "SUP",
        "sup": "SUP",
        "SUPPORT": "SUP",
        "support": "SUP",
    }

    # Default role order for deterministic fallback (most common roles first)
    DEFAULT_ROLE_ORDER = ["MID", "ADC", "TOP", "JNG", "SUP"]

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

        Returns probabilities using canonical role names (TOP, JNG, MID, ADC, SUP).
        For unknown champions, uses champion_role_history.json as fallback.
        """
        filled = filled_roles or set()

        if champion_name in self._flex_data:
            data = self._flex_data[champion_name]
            probs = {}
            for role in self.VALID_ROLES:
                if role not in filled:
                    # Data uses JUNGLE, we output JNG
                    data_key = "JUNGLE" if role == "JNG" else role
                    probs[role] = data.get(data_key, 0)

            total = sum(probs.values())
            if total > 0:
                probs = {role: p / total for role, p in probs.items()}
                return probs
            # All unfilled roles have 0 probability - champion can't fit any unfilled role
            return {}

        # Fallback: use role history if available
        if champion_name in self._role_history:
            primary_role = self._role_history[champion_name]
            if primary_role not in filled:
                return {primary_role: 1.0}
            # Primary is filled, return uniform over remaining
            available = self.VALID_ROLES - filled
            if available:
                prob = 1.0 / len(available)
                return {role: prob for role in available}
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
        """Normalize role name to canonical form (TOP, JNG, MID, ADC, SUP)."""
        return self.ROLE_ALIASES.get(role, self.ROLE_ALIASES.get(role.upper(), role.upper()))
