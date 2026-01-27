"""Pick recommendation engine combining all scoring components."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.scorers import MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator
from ban_teemo.services.synergy_service import SynergyService


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    BASE_WEIGHTS = {"meta": 0.25, "proficiency": 0.35, "matchup": 0.25, "counter": 0.15}
    SYNERGY_MULTIPLIER_RANGE = 0.3

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)

    def get_recommendations(
        self,
        player_name: str,
        player_role: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        limit: int = 5
    ) -> list[dict]:
        """Generate ranked pick recommendations."""
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)
        candidates = self._get_candidates(player_name, player_role, unavailable)

        recommendations = []
        for champ in candidates:
            result = self._calculate_score(champ, player_name, player_role, our_picks, enemy_picks)
            recommendations.append({
                "champion_name": champ,
                "score": result["total_score"],
                "base_score": result["base_score"],
                "synergy_multiplier": result["synergy_multiplier"],
                "confidence": result["confidence"],
                "components": result["components"],
                "reasons": self._generate_reasons(champ, result)
            })

        recommendations.sort(key=lambda x: -x["score"])
        return recommendations[:limit]

    def _get_candidates(self, player_name: str, role: str, unavailable: set[str]) -> list[str]:
        """Get candidate champions to consider."""
        candidates = set()
        pool = self.proficiency_scorer.get_player_champion_pool(player_name, min_games=1)
        for entry in pool[:20]:
            if entry["champion"] not in unavailable:
                candidates.add(entry["champion"])

        if len(candidates) < 5:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=15)
            for champ in meta_picks:
                if champ not in unavailable:
                    candidates.add(champ)
                if len(candidates) >= 10:
                    break

        return list(candidates)

    def _calculate_score(
        self, champion: str, player_name: str, player_role: str,
        our_picks: list[str], enemy_picks: list[str]
    ) -> dict:
        """Calculate score using base factors + synergy multiplier."""
        components = {}

        # Meta
        components["meta"] = self.meta_scorer.get_meta_score(champion)

        # Proficiency
        prof_score, prof_conf = self.proficiency_scorer.get_proficiency_score(player_name, champion)
        components["proficiency"] = prof_score
        prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(prof_conf, 0.5)

        # Matchup (lane)
        matchup_scores = []
        for enemy in enemy_picks:
            role_probs = self.flex_resolver.get_role_probabilities(enemy)
            if player_role in role_probs and role_probs[player_role] > 0:
                result = self.matchup_calculator.get_lane_matchup(champion, enemy, player_role)
                matchup_scores.append(result["score"])
        components["matchup"] = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5

        # Counter (team)
        counter_scores = []
        for enemy in enemy_picks:
            result = self.matchup_calculator.get_team_matchup(champion, enemy)
            counter_scores.append(result["score"])
        components["counter"] = sum(counter_scores) / len(counter_scores) if counter_scores else 0.5

        # Synergy
        synergy_result = self.synergy_service.calculate_team_synergy(our_picks + [champion])
        synergy_score = synergy_result["total_score"]
        components["synergy"] = synergy_score
        synergy_multiplier = 1.0 + (synergy_score - 0.5) * self.SYNERGY_MULTIPLIER_RANGE

        # Base score
        base_score = (
            components["meta"] * self.BASE_WEIGHTS["meta"] +
            components["proficiency"] * self.BASE_WEIGHTS["proficiency"] +
            components["matchup"] * self.BASE_WEIGHTS["matchup"] +
            components["counter"] * self.BASE_WEIGHTS["counter"]
        )

        total_score = base_score * synergy_multiplier
        confidence = (1.0 + prof_conf_val) / 2

        return {
            "total_score": round(total_score, 3),
            "base_score": round(base_score, 3),
            "synergy_multiplier": round(synergy_multiplier, 3),
            "confidence": round(confidence, 3),
            "components": {k: round(v, 3) for k, v in components.items()}
        }

    def _generate_reasons(self, champion: str, result: dict) -> list[str]:
        """Generate human-readable reasons."""
        reasons = []
        components = result["components"]

        if components.get("meta", 0) >= 0.7:
            tier = self.meta_scorer.get_meta_tier(champion)
            reasons.append(f"{tier or 'High'}-tier meta pick")
        if components.get("proficiency", 0) >= 0.7:
            reasons.append("Strong player proficiency")
        if components.get("matchup", 0) >= 0.55:
            reasons.append("Favorable matchups")
        if result.get("synergy_multiplier", 1.0) >= 1.10:
            reasons.append("Strong team synergy")

        return reasons if reasons else ["Solid overall pick"]
