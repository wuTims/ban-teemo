"""Tournament meta scorer based on recent pro tournament data."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import normalize_role


class TournamentScorer:
    """Scores champions based on recent tournament pick/ban data.

    Provides two distinct scoring signals:
    - tournament_priority: Role-agnostic contestation (how often pros pick/ban)
    - tournament_performance: Role-specific winrate with sample-size adjustment

    Can load data from custom files for historical replay support.
    """

    def __init__(self, knowledge_dir: Optional[Path] = None, data_file: Optional[str] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._data_file = data_file or "tournament_meta.json"
        self._tournament_data: dict = {}
        self._defaults: dict = {}
        self._metadata: dict = {}
        self._load_data()

    def _load_data(self):
        """Load tournament meta data with fallback to default."""
        tournament_path = self.knowledge_dir / self._data_file

        # Try custom file first, fall back to default
        if not tournament_path.exists() and self._data_file != "tournament_meta.json":
            fallback_path = self.knowledge_dir / "tournament_meta.json"
            if fallback_path.exists():
                tournament_path = fallback_path

        if tournament_path.exists():
            with open(tournament_path) as f:
                data = json.load(f)
                self._tournament_data = data.get("champions", {})
                self._defaults = data.get("defaults", {})
                self._metadata = data.get("metadata", {})

    def get_priority(self, champion_name: str) -> float:
        """Get role-agnostic priority score (0.0-1.0).

        Priority represents how often pros contest this champion (picks + bans).
        Higher values mean pros value this champion more regardless of role.

        Args:
            champion_name: Champion to score

        Returns:
            Float 0.0-1.0 representing tournament priority.
            Returns missing_champion_priority penalty if champion not in data.
        """
        if champion_name not in self._tournament_data:
            return self._defaults.get("missing_champion_priority", 0.05)

        return self._tournament_data[champion_name].get("priority", 0.05)

    def get_performance(self, champion_name: str, role: str) -> float:
        """Get role-specific adjusted performance score (0.0-1.0).

        Performance is the winrate adjusted for sample size:
        - High WR with low sample is blended toward 0.5 (reduce false optimism)
        - Low WR is preserved as a warning signal

        Args:
            champion_name: Champion to score
            role: Role to get performance for (e.g., "mid", "top")

        Returns:
            Float 0.0-1.0 representing adjusted tournament performance.
            Returns missing_champion_performance penalty if champion/role not in data.
        """
        default_perf = self._defaults.get("missing_champion_performance", 0.35)

        if champion_name not in self._tournament_data:
            return default_perf

        champ_data = self._tournament_data[champion_name]
        roles = champ_data.get("roles", {})

        normalized_role = normalize_role(role)
        if normalized_role not in roles:
            # Champion exists but not played in this role
            # Use a slightly higher penalty than missing entirely
            return default_perf

        return roles[normalized_role].get("adjusted_performance", default_perf)

    def get_tournament_scores(self, champion_name: str, role: str) -> dict:
        """Get both tournament scores plus metadata for UI display.

        Args:
            champion_name: Champion to score
            role: Role for performance lookup

        Returns:
            Dict with:
                - priority: Role-agnostic priority score
                - performance: Role-specific adjusted performance
                - has_data: Whether champion has tournament data
                - role_has_data: Whether champion has data for this specific role
                - picks: Number of picks in this role (for confidence display)
        """
        has_data = champion_name in self._tournament_data
        role_has_data = False
        picks = 0

        if has_data:
            champ_data = self._tournament_data[champion_name]
            roles = champ_data.get("roles", {})
            normalized_role = normalize_role(role)
            if normalized_role in roles:
                role_has_data = True
                picks = roles[normalized_role].get("picks", 0)

        return {
            "priority": self.get_priority(champion_name),
            "performance": self.get_performance(champion_name, role),
            "has_data": has_data,
            "role_has_data": role_has_data,
            "picks": picks,
        }

    def get_metadata(self) -> dict:
        """Get tournament data metadata (source, patch, etc.)."""
        tournament_path = self.knowledge_dir / "tournament_meta.json"
        if tournament_path.exists():
            with open(tournament_path) as f:
                data = json.load(f)
                return data.get("metadata", {})
        return {}

    def get_top_priority_champions(self, limit: int = 15) -> list[str]:
        """Get champions with highest tournament priority.

        Args:
            limit: Maximum number of champions to return

        Returns:
            List of champion names sorted by tournament priority (descending)
        """
        if not self._tournament_data:
            return []

        champions_by_priority = sorted(
            self._tournament_data.items(),
            key=lambda x: x[1].get("priority", 0),
            reverse=True
        )
        return [name for name, _ in champions_by_priority[:limit]]
