"""Matchup calculation with flex pick uncertainty handling."""
import json
from pathlib import Path
from typing import Optional


class MatchupCalculator:
    """Calculates matchup scores between champions."""

    # Translate canonical app roles to data file roles
    ROLE_TO_DATA = {
        "JNG": "JUNGLE",
        "TOP": "TOP",
        "MID": "MID",
        "ADC": "ADC",
        "SUP": "SUP",
    }

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._counters: dict = {}
        self._load_data()

    def _load_data(self):
        """Load matchup statistics."""
        matchup_path = self.knowledge_dir / "matchup_stats.json"
        if matchup_path.exists():
            with open(matchup_path) as f:
                data = json.load(f)
                self._counters = data.get("counters", {})

    def get_lane_matchup(self, our_champion: str, enemy_champion: str, role: str) -> dict:
        """Get lane-specific matchup score."""
        # Translate canonical role (JNG) to data role (JUNGLE)
        data_role = self.ROLE_TO_DATA.get(role.upper(), role.upper())

        # Direct lookup
        if our_champion in self._counters:
            vs_lane = self._counters[our_champion].get("vs_lane", {})
            role_data = vs_lane.get(data_role, {})
            if enemy_champion in role_data:
                matchup = role_data[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup (invert)
        if enemy_champion in self._counters:
            vs_lane = self._counters[enemy_champion].get("vs_lane", {})
            role_data = vs_lane.get(data_role, {})
            if our_champion in role_data:
                matchup = role_data[our_champion]
                return {
                    "score": round(1.0 - matchup.get("win_rate", 0.5), 3),
                    "confidence": matchup.get("confidence", "MEDIUM"),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {"score": 0.5, "confidence": "NO_DATA", "games": 0, "data_source": "none"}

    def get_team_matchup(self, our_champion: str, enemy_champion: str) -> dict:
        """Get team-level matchup."""
        # Direct lookup
        if our_champion in self._counters:
            vs_team = self._counters[our_champion].get("vs_team", {})
            if enemy_champion in vs_team:
                matchup = vs_team[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup
        if enemy_champion in self._counters:
            vs_team = self._counters[enemy_champion].get("vs_team", {})
            if our_champion in vs_team:
                matchup = vs_team[our_champion]
                return {
                    "score": round(1.0 - matchup.get("win_rate", 0.5), 3),
                    "games": matchup.get("games", 0),
                    "data_source": "reverse_lookup"
                }

        return {"score": 0.5, "games": 0, "data_source": "none"}
