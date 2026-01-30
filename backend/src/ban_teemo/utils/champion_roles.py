"""Champion role lookup utilities."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import normalize_role


class ChampionRoleLookup:
    """Lookup champion primary roles from role history data."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._role_data: dict = {}
        self._load_data()

    def _load_data(self):
        """Load champion role history."""
        path = self.knowledge_dir / "champion_role_history.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                self._role_data = data.get("champions", {})

    def get_primary_role(self, champion_name: str) -> Optional[str]:
        """Get champion's primary role (normalized lowercase).

        Priority:
        1. Single current_viable_role
        2. Highest in current_distribution
        3. canonical_role
        4. None if no data
        """
        champ_data = self._role_data.get(champion_name, {})
        if not champ_data:
            return None

        # Priority 1: Single current viable role
        current_viable = champ_data.get("current_viable_roles", [])
        if len(current_viable) == 1:
            return normalize_role(current_viable[0])

        # Priority 2: Highest in current_distribution
        dist = champ_data.get("current_distribution", {})
        if dist:
            # Sort by value desc, then key asc for determinism
            sorted_roles = sorted(dist.items(), key=lambda x: (-x[1], x[0]))
            if sorted_roles:
                return normalize_role(sorted_roles[0][0])

        # Priority 3: Canonical role
        canonical = champ_data.get("canonical_role")
        if canonical:
            return normalize_role(canonical)

        return None


# Module-level convenience function
_default_lookup: Optional[ChampionRoleLookup] = None


def get_champion_primary_role(champion_name: str) -> Optional[str]:
    """Get champion's primary role using default lookup."""
    global _default_lookup
    if _default_lookup is None:
        _default_lookup = ChampionRoleLookup()
    return _default_lookup.get_primary_role(champion_name)
