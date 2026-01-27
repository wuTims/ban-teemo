"""Player proficiency scoring with confidence tracking."""
import json
from pathlib import Path
from typing import Optional


class ProficiencyScorer:
    """Scores player proficiency on champions."""

    CONFIDENCE_THRESHOLDS = {"HIGH": 8, "MEDIUM": 4, "LOW": 1}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[5] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._proficiency_data: dict = {}
        self._load_data()

    def _load_data(self):
        """Load player proficiency data."""
        prof_path = self.knowledge_dir / "player_proficiency.json"
        if prof_path.exists():
            with open(prof_path) as f:
                data = json.load(f)
                self._proficiency_data = data.get("proficiencies", {})

    def get_proficiency_score(self, player_name: str, champion_name: str) -> tuple[float, str]:
        """Get proficiency score and confidence for player-champion pair."""
        if player_name not in self._proficiency_data:
            return 0.5, "NO_DATA"

        player_data = self._proficiency_data[player_name]
        if champion_name not in player_data:
            return 0.5, "NO_DATA"

        champ_data = player_data[champion_name]
        games = champ_data.get("games_raw", champ_data.get("games_weighted", 0))
        win_rate = champ_data.get("win_rate_weighted", champ_data.get("win_rate", 0.5))

        games_factor = min(1.0, games / 10)
        score = win_rate * 0.6 + games_factor * 0.4
        confidence = champ_data.get("confidence") or self._games_to_confidence(int(games))

        return round(score, 3), confidence

    def _games_to_confidence(self, games: int) -> str:
        """Convert game count to confidence level."""
        if games >= self.CONFIDENCE_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif games >= self.CONFIDENCE_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        elif games >= self.CONFIDENCE_THRESHOLDS["LOW"]:
            return "LOW"
        return "NO_DATA"

    def get_player_champion_pool(self, player_name: str, min_games: int = 1) -> list[dict]:
        """Get a player's champion pool sorted by proficiency."""
        if player_name not in self._proficiency_data:
            return []

        pool = []
        for champ, data in self._proficiency_data[player_name].items():
            games = data.get("games_raw", 0)
            if games >= min_games:
                score, conf = self.get_proficiency_score(player_name, champ)
                pool.append({"champion": champ, "score": score, "games": games, "confidence": conf})

        return sorted(pool, key=lambda x: -x["score"])
