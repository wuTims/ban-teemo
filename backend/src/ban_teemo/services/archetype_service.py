"""Archetype analysis for team compositions."""
import json
from pathlib import Path
from typing import Optional


class ArchetypeService:
    """Analyzes team composition archetypes and effectiveness."""

    ARCHETYPES = ["engage", "split", "teamfight", "protect", "pick"]

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"
        self.knowledge_dir = knowledge_dir
        self._champion_archetypes: dict = {}
        self._effectiveness_matrix: dict = {}
        self._load_data()

    def _load_data(self):
        """Load archetype data."""
        path = self.knowledge_dir / "archetype_counters.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                self._champion_archetypes = data.get("champion_archetypes", {})
                self._effectiveness_matrix = data.get("effectiveness_matrix", {})

    def get_champion_archetypes(self, champion: str) -> dict:
        """Get archetype scores for a champion."""
        if champion not in self._champion_archetypes:
            return {"primary": None, "secondary": None, "scores": {}}

        scores = self._champion_archetypes[champion]
        sorted_archetypes = sorted(scores.items(), key=lambda x: -x[1])

        return {
            "primary": sorted_archetypes[0][0] if sorted_archetypes else None,
            "secondary": sorted_archetypes[1][0] if len(sorted_archetypes) > 1 else None,
            "scores": scores
        }

    def calculate_team_archetype(self, picks: list[str]) -> dict:
        """Calculate aggregate archetype for a team composition."""
        if not picks:
            return {"primary": None, "secondary": None, "scores": {}, "alignment": 0.0}

        aggregate = {arch: 0.0 for arch in self.ARCHETYPES}

        for champ in picks:
            champ_data = self.get_champion_archetypes(champ)
            for arch, score in champ_data.get("scores", {}).items():
                aggregate[arch] = aggregate.get(arch, 0) + score

        # Normalize
        total = sum(aggregate.values())
        if total > 0:
            aggregate = {k: v / total for k, v in aggregate.items()}
            sorted_archetypes = sorted(aggregate.items(), key=lambda x: -x[1])
            primary = sorted_archetypes[0][0]
            secondary = sorted_archetypes[1][0] if len(sorted_archetypes) > 1 else None
            primary_score = sorted_archetypes[0][1]
        else:
            # No archetype data for any champion - return None primary
            primary = None
            secondary = None
            primary_score = 0.0

        return {
            "primary": primary,
            "secondary": secondary,
            "scores": aggregate,
            "alignment": round(primary_score, 3)  # How focused the comp is
        }

    def get_archetype_effectiveness(self, our_archetype: str, enemy_archetype: str) -> float:
        """Get effectiveness multiplier (RPS style)."""
        if our_archetype not in self._effectiveness_matrix:
            return 1.0
        return self._effectiveness_matrix[our_archetype].get(f"vs_{enemy_archetype}", 1.0)

    def calculate_comp_advantage(self, our_picks: list[str], enemy_picks: list[str]) -> dict:
        """Calculate composition advantage between two teams."""
        our_arch = self.calculate_team_archetype(our_picks)
        enemy_arch = self.calculate_team_archetype(enemy_picks)

        effectiveness = 1.0
        if our_arch["primary"] and enemy_arch["primary"]:
            effectiveness = self.get_archetype_effectiveness(
                our_arch["primary"], enemy_arch["primary"]
            )

        return {
            "advantage": round(effectiveness, 3),
            "our_archetype": our_arch["primary"],
            "enemy_archetype": enemy_arch["primary"],
            "description": self._describe_advantage(effectiveness, our_arch["primary"], enemy_arch["primary"])
        }

    def _describe_advantage(self, effectiveness: float, our: str, enemy: str) -> str:
        """Generate human-readable advantage description."""
        if effectiveness > 1.1:
            return f"Your {our} comp counters their {enemy} style"
        elif effectiveness < 0.9:
            return f"Their {enemy} comp counters your {our} style"
        return "Neutral composition matchup"
