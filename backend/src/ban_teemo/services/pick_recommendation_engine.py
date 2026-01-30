"""Pick recommendation engine combining all scoring components."""
from pathlib import Path
from typing import Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.scorers import (
    MetaScorer,
    FlexResolver,
    ProficiencyScorer,
    MatchupCalculator,
    SkillTransferService,
)
from ban_teemo.services.synergy_service import SynergyService
from ban_teemo.utils.role_normalizer import CANONICAL_ROLES, normalize_role

# Soft role fill threshold - role considered "filled" at this confidence
ROLE_FILL_THRESHOLD = 0.9


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    # Weights sum to 1.0 - meta and archetype emphasized
    BASE_WEIGHTS = {
        "meta": 0.25,         # Champion's current meta strength
        "proficiency": 0.20,  # Player expertise (comfort + role strength)
        "matchup": 0.20,      # Lane matchup win rates
        "counter": 0.15,      # Team-level counter value
        "archetype": 0.20,    # Team composition alignment
    }
    SYNERGY_MULTIPLIER_RANGE = 0.3
    ALL_ROLES = CANONICAL_ROLES  # {top, jungle, mid, bot, support}
    TRANSFER_EXPANSION_LIMIT = 2

    def __init__(self, knowledge_dir: Optional[Path] = None):
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.skill_transfer_service = SkillTransferService(knowledge_dir)

    def get_recommendations(
        self,
        team_players: list[dict],
        our_picks: list,
        enemy_picks: list[str],
        banned: list[str],
        limit: int = 5,
    ) -> list[dict]:
        """Generate ranked pick recommendations for best team composition.

        Args:
            team_players: List of player dicts with 'name' and 'role' keys
            our_picks: Champions already picked - list of strings OR list of dicts
                       with 'champion' and 'role' keys (for soft role fill)
            enemy_picks: Champions already picked by enemy team
            banned: Champions already banned
            limit: Maximum recommendations to return

        Returns:
            List of recommendations with champion_name, score, suggested_role, etc.
        """
        # Normalize our_picks: extract champion names for unavailable set
        our_pick_names = []
        our_picks_normalized = []
        for pick in our_picks:
            if isinstance(pick, dict):
                champ = pick.get("champion", "")
                our_pick_names.append(champ)
                our_picks_normalized.append(pick)
            else:
                our_pick_names.append(pick)
                our_picks_normalized.append({"champion": pick, "role": None})

        unavailable = set(banned) | set(our_pick_names) | set(enemy_picks)

        # Calculate soft role fill from picks
        role_fill = self._calculate_role_fill(our_picks_normalized)
        unfilled_roles = self._get_unfilled_roles(role_fill)

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
                champ, team_players, unfilled_roles, our_pick_names, enemy_picks, role_cache, role_fill
            )
            recommendations.append({
                "champion_name": champ,
                "score": result["total_score"],
                "base_score": result["base_score"],
                "synergy_multiplier": result["synergy_multiplier"],
                "confidence": result["confidence"],
                "suggested_role": result["suggested_role"],
                "components": result["components"],
                "effective_weights": result.get("effective_weights"),
                "proficiency_source": result.get("proficiency_source"),
                "proficiency_player": result.get("proficiency_player"),
                "flag": self._compute_flag(result),
                "reasons": self._generate_reasons(champ, result)
            })

        # Safety filter: ensure no recommendations for already-filled roles
        filled_roles = {r for r in self.ALL_ROLES if r not in unfilled_roles}
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
        base_candidates = set()

        # Collect champions from player pools
        for player in team_players:
            pool = self.proficiency_scorer.get_player_champion_pool(player["name"], min_games=1)
            for entry in pool[:15]:
                champ = entry["champion"]
                if champ not in unavailable:
                    base_candidates.add(champ)

        # Collect meta picks for unfilled roles
        for role in unfilled_roles:
            meta_picks = self.meta_scorer.get_top_meta_champions(role=role, limit=10)
            for champ in meta_picks:
                if champ not in unavailable:
                    base_candidates.add(champ)

        # Collect global power picks (regardless of role)
        # Ensures power picks aren't missed due to sparse player data
        global_power = self.meta_scorer.get_top_meta_champions(role=None, limit=20)
        for champ in global_power:
            if champ not in unavailable:
                base_candidates.add(champ)

        all_champions.update(base_candidates)

        # Expand candidates with transfer targets (one-hop)
        for champ in base_candidates:
            for transfer in self.skill_transfer_service.get_similar_champions(
                champ, limit=self.TRANSFER_EXPANSION_LIMIT
            ):
                target = transfer.get("champion")
                if target and target not in unavailable:
                    all_champions.add(target)

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
        """Get candidate champions from team pools, meta picks, and global power picks.

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

        # 3. Global power picks (high presence regardless of role/pool)
        # Ensures power picks aren't missed due to sparse player data
        global_power = self.meta_scorer.get_top_meta_champions(role=None, limit=20)
        for champ in global_power:
            if champ not in unavailable and champ not in candidates:
                probs = role_cache.get(champ, {})
                if probs:
                    candidates.add(champ)

        # 4. One-hop transfer targets for candidate expansion
        base_candidates = set(candidates)
        for champ in base_candidates:
            for transfer in self.skill_transfer_service.get_similar_champions(
                champ, limit=self.TRANSFER_EXPANSION_LIMIT
            ):
                target = transfer.get("champion")
                if not target or target in unavailable or target in candidates:
                    continue
                probs = role_cache.get(target, {})
                if probs:
                    candidates.add(target)

        return list(candidates)

    def _calculate_score(
        self,
        champion: str,
        team_players: list[dict],
        unfilled_roles: set[str],
        our_picks: list[str],
        enemy_picks: list[str],
        role_cache: dict[str, dict[str, float]],
        role_fill: Optional[dict[str, float]] = None,
    ) -> dict:
        """Calculate score using base factors + synergy multiplier.

        Uses pre-computed role_cache for O(1) lookups.
        """
        components = {}

        # Use cached role probabilities for suggested_role
        probs = role_cache.get(champion, {})
        (
            suggested_role,
            role_prof_score,
            role_prof_conf,
            prof_source,
            prof_player,
        ) = self._choose_best_role(champion, probs, team_players, role_fill=role_fill)
        suggested_role = suggested_role or "mid"

        # Meta
        components["meta"] = self.meta_scorer.get_meta_score(champion)

        # Proficiency - role-assigned player only
        components["proficiency"] = role_prof_score
        prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(
            role_prof_conf, 0.5
        )

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
        pick_count = len(our_picks)
        has_enemy_picks = len(enemy_picks) > 0
        effective_weights = self._get_effective_weights(
            role_prof_conf,
            pick_count=pick_count,
            has_enemy_picks=has_enemy_picks
        )
        base_score = (
            components["meta"] * effective_weights["meta"] +
            components["proficiency"] * effective_weights["proficiency"] +
            components["matchup"] * effective_weights["matchup"] +
            components["counter"] * effective_weights["counter"] +
            components["archetype"] * effective_weights["archetype"]
        )

        # Apply blind pick safety factor for early picks without enemy context
        blind_safety_applied = False
        if pick_count <= 1 and not has_enemy_picks:
            blind_safety = self.meta_scorer.get_blind_pick_safety(champion)
            base_score = base_score * blind_safety
            blind_safety_applied = True
            components["blind_safety"] = blind_safety

        # Apply role flex bonus for early picks (hides role assignment)
        if pick_count <= 1:
            role_flex = self._get_role_flex_score(champion)
            # Add as weighted component (5% of total)
            role_flex_bonus = role_flex * 0.05
            base_score = base_score + role_flex_bonus
            components["role_flex"] = role_flex

        total_score = base_score * synergy_multiplier
        confidence = (1.0 + prof_conf_val) / 2

        return {
            "total_score": round(total_score, 3),
            "base_score": round(base_score, 3),
            "synergy_multiplier": round(synergy_multiplier, 3),
            "confidence": round(confidence, 3),
            "suggested_role": suggested_role,
            "components": {k: round(v, 3) for k, v in components.items()},
            "effective_weights": {k: round(v, 3) for k, v in effective_weights.items()},
            "proficiency_source": prof_source,
            "proficiency_player": prof_player,
            "blind_safety_applied": blind_safety_applied,
        }

    def _calculate_archetype_score(
        self,
        champion: str,
        our_picks: list[str],
        enemy_picks: list[str],
    ) -> float:
        """Calculate phase-aware archetype score.

        Scoring strategy changes by draft phase:
        - Early draft (0-1 picks): Value raw strength + versatility bonus
        - Mid draft (2-3 picks): Blend raw strength with team alignment
        - Late draft (4+ picks): Weight alignment + counter-effectiveness

        Returns:
            Score from 0-1, where 0.5 is neutral.
        """
        pick_count = len(our_picks)

        # Get champion's archetype data
        raw_strength = self.archetype_service.get_raw_strength(champion)
        versatility = self.archetype_service.get_versatility_score(champion)

        # PHASE 1: Early draft (0-1 picks) - Value versatility
        if pick_count <= 1:
            # Versatile champions are valuable - they hide strategy
            versatility_bonus = versatility * 0.15
            return min(1.0, raw_strength + versatility_bonus)

        # PHASE 2+: Mid-late draft - Value alignment with team direction
        team_arch = self.archetype_service.calculate_team_archetype(our_picks)
        team_primary = team_arch.get("primary")

        if not team_primary:
            # No clear team direction yet - use raw strength
            return raw_strength

        # How much does this champion contribute to team's direction?
        contribution = self.archetype_service.get_contribution_to_archetype(
            champion, team_primary
        )

        # Blend contribution with raw strength
        # More picks = weight contribution more heavily
        alignment_weight = min(0.7, pick_count * 0.15)  # 0.30 at 2 picks -> 0.70 at 5
        base_score = (
            contribution * alignment_weight +
            raw_strength * (1 - alignment_weight)
        )

        # PHASE 3: Factor in counter-effectiveness vs enemy (late draft)
        if enemy_picks and pick_count >= 3:
            advantage = self.archetype_service.calculate_comp_advantage(
                our_picks + [champion], enemy_picks
            )
            effectiveness = advantage.get("advantage", 1.0)
            # Normalize effectiveness (typically 0.8-1.2) to 0-1 scale
            effectiveness_normalized = max(0.0, min(1.0, (effectiveness - 0.8) / 0.4))

            # Weight effectiveness more as draft progresses
            eff_weight = min(0.4, (pick_count - 2) * 0.1)  # 0.1 at 3 picks -> 0.4 at 5+
            base_score = base_score * (1 - eff_weight) + effectiveness_normalized * eff_weight

        return round(base_score, 3)

    def _choose_best_role(
        self,
        champion: str,
        role_probs: dict[str, float],
        team_players: list[dict],
        role_fill: Optional[dict[str, float]] = None,
    ) -> tuple[str, float, str, str, Optional[str]]:
        """Choose role based on role_prob and role_need, NOT player proficiency.

        Role selection is decoupled from player baseline to prevent misassignment.
        Proficiency is calculated AFTER role is chosen.

        For flex champs: if best role is filled, re-evaluate among unfilled roles
        instead of dropping the champion entirely.
        """
        if not role_probs:
            return "mid", 0.5, "NO_DATA", "none", None

        # If no role_fill provided, assume all roles unfilled
        if role_fill is None:
            role_fill = {}

        # Get unfilled roles (< threshold)
        unfilled_roles = set()
        for role in role_probs:
            fill = role_fill.get(role, 0.0)
            if fill < ROLE_FILL_THRESHOLD:
                unfilled_roles.add(role)

        # Filter to only consider unfilled roles (but keep all if none unfilled)
        candidate_roles = {r: p for r, p in role_probs.items() if r in unfilled_roles}
        if not candidate_roles:
            # All roles filled - fall back to original probs (will likely be filtered out later)
            candidate_roles = role_probs

        # Calculate role need weights for candidate roles
        role_need = {}
        for role in candidate_roles:
            fill = role_fill.get(role, 0.0)
            # Role need decreases as fill increases; 0 at >= 0.9
            role_need[role] = max(0.0, 1.0 - fill / ROLE_FILL_THRESHOLD)

        # Select role based on role_prob × role_need (NOT player proficiency)
        best_role = None
        best_score = -1.0

        for role, prob in candidate_roles.items():
            need_weight = role_need.get(role, 1.0)
            score = prob * need_weight

            if score > best_score:
                best_role = role
                best_score = score

        if not best_role:
            best_role = max(candidate_roles, key=candidate_roles.get)

        # NOW calculate proficiency for the chosen role
        prof_score, conf, player_name, source = (
            self.proficiency_scorer.get_champion_proficiency(
                champion, best_role, team_players
            )
        )

        return best_role, prof_score, conf, source, player_name

    def _get_effective_weights(
        self,
        prof_conf: str,
        pick_count: int = 0,
        has_enemy_picks: bool = False
    ) -> dict[str, float]:
        """Get context-adjusted scoring weights.

        Adjustments:
        - First pick (pick_count=0, no enemy): reduce proficiency, boost meta
        - Counter-pick (late draft, has enemy): boost matchup
        - NO_DATA proficiency: redistribute to other components

        Args:
            prof_conf: Proficiency confidence level
            pick_count: Number of picks our team has made
            has_enemy_picks: Whether enemy has revealed picks

        Returns:
            Dict of component weights summing to ~1.0
        """
        weights = dict(self.BASE_WEIGHTS)

        # First pick context: reduce proficiency, increase meta
        # Rationale: First picks are about power level, not player comfort
        if pick_count == 0 and not has_enemy_picks:
            redistribution = 0.08  # Take from proficiency
            weights["proficiency"] -= redistribution
            weights["meta"] += redistribution

        # Counter-pick context: increase matchup weight
        # Rationale: Late picks should exploit matchup knowledge
        elif has_enemy_picks and pick_count >= 3:
            redistribution = 0.05
            weights["meta"] -= redistribution
            weights["matchup"] += redistribution

        # Handle NO_DATA proficiency - redistribute most of its weight
        if prof_conf == "NO_DATA":
            redistribute = weights["proficiency"] * 0.8
            weights["proficiency"] = weights["proficiency"] * 0.2
            # Distribute evenly to other components
            for key in ["meta", "matchup", "counter", "archetype"]:
                weights[key] += redistribute / 4

        return weights

    def _calculate_role_fill(self, our_picks: list[dict]) -> dict[str, float]:
        """Calculate cumulative role fill from existing picks.

        Flex champions contribute fractionally based on their role probabilities.
        Pure role champions contribute 1.0 to their role.

        Uses get_role_probabilities() which reads from champion_role_history.json
        (the single source of truth for role data).

        Args:
            our_picks: List of pick dicts with 'champion' and 'role' keys

        Returns:
            Dict mapping role -> fill confidence (0.0 to 1.0+)
        """
        role_fill: dict[str, float] = {}

        for pick in our_picks:
            champion = pick.get("champion") if isinstance(pick, dict) else pick
            assigned_role = pick.get("role") if isinstance(pick, dict) else None

            if not champion:
                continue

            # Get role probabilities (with fallback to role_history for unknown champs)
            role_probs = self.flex_resolver.get_role_probabilities(champion, filled_roles=set())

            if not role_probs:
                # No role data at all - use assigned role if provided
                if assigned_role:
                    normalized = normalize_role(assigned_role)
                    if normalized:
                        role_fill[normalized] = role_fill.get(normalized, 0.0) + 1.0
                continue

            # Check if flex (multiple roles with significant probability)
            is_flex = self.flex_resolver.is_flex_pick(champion)

            if is_flex:
                # Flex champion: distribute based on role probabilities
                for role, prob in role_probs.items():
                    role_fill[role] = role_fill.get(role, 0.0) + prob
            else:
                # Pure role champion: 1.0 to assigned or primary role
                role_to_fill = assigned_role
                if role_to_fill:
                    normalized = normalize_role(role_to_fill)
                    if normalized:
                        role_fill[normalized] = role_fill.get(normalized, 0.0) + 1.0
                else:
                    # Use primary role from probabilities
                    primary_role = max(role_probs, key=role_probs.get)
                    role_fill[primary_role] = role_fill.get(primary_role, 0.0) + 1.0

        return role_fill

    def _get_unfilled_roles(self, role_fill: dict[str, float]) -> set[str]:
        """Get roles that are not yet filled (< ROLE_FILL_THRESHOLD)."""
        return {role for role in self.ALL_ROLES if role_fill.get(role, 0.0) < ROLE_FILL_THRESHOLD}

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

    def _get_role_flex_score(self, champion: str) -> float:
        """Calculate role flexibility score for a champion.

        Champions that can play multiple roles are valuable in early draft
        because they hide team's role assignment from the enemy.

        Returns:
            Float 0.0-0.8 representing role flexibility value
        """
        probs = self.flex_resolver.get_role_probabilities(champion)
        if not probs:
            return 0.2  # Unknown - assume single role

        # Count roles with >= 20% probability (viable roles)
        viable_roles = [r for r, p in probs.items() if p >= 0.20]

        if len(viable_roles) >= 3:
            return 0.8  # True flex (3+ roles)
        elif len(viable_roles) >= 2:
            return 0.5  # Dual flex
        return 0.2  # Single role

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
