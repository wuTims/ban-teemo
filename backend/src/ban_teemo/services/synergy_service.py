"""Synergy scoring with curated ratings and statistical fallback."""
import json
from pathlib import Path
from typing import Optional


class SynergyService:
    """Scores champion synergies."""

    RATING_MULTIPLIERS = {"S": 1.0, "A": 0.8, "B": 0.6, "C": 0.4}
    BASE_CURATED_SCORE = 0.85

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._curated_synergies: dict[tuple[str, str], str] = {}
        self._stat_synergies: dict = {}
        self._load_data()

    def _load_data(self):
        """Load curated and statistical synergy data."""
        curated_path = self.knowledge_dir / "synergies.json"
        if curated_path.exists():
            with open(curated_path) as f:
                synergies = json.load(f)
                for syn in synergies:
                    champs = syn.get("champions", [])
                    strength = syn.get("strength", "C")

                    if syn.get("partner_requirement"):
                        for partner in syn.get("best_partners", []):
                            partner_champ = partner.get("champion")
                            partner_rating = partner.get("rating", strength)
                            if partner_champ and len(champs) >= 1:
                                key = tuple(sorted([champs[0], partner_champ]))
                                self._curated_synergies[key] = partner_rating

                    if len(champs) >= 2:
                        key = tuple(sorted(champs[:2]))
                        self._curated_synergies[key] = strength

        stats_path = self.knowledge_dir / "champion_synergies.json"
        if stats_path.exists():
            with open(stats_path) as f:
                data = json.load(f)
                self._stat_synergies = data.get("synergies", {})

    def get_synergy_score(self, champ_a: str, champ_b: str) -> float:
        """Get synergy score between two champions (0.0-1.0)."""
        key = tuple(sorted([champ_a, champ_b]))

        # Prefer curated ratings (expert-verified), fall back to statistical data
        if key in self._curated_synergies:
            rating = self._curated_synergies[key]
            multiplier = self.RATING_MULTIPLIERS.get(rating.upper(), 0.4)
            return round(self.BASE_CURATED_SCORE * multiplier, 3)

        if champ_a in self._stat_synergies:
            if champ_b in self._stat_synergies[champ_a]:
                return self._stat_synergies[champ_a][champ_b].get("synergy_score", 0.5)

        if champ_b in self._stat_synergies:
            if champ_a in self._stat_synergies[champ_b]:
                return self._stat_synergies[champ_b][champ_a].get("synergy_score", 0.5)

        return 0.5

    def calculate_team_synergy(self, picks: list[str]) -> dict:
        """Calculate aggregate synergy for a team."""
        if len(picks) < 2:
            return {"total_score": 0.5, "pair_count": 0, "synergy_pairs": []}

        scores = []
        synergy_pairs = []

        for i, champ_a in enumerate(picks):
            for champ_b in picks[i + 1:]:
                score = self.get_synergy_score(champ_a, champ_b)
                scores.append(score)
                if score != 0.5:
                    synergy_pairs.append({"champions": [champ_a, champ_b], "score": score})

        synergy_pairs.sort(key=lambda x: -x["score"])
        total_score = sum(scores) / len(scores) if scores else 0.5

        return {
            "total_score": round(total_score, 3),
            "pair_count": len(scores),
            "synergy_pairs": synergy_pairs[:5]
        }
