"""Pick recommendation engine combining all scoring components."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.scorers import MetaScorer, FlexResolver, ProficiencyScorer, MatchupCalculator
from ban_teemo.services.synergy_service import SynergyService
from ban_teemo.utils.role_normalizer import CANONICAL_ROLES, normalize_role


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    # Weights sum to 1.0 - archetype adds team composition coherence
    BASE_WEIGHTS = {
        "meta": 0.20,
        "proficiency": 0.30,
        "matchup": 0.20,
        "counter": 0.15,
        "archetype": 0.15,  # Team composition alignment
    }
    SYNERGY_MULTIPLIER_RANGE = 0.3
    ALL_ROLES = CANONICAL_ROLES  # {top, jungle, mid, bot, support}

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)

    def get_recommendations(
        self,
        team_players: list[dict],
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        limit: int = 5,
    ) -> list[dict]:
        """Generate ranked pick recommendations for best team composition.

        Args:
            team_players: List of player dicts with 'name' and 'role' keys
            our_picks: Champions already picked by our team
            enemy_picks: Champions already picked by enemy team
            banned: Champions already banned
            limit: Maximum recommendations to return

        Returns:
            List of recommendations with champion_name, score, suggested_role, etc.
        """
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)
        filled_roles = self._infer_filled_roles(our_picks)
        unfilled_roles = self.ALL_ROLES - filled_roles

        if not unfilled_roles:
            return []

        # PRE-COMPUTE: Build role cache for all potential candidates + enemy picks
        # This avoids redundant flex resolver calls in _get_candidates and _calculate_score
        role_cache = self._build_role_cache(
            team_players, unfilled_roles, unavailable, enemy_picks
        )

        candidates = self._get_candidates(team_players, unfilled_roles, unavailable, role_cache)

        if not candidates:
            return []

        recommendations = []
        for champ in candidates:
            result = self._calculate_score(
                champ, team_players, unfilled_roles, our_picks, enemy_picks, role_cache
            )
            recommendations.append({
                "champion_name": champ,
                "score": result["total_score"],
                "base_score": result["base_score"],
                "synergy_multiplier": result["synergy_multiplier"],
                "confidence": result["confidence"],
                "suggested_role": result["suggested_role"],
                "components": result["components"],
                "flag": self._compute_flag(result),
                "reasons": self._generate_reasons(champ, result)
            })

        # Safety filter: ensure no recommendations for already-filled roles
        recommendations = [r for r in recommendations if r["suggested_role"] not in filled_roles]

        recommendations.sort(key=lambda x: -x["score"])
        return recommendations[:limit]

    def _infer_filled_roles(self, picks: list[str]) -> set[str]:
        """Infer which roles are filled based on picks using primary role."""
        filled = set()
        for champ in picks:
            probs = self.flex_resolver.get_role_probabilities(champ)
            if probs:
                primary = max(probs, key=probs.get)
                filled.add(primary)
        return filled

    def _build_role_cache(
        self,
        team_players: list[dict],
        unfilled_roles: set[str],
        unavailable: set[str],
        enemy_picks: list[str],
    ) -> dict[str, dict[str, float]]:
        """Pre-compute role probabilities for candidates + enemies.

        This cache is REQUEST-SCOPED (built fresh each get_recommendations call).
        No state leaks between requests.

        Filtering logic:
        - Candidates: filtered by filled_roles (only unfilled roles matter for scoring)
        - Enemies: unfiltered (need full distribution for lane matchup analysis)

        No overlap risk: enemy_picks are in `unavailable`, so they won't be added
        from player pools or meta picks - only via explicit update().

        Returns:
            Dict mapping champion -> role probabilities
        """
        filled_roles = self.ALL_ROLES - unfilled_roles
        all_champions = set()

        # Collect champions from player pools
        for player in team_players:
            pool = self.proficiency_scorer.get_player_champion_pool(player["name"], min_games=1)
            for entry in pool[:15]:
                champ = entry["champion"]
                if champ not in unavailable:
                    all_champions.add(champ)

        # Collect meta picks for unfilled roles
        for role in unfilled_roles:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
            for champ in meta_picks:
                if champ not in unavailable:
                    all_champions.add(champ)

        # Include enemy picks for lane matchup filtering in _calculate_score
        all_champions.update(enemy_picks)

        # Batch compute role probabilities
        # Note: for enemy picks we don't filter by filled_roles since we need their full distribution
        return {
            champ: self.flex_resolver.get_role_probabilities(
                champ, filled_roles=filled_roles if champ not in enemy_picks else set()
            )
            for champ in all_champions
        }

    def _get_candidates(
        self,
        team_players: list[dict],
        unfilled_roles: set[str],
        unavailable: set[str],
        role_cache: dict[str, dict[str, float]],
    ) -> list[str]:
        """Get candidate champions from team pools and meta picks for unfilled roles.

        Uses pre-computed role_cache for O(1) lookups.
        Only returns champions that can play at least one unfilled role.
        """
        candidates = set()

        # 1. All players' champion pools
        for player in team_players:
            pool = self.proficiency_scorer.get_player_champion_pool(player["name"], min_games=1)
            for entry in pool[:15]:
                champ = entry["champion"]
                if champ not in unavailable:
                    probs = role_cache.get(champ, {})
                    if probs:  # Has at least one viable unfilled role
                        candidates.add(champ)

        # 2. Meta picks for each unfilled role
        for role in unfilled_roles:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
            for champ in meta_picks:
                if champ not in unavailable and champ not in candidates:
                    probs = role_cache.get(champ, {})
                    if probs:
                        candidates.add(champ)

        return list(candidates)

    def _calculate_score(
        self,
        champion: str,
        team_players: list[dict],
        unfilled_roles: set[str],
        our_picks: list[str],
        enemy_picks: list[str],
        role_cache: dict[str, dict[str, float]],
    ) -> dict:
        """Calculate score using base factors + synergy multiplier.

        Uses pre-computed role_cache for O(1) lookups.
        """
        components = {}

        # Use cached role probabilities for suggested_role
        probs = role_cache.get(champion, {})
        suggested_role = None
        if probs:
            suggested_role = max(probs, key=probs.get)
        suggested_role = suggested_role or "mid"

        # Meta
        components["meta"] = self.meta_scorer.get_meta_score(champion)

        # Proficiency - best across all team players
        best_prof = 0.0
        best_conf = "NO_DATA"
        for player in team_players:
            score, conf = self.proficiency_scorer.get_proficiency_score(player["name"], champion)
            if score > best_prof:
                best_prof = score
                best_conf = conf
        components["proficiency"] = best_prof
        prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(best_conf, 0.5)

        # Matchup (lane) - USE CACHE for enemy role probabilities
        matchup_scores = []
        for enemy in enemy_picks:
            role_probs = role_cache.get(enemy, {})  # Use cache instead of direct call
            if suggested_role in role_probs and role_probs[suggested_role] > 0:
                result = self.matchup_calculator.get_lane_matchup(champion, enemy, suggested_role)
                matchup_scores.append(result["score"])
        components["matchup"] = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5

        # Counter (team) - unchanged
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

        # Archetype - how well does this champion fit the emerging team composition?
        archetype_score = self._calculate_archetype_score(champion, our_picks, enemy_picks)
        components["archetype"] = archetype_score

        # Base score
        base_score = (
            components["meta"] * self.BASE_WEIGHTS["meta"] +
            components["proficiency"] * self.BASE_WEIGHTS["proficiency"] +
            components["matchup"] * self.BASE_WEIGHTS["matchup"] +
            components["counter"] * self.BASE_WEIGHTS["counter"] +
            components["archetype"] * self.BASE_WEIGHTS["archetype"]
        )

        total_score = base_score * synergy_multiplier
        confidence = (1.0 + prof_conf_val) / 2

        return {
            "total_score": round(total_score, 3),
            "base_score": round(base_score, 3),
            "synergy_multiplier": round(synergy_multiplier, 3),
            "confidence": round(confidence, 3),
            "suggested_role": suggested_role,
            "components": {k: round(v, 3) for k, v in components.items()}
        }

    def _calculate_archetype_score(
        self,
        champion: str,
        our_picks: list[str],
        enemy_picks: list[str],
    ) -> float:
        """Calculate archetype alignment and advantage score.

        Two factors:
        1. Alignment: Does adding this champion strengthen our team's archetype identity?
        2. Advantage: Does our comp's archetype counter the enemy's archetype?

        Returns:
            Score from 0-1, where 0.5 is neutral.
        """
        # Get champion's archetype contribution
        champ_arch = self.archetype_service.get_champion_archetypes(champion)
        if not champ_arch.get("primary"):
            # No archetype data for this champion - return neutral
            return 0.5

        # Calculate team archetype WITH this champion
        proposed_team = our_picks + [champion]
        team_arch = self.archetype_service.calculate_team_archetype(proposed_team)

        # Alignment score: how focused is the team on a single archetype?
        # Higher alignment = more coherent team composition
        alignment = team_arch.get("alignment", 0.0)

        # If enemy has picks, factor in archetype effectiveness
        effectiveness = 1.0
        if enemy_picks:
            advantage = self.archetype_service.calculate_comp_advantage(proposed_team, enemy_picks)
            effectiveness = advantage.get("advantage", 1.0)

        # Combine: alignment (0-1) and effectiveness (0.8-1.2 typically)
        # Scale effectiveness to 0-1 range: (eff - 0.8) / 0.4 gives 0-1 for 0.8-1.2 range
        effectiveness_normalized = min(1.0, max(0.0, (effectiveness - 0.8) / 0.4))

        # Weight alignment more heavily early (building identity)
        # Weight effectiveness more heavily late (countering enemy)
        pick_count = len(our_picks)
        if pick_count <= 2:
            # Early draft: focus on building coherent comp
            score = alignment * 0.8 + effectiveness_normalized * 0.2
        else:
            # Late draft: balance coherence and counter-picking
            score = alignment * 0.5 + effectiveness_normalized * 0.5

        return round(score, 3)

    def _compute_flag(self, result: dict) -> str | None:
        """Compute recommendation flag for UI badges.

        Thresholds:
        - LOW_CONFIDENCE: confidence < 0.7 (possible range is 0.65-1.0)
        - SURPRISE_PICK: low meta but high proficiency
        """
        if result["confidence"] < 0.7:
            return "LOW_CONFIDENCE"
        if result["components"].get("meta", 0) < 0.4 and result["components"].get("proficiency", 0) >= 0.7:
            return "SURPRISE_PICK"
        return None

    def _generate_reasons(self, champion: str, result: dict) -> list[str]:
        """Generate human-readable reasons based on component strengths."""
        reasons = []
        components = result["components"]

        # Meta tier - use actual tier from data
        meta = components.get("meta", 0)
        if meta >= 0.65:
            tier = self.meta_scorer.get_meta_tier(champion)
            reasons.append(f"{tier or 'High'}-tier meta pick")
        elif meta >= 0.5:
            tier = self.meta_scorer.get_meta_tier(champion)
            if tier:
                reasons.append(f"{tier}-tier meta pick")

        # Proficiency - always mention if high since it's a key differentiator
        prof = components.get("proficiency", 0)
        if prof >= 0.85:
            reasons.append("Elite team proficiency")
        elif prof >= 0.7:
            reasons.append("Strong team proficiency")

        # Matchup - only mention if we have actual favorable data (not neutral 0.5)
        matchup = components.get("matchup", 0.5)
        if matchup >= 0.6:
            reasons.append("Strong lane matchup")
        elif matchup >= 0.55:
            reasons.append("Favorable lane matchups")

        # Counter - team-wide matchup advantage
        counter = components.get("counter", 0.5)
        if counter >= 0.6:
            reasons.append("Counters enemy comp")
        elif counter >= 0.55:
            reasons.append("Good into enemy team")

        # Synergy
        synergy = components.get("synergy", 0.5)
        synergy_mult = result.get("synergy_multiplier", 1.0)
        if synergy_mult >= 1.08:
            reasons.append("Strong team synergy")
        elif synergy >= 0.55:
            reasons.append("Good team synergy")

        # Archetype - team composition coherence
        archetype = components.get("archetype", 0.5)
        if archetype >= 0.7:
            reasons.append("Strengthens team identity")
        elif archetype >= 0.55:
            reasons.append("Fits team composition")

        return reasons if reasons else ["Solid overall pick"]
