"""Flex pick role resolution with probability estimation."""
import json
from pathlib import Path
from typing import Optional


class FlexResolver:
    """Resolves flex pick role probabilities."""

    VALID_ROLES = {"TOP", "JUNGLE", "MID", "ADC", "SUP"}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._flex_data: dict = {}
        self._load_data()

    def _load_data(self):
        """Load flex champion data."""
        flex_path = self.knowledge_dir / "flex_champions.json"
        if flex_path.exists():
            with open(flex_path) as f:
                data = json.load(f)
                self._flex_data = data.get("flex_picks", {})

    def get_role_probabilities(
        self, champion_name: str, filled_roles: Optional[set[str]] = None
    ) -> dict[str, float]:
        """Get role probability distribution for a champion."""
        filled = filled_roles or set()

        if champion_name not in self._flex_data:
            available = self.VALID_ROLES - filled
            if not available:
                return {}
            prob = 1.0 / len(available)
            return {role: prob for role in available}

        data = self._flex_data[champion_name]
        probs = {}
        for role in self.VALID_ROLES:
            if role not in filled:
                probs[role] = data.get(role, 0)

        total = sum(probs.values())
        if total > 0:
            probs = {role: p / total for role, p in probs.items()}
        elif probs:
            prob = 1.0 / len(probs)
            probs = {role: prob for role in probs}

        return probs

    def is_flex_pick(self, champion_name: str) -> bool:
        """Check if champion is a flex pick."""
        if champion_name not in self._flex_data:
            return False
        return self._flex_data[champion_name].get("is_flex", False)
