"""Team draft evaluation with strengths and weaknesses analysis."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.synergy_service import SynergyService


class TeamEvaluationService:
    """Evaluates team compositions for strengths and weaknesses."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)

    def evaluate_team_draft(self, picks: list[str]) -> dict:
        """Evaluate a team's draft composition."""
        if not picks:
            return {
                "archetype": None,
                "synergy_score": 0.5,
                "composition_score": 0.5,
                "strengths": [],
                "weaknesses": []
            }

        # Get archetype analysis
        archetype = self.archetype_service.calculate_team_archetype(picks)

        # Get synergy analysis
        synergy = self.synergy_service.calculate_team_synergy(picks)

        # Calculate composition score (synergy + archetype alignment)
        composition_score = (synergy["total_score"] + archetype.get("alignment", 0.5)) / 2

        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []

        if archetype.get("alignment", 0) >= 0.4:
            strengths.append(f"Strong {archetype['primary']} identity")
        else:
            weaknesses.append("Lacks clear team identity")

        if synergy["total_score"] >= 0.6:
            strengths.append("Good champion synergies")
        elif synergy["total_score"] <= 0.4:
            weaknesses.append("Poor champion synergies")

        # Archetype-specific strengths/weaknesses
        primary = archetype.get("primary")
        if primary == "engage":
            strengths.append("Strong initiation")
            weaknesses.append("Weak to disengage/poke")
        elif primary == "split":
            strengths.append("Strong side lane pressure")
            weaknesses.append("Weak teamfighting")
        elif primary == "teamfight":
            strengths.append("Strong 5v5 combat")
            weaknesses.append("Weak to split push")
        elif primary == "protect":
            strengths.append("Strong carry protection")
            weaknesses.append("Weak engage")
        elif primary == "pick":
            strengths.append("Strong catch potential")
            weaknesses.append("Weak to grouped teams")

        return {
            "archetype": archetype["primary"],
            "synergy_score": synergy["total_score"],
            "composition_score": round(composition_score, 3),
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "synergy_pairs": synergy.get("synergy_pairs", [])
        }

    def evaluate_vs_enemy(self, our_picks: list[str], enemy_picks: list[str]) -> dict:
        """Evaluate our draft vs enemy draft."""
        our_eval = self.evaluate_team_draft(our_picks)
        enemy_eval = self.evaluate_team_draft(enemy_picks)

        # Get archetype matchup
        comp_advantage = self.archetype_service.calculate_comp_advantage(our_picks, enemy_picks)

        return {
            "our_evaluation": our_eval,
            "enemy_evaluation": enemy_eval,
            "matchup_advantage": comp_advantage["advantage"],
            "matchup_description": comp_advantage["description"]
        }
