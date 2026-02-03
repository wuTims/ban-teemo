"""Draft quality analysis comparing actual vs recommended picks."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.team_evaluation_service import TeamEvaluationService
from ban_teemo.services.archetype_service import ArchetypeService


class DraftQualityAnalyzer:
    """Analyzes draft quality by comparing actual picks to recommendations."""

    def __init__(self, knowledge_dir: Optional[Path] = None, tournament_data_file: Optional[str] = None):
        self.team_eval = TeamEvaluationService(knowledge_dir, tournament_data_file=tournament_data_file)
        self.archetype_service = ArchetypeService(knowledge_dir)

    def analyze(
        self,
        actual_picks: list[str],
        recommended_picks: list[list[str]] | list[str],
        enemy_picks: list[str],
    ) -> dict:
        """Compare actual draft to recommended draft.

        Args:
            actual_picks: Champions actually picked by the team
            recommended_picks: Top 5 recommendations at each pick step (list of lists)
                             or legacy format (list of single picks for backwards compat)
            enemy_picks: Enemy team's picks

        Returns:
            Dict with actual_draft, recommended_draft, and comparison
        """
        # Handle legacy format (list of strings) vs new format (list of lists)
        if recommended_picks and isinstance(recommended_picks[0], str):
            # Legacy format: convert to new format
            top_1_picks = recommended_picks
            top_n_picks = [[p] for p in recommended_picks]
        else:
            # New format: extract top 1 for ideal draft evaluation
            top_n_picks = recommended_picks
            top_1_picks = [picks[0] if picks else "" for picks in recommended_picks]

        # Evaluate actual team
        actual_eval = self.team_eval.evaluate_vs_enemy(actual_picks, enemy_picks)
        actual_arch = self.archetype_service.calculate_team_archetype(actual_picks)

        # Evaluate recommended team (using top 1 picks as the "ideal")
        rec_eval = self.team_eval.evaluate_vs_enemy(top_1_picks, enemy_picks)
        rec_arch = self.archetype_service.calculate_team_archetype(top_1_picks)

        # Get enemy archetype for insight
        enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)

        # Build archetype insight (purely descriptive)
        archetype_insight = self._build_archetype_insight(
            actual_arch["primary"],
            enemy_arch["primary"],
        )

        # Calculate picks that matched (actual pick in top 5 recommendations)
        picks_matched = sum(
            1 for actual, top_n in zip(actual_picks, top_n_picks)
            if actual in top_n
        )

        return {
            "actual_draft": {
                "picks": actual_picks,
                "archetype": actual_arch["primary"],
                "composition_score": round(actual_eval["our_evaluation"]["composition_score"], 3),
                "synergy_score": round(actual_eval["our_evaluation"]["synergy_score"], 3),
                "meta_strength": actual_eval["our_evaluation"].get("meta_strength", 0.0),
                "champion_meta": actual_eval["our_evaluation"].get("champion_meta", []),
                "vs_enemy_advantage": actual_eval["matchup_advantage"],
                "vs_enemy_description": actual_eval["matchup_description"],
            },
            "recommended_draft": {
                "picks": recommended_picks,
                "archetype": rec_arch["primary"],
                "composition_score": round(rec_eval["our_evaluation"]["composition_score"], 3),
                "synergy_score": round(rec_eval["our_evaluation"]["synergy_score"], 3),
                "meta_strength": rec_eval["our_evaluation"].get("meta_strength", 0.0),
                "champion_meta": rec_eval["our_evaluation"].get("champion_meta", []),
                "vs_enemy_advantage": rec_eval["matchup_advantage"],
                "vs_enemy_description": rec_eval["matchup_description"],
            },
            "comparison": {
                "score_delta": round(
                    rec_eval["our_evaluation"]["composition_score"]
                    - actual_eval["our_evaluation"]["composition_score"],
                    3
                ),
                "advantage_delta": round(
                    rec_eval["matchup_advantage"] - actual_eval["matchup_advantage"],
                    3
                ),
                "archetype_insight": archetype_insight,
                "picks_matched": picks_matched,
                "picks_tracked": len(recommended_picks),
            },
        }

    def _build_archetype_insight(
        self,
        actual_arch: Optional[str],
        enemy_arch: Optional[str],
    ) -> str:
        """Generate descriptive insight about archetype matchup."""
        if not actual_arch or not enemy_arch:
            return "Insufficient data for archetype analysis"

        # Get effectiveness of actual archetype vs enemy
        effectiveness = self.archetype_service.get_archetype_effectiveness(
            actual_arch, enemy_arch
        )

        # Same archetype matchup
        if actual_arch == enemy_arch:
            return f"Mirror {actual_arch} matchup"

        # Describe the matchup without prescriptive advice
        if effectiveness > 1.1:
            return f"{actual_arch.capitalize()} favored vs {enemy_arch}"
        elif effectiveness < 0.9:
            return f"{enemy_arch.capitalize()} favored vs {actual_arch}"
        else:
            return f"{actual_arch.capitalize()} vs {enemy_arch} (neutral)"
