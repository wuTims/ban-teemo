"""Matchup calculation with flex pick uncertainty handling."""
import json
from pathlib import Path
from typing import Optional

from ban_teemo.utils.role_normalizer import normalize_role


class MatchupCalculator:
    """Calculates matchup scores between champions."""

    # Translate canonical lowercase roles to data file roles
    ROLE_TO_DATA = {
        "top": "TOP",
        "jungle": "JUNGLE",
        "mid": "MID",
        "bot": "ADC",
        "support": "SUP",
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
        """Get lane-specific matchup score.

        Uses a two-step lookup strategy to maximize data coverage:

        1. DIRECT LOOKUP: our_champion vs enemy_champion
           Returns the stored win_rate directly (our perspective).

        2. REVERSE LOOKUP: enemy_champion vs our_champion, then INVERT
           If direct lookup fails, check if we have enemy's perspective.
           Inversion (1.0 - win_rate) is valid because matchup win rates
           are complementary: if A beats B 60%, then B beats A 40%.

        WHY INVERSION WORKS:
        Win rate in a 1v1 matchup is zero-sum. If Darius has 55% win rate
        vs Garen (from Darius's perspective), then Garen has 45% win rate
        vs Darius. The inversion assumes matchup data captures this
        symmetry, which holds for same-role lane matchups.

        LIMITATION: Team-wide effects (jungle pressure, roams) can break
        symmetry, but for lane phase estimation, inversion is accurate.
        """
        # Normalize role and translate to data format
        normalized_role = normalize_role(role) or role.lower()
        data_role = self.ROLE_TO_DATA.get(normalized_role, role.upper())

        # Direct lookup: our_champion vs enemy_champion
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

        # Reverse lookup: enemy_champion vs our_champion, then invert
        # Inversion: if enemy has 60% vs us, we have 40% vs them
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
        """Get team-level matchup (champion vs champion regardless of lane).

        Same lookup strategy as get_lane_matchup (direct then reverse with
        inversion). Team matchups capture how champions perform against each
        other across all game phases, not just lane.

        INVERSION VALIDITY: Same principle as lane matchups - if Azir has
        55% win rate in games with enemy Zed, then Zed has 45% in games
        with enemy Azir. Team-level effects are captured in the original
        data, so inversion remains valid.
        """
        # Direct lookup: our_champion vs enemy_champion
        if our_champion in self._counters:
            vs_team = self._counters[our_champion].get("vs_team", {})
            if enemy_champion in vs_team:
                matchup = vs_team[enemy_champion]
                return {
                    "score": matchup.get("win_rate", 0.5),
                    "games": matchup.get("games", 0),
                    "data_source": "direct_lookup"
                }

        # Reverse lookup: enemy_champion vs our_champion, then invert
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
