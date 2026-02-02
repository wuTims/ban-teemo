"""Draft quality analysis comparing actual vs recommended picks."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.team_evaluation_service import TeamEvaluationService
from ban_teemo.services.archetype_service import ArchetypeService


class DraftQualityAnalyzer:
    """Analyzes draft quality by comparing actual picks to recommendations."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.team_eval = TeamEvaluationService(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)

    def analyze(
        self,
        actual_picks: list[str],
        recommended_picks: list[str],
        enemy_picks: list[str],
    ) -> dict:
        """Compare actual draft to recommended draft.

        Args:
            actual_picks: Champions actually picked by the team
            recommended_picks: Top recommendations at each pick step
            enemy_picks: Enemy team's picks

        Returns:
            Dict with actual_draft, recommended_draft, and comparison
        """
        # Evaluate actual team
        actual_eval = self.team_eval.evaluate_vs_enemy(actual_picks, enemy_picks)
        actual_arch = self.archetype_service.calculate_team_archetype(actual_picks)

        # Evaluate recommended team
        rec_eval = self.team_eval.evaluate_vs_enemy(recommended_picks, enemy_picks)
        rec_arch = self.archetype_service.calculate_team_archetype(recommended_picks)

        # Get enemy archetype for insight
        enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)

        # Build archetype insight
        archetype_insight = self._build_archetype_insight(
            actual_arch["primary"],
            rec_arch["primary"],
            enemy_arch["primary"],
        )

        # Calculate picks that matched
        picks_matched = sum(
            1 for a, r in zip(actual_picks, recommended_picks) if a == r
        )

        return {
            "actual_draft": {
                "picks": actual_picks,
                "archetype": actual_arch["primary"],
                "composition_score": round(actual_eval["our_evaluation"]["composition_score"], 3),
                "synergy_score": round(actual_eval["our_evaluation"]["synergy_score"], 3),
                "vs_enemy_advantage": actual_eval["matchup_advantage"],
                "vs_enemy_description": actual_eval["matchup_description"],
            },
            "recommended_draft": {
                "picks": recommended_picks,
                "archetype": rec_arch["primary"],
                "composition_score": round(rec_eval["our_evaluation"]["composition_score"], 3),
                "synergy_score": round(rec_eval["our_evaluation"]["synergy_score"], 3),
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
        rec_arch: Optional[str],
        enemy_arch: Optional[str],
    ) -> str:
        """Generate insight about archetype differences."""
        if not rec_arch or not enemy_arch:
            return "Insufficient data for archetype analysis"

        if not actual_arch:
            return f"Recommended {rec_arch} archetype vs enemy's {enemy_arch} style"

        if actual_arch == rec_arch:
            return f"Both drafts have {actual_arch} identity"

        # Get effectiveness of each archetype vs enemy
        actual_eff = 1.0
        rec_eff = 1.0
        if actual_arch:
            actual_eff = self.archetype_service.get_archetype_effectiveness(
                actual_arch, enemy_arch
            )
        if rec_arch:
            rec_eff = self.archetype_service.get_archetype_effectiveness(
                rec_arch, enemy_arch
            )

        if rec_eff > actual_eff:
            return f"Recommended {rec_arch} archetype better vs enemy's {enemy_arch} style"
        elif actual_eff > rec_eff:
            return f"Your {actual_arch} archetype actually better vs enemy's {enemy_arch} style"
        else:
            return f"Both {actual_arch} and {rec_arch} archetypes neutral vs enemy"
