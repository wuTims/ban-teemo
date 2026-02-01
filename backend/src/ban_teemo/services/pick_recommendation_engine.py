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
    TournamentScorer,
)
from ban_teemo.services.synergy_service import SynergyService
from ban_teemo.utils.role_normalizer import CANONICAL_ROLES, normalize_role

# Soft role fill threshold - role considered "filled" at this confidence
# 0.75 means if a champion is 75%+ likely in a role, that role is filled
ROLE_FILL_THRESHOLD = 0.75


class PickRecommendationEngine:
    """Generates pick recommendations using weighted multi-factor scoring."""

    # Domain expert priority order (tuned via experiments - see scripts/scoring_experiments.py):
    # 1. Meta strength - "pick strong champions" (highest - uses hybrid scoring)
    # 2. Matchup/Counter - "don't feed"
    # 3. Team composition (archetype) - reduced to avoid specialist bias
    # 4. Proficiency - "they're pros anyway"
    #
    # NOTE: Synergy is NOT a base weight - it's applied as a multiplier to the
    # final score. This is intentional: synergy is a team-wide modifier that
    # scales the entire recommendation, not an individual champion attribute.
    #
    # Tuning notes (2026-01-31):
    # - Archetype reduced from 0.30 to 0.15: 29 champions have archetype=1.0,
    #   causing "specialist bias" where niche picks outscored balanced meta picks
    # - Meta increased to 0.45 with hybrid scoring: averages original tier-based
    #   score with presence-based score, improving accuracy by +5.8%
    BASE_WEIGHTS = {
        "meta": 0.45,            # Champion power level (hybrid scoring)
        "matchup_counter": 0.25, # Combined lane + team matchups
        "archetype": 0.15,       # Team composition fit (reduced - specialist bias)
        "proficiency": 0.15,     # Player comfort (lowest - they're pros)
    }

    # Simulator mode weights - replaces meta with tournament components
    # Tournament data provides current pro meta signals (picks/bans/winrates)
    SIMULATOR_BASE_WEIGHTS = {
        "tournament_priority": 0.25,    # Role-agnostic contestation
        "tournament_performance": 0.20, # Role-specific adjusted winrate
        "matchup_counter": 0.25,        # Combined lane + team matchups
        "archetype": 0.15,              # Team composition fit
        "proficiency": 0.15,            # Player comfort
    }

    # Widened from 0.3 to 0.5 for better score differentiation (0.75-1.25 range)
    SYNERGY_MULTIPLIER_RANGE = 0.5
    ALL_ROLES = CANONICAL_ROLES  # {top, jungle, mid, bot, support}
    TRANSFER_EXPANSION_LIMIT = 2

    def __init__(self, knowledge_dir: Optional[Path] = None, simulator_mode: bool = False):
        self.simulator_mode = simulator_mode
        self.meta_scorer = MetaScorer(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.skill_transfer_service = SkillTransferService(knowledge_dir)
        self.tournament_scorer = TournamentScorer(knowledge_dir)

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

        # Meta / Tournament scoring
        if self.simulator_mode:
            # Simulator mode: use tournament data for current pro meta signals
            tournament_scores = self.tournament_scorer.get_tournament_scores(
                champion, suggested_role
            )
            components["tournament_priority"] = tournament_scores["priority"]
            components["tournament_performance"] = tournament_scores["performance"]
            # Also store meta for reference/fallback but don't weight it
            components["meta"] = self.meta_scorer.get_meta_score(champion)
        else:
            # Normal mode: use existing meta scoring
            components["meta"] = self.meta_scorer.get_meta_score(champion)

        # Proficiency - role-assigned player only
        components["proficiency"] = role_prof_score
        prof_conf_val = {"HIGH": 1.0, "MEDIUM": 0.8, "LOW": 0.5, "NO_DATA": 0.3}.get(
            role_prof_conf, 0.5
        )

        # Combined matchup_counter (lane + team matchups)
        # Rationale: "don't feed" encompasses both lane and team-level matchups
        matchup_scores = []
        counter_scores = []
        matchup_data_found = 0
        matchup_lookups = 0

        for enemy in enemy_picks:
            # Lane matchup
            role_probs = role_cache.get(enemy, {})  # Use cache instead of direct call
            if suggested_role in role_probs and role_probs[suggested_role] > 0:
                result = self.matchup_calculator.get_lane_matchup(champion, enemy, suggested_role)
                matchup_scores.append(result["score"])
                matchup_lookups += 1
                if result.get("data_source") != "none":
                    matchup_data_found += 1

            # Team counter
            result = self.matchup_calculator.get_team_matchup(champion, enemy)
            counter_scores.append(result["score"])
            matchup_lookups += 1
            if result.get("data_source") != "none":
                matchup_data_found += 1

        # Combine: weight lane matchup slightly higher (60/40)
        # Lane matchup is more important than general team counter
        matchup_avg = sum(matchup_scores) / len(matchup_scores) if matchup_scores else 0.5
        counter_avg = sum(counter_scores) / len(counter_scores) if counter_scores else 0.5
        components["matchup_counter"] = matchup_avg * 0.6 + counter_avg * 0.4

        # Determine matchup data confidence
        # NO_DATA: no lookups had real data, PARTIAL: some data, FULL: all data
        if matchup_lookups == 0:
            matchup_conf = "NO_DATA"  # No enemy picks yet
        elif matchup_data_found == 0:
            matchup_conf = "NO_DATA"  # All lookups returned defaults
        elif matchup_data_found < matchup_lookups:
            matchup_conf = "PARTIAL"  # Some data available
        else:
            matchup_conf = "FULL"  # All lookups had real data

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

        # Cap proficiency on first pick to prevent comfort picks dominating over power picks
        # Weight reduction alone (0.20 -> 0.10) isn't enough when prof=0.95
        if pick_count == 0:
            components["proficiency"] = min(components["proficiency"], 0.7)

        effective_weights = self._get_effective_weights(
            role_prof_conf,
            pick_count=pick_count,
            has_enemy_picks=has_enemy_picks,
            matchup_conf=matchup_conf,
            simulator_mode=self.simulator_mode,
        )
        # NOTE: Synergy is applied as a multiplier AFTER base_score, not as a component.
        # This avoids double-counting synergy (which is already a multiplier in the
        # current implementation). See synergy_multiplier usage below.
        if self.simulator_mode:
            # Simulator mode: tournament components replace meta
            base_score = (
                components["tournament_priority"] * effective_weights["tournament_priority"] +
                components["tournament_performance"] * effective_weights["tournament_performance"] +
                components["archetype"] * effective_weights["archetype"] +
                components["matchup_counter"] * effective_weights["matchup_counter"] +
                components["proficiency"] * effective_weights["proficiency"]
            )
        else:
            # Normal mode: use meta
            base_score = (
                components["archetype"] * effective_weights["archetype"] +
                components["meta"] * effective_weights["meta"] +
                components["matchup_counter"] * effective_weights["matchup_counter"] +
                components["proficiency"] * effective_weights["proficiency"]
            )
        # Synergy multiplier is applied separately: total_score = base_score * synergy_multiplier

        # Apply blind pick safety factor for early picks without enemy context
        blind_safety_applied = False
        if pick_count <= 1 and not has_enemy_picks:
            blind_safety = self.meta_scorer.get_blind_pick_safety(champion)
            base_score = base_score * blind_safety
            blind_safety_applied = True
            components["blind_safety"] = blind_safety

        # Apply role flex bonus for early picks (hides role assignment)
        # Increased from 5% to 15% - flex picks are consistently undervalued
        if pick_count <= 1:
            role_flex = self._get_role_flex_score(champion)
            role_flex_bonus = role_flex * 0.15  # Was 0.05
            base_score = base_score + role_flex_bonus
            components["role_flex"] = role_flex

            # Add presence bonus for highly contested champions (>40% presence)
            # These are clearly valued by pros regardless of other factors
            presence = self.meta_scorer.get_presence(champion)
            if presence > 0.4:
                presence_bonus = 0.05
                base_score = base_score + presence_bonus
                components["presence_bonus"] = presence_bonus

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
        has_enemy_picks: bool = False,
        matchup_conf: str = "FULL",
        simulator_mode: bool = False,
    ) -> dict[str, float]:
        """Get context-adjusted scoring weights.

        Priority order (domain expert):
        1. archetype - team composition (NEVER reduced - defines team identity)
        2. meta/tournament - champion power
        3. matchup_counter - don't feed
        4. proficiency - lowest (pros can play anything)

        Design rationale:
        - Archetype is never reduced because first pick often defines team identity
        - Meta is boosted early (power picks) and reduced late (counters matter more)
        - Matchup_counter is boosted late when counter-picking is possible
        - Proficiency is always lowest priority for pro play

        Simulator mode uses AGGRESSIVE phase adjustments:
        - Early blind: priority +0.05, performance -0.05, matchup -0.10, archetype +0.10
        - Late counter: priority -0.10, performance +0.05, matchup +0.10, proficiency -0.05
        These larger swings (0.10-0.15) allow counter-picks to overcome raw priority.

        Data confidence handling:
        - When proficiency or matchup data is missing (NO_DATA), we reduce that
          component's weight and redistribute to components we DO have data for.
        - This prevents "0.5 defaults" from having outsized influence on scoring.
        """
        if simulator_mode:
            return self._get_simulator_weights(
                prof_conf, pick_count, has_enemy_picks, matchup_conf
            )

        # Normal mode weights
        weights = dict(self.BASE_WEIGHTS)

        # First pick: boost meta, reduce proficiency further
        # NOTE: Archetype is NOT reduced - first pick often sets team identity
        if pick_count == 0 and not has_enemy_picks:
            # Blind picks are about power level + team identity
            weights["meta"] += 0.05           # 0.45 -> 0.50
            weights["proficiency"] -= 0.05    # 0.15 -> 0.10

        # Late draft: boost matchup_counter, reduce meta
        elif has_enemy_picks and pick_count >= 3:
            weights["matchup_counter"] += 0.05  # 0.25 -> 0.30
            weights["meta"] -= 0.05             # 0.45 -> 0.40

        # Handle NO_DATA matchup - reduce weight to avoid 0.5 defaults dominating
        # This happens when champion has insufficient pro play matchup data
        #
        # IMPORTANT: Redistribute to META only (not archetype) because archetype
        # scores are biased toward specialists (29 champs have arch=1.0).
        # Redistributing to archetype causes specialists to dominate over
        # balanced high-meta champions like Azir.
        if matchup_conf == "NO_DATA":
            redistribute = weights["matchup_counter"] * 0.5  # Keep 50% weight
            weights["matchup_counter"] *= 0.5
            # Redistribute to meta only - archetype bias causes specialist domination
            weights["meta"] += redistribute
        elif matchup_conf == "PARTIAL":
            # Partial data - reduce weight by 25%
            redistribute = weights["matchup_counter"] * 0.25
            weights["matchup_counter"] *= 0.75
            # Redistribute mostly to meta, small amount to archetype
            weights["meta"] += redistribute * 0.8
            weights["archetype"] += redistribute * 0.2

        # Handle NO_DATA proficiency
        if prof_conf == "NO_DATA":
            redistribute = weights["proficiency"] * 0.8
            weights["proficiency"] *= 0.2
            # Distribute to meta and matchup (avoid archetype bias toward specialists)
            weights["meta"] += redistribute * 0.6
            weights["matchup_counter"] += redistribute * 0.4

        return weights

    def _get_simulator_weights(
        self,
        prof_conf: str,
        pick_count: int,
        has_enemy_picks: bool,
        matchup_conf: str,
    ) -> dict[str, float]:
        """Get simulator mode weights with aggressive phase adjustments.

        Aggressive phase swings allow counter-picks to overcome raw tournament priority:
        - Early blind: Prioritize contested picks (priority) + team identity (archetype)
        - Late counter: Prioritize proven performers (performance) + counter-picking (matchup)

        Phase adjustments:
        | Component              | Base | Early | Late  |
        |------------------------|------|-------|-------|
        | tournament_priority    | 0.25 | +0.05 | -0.10 |
        | tournament_performance | 0.20 | -0.05 | +0.05 |
        | matchup_counter        | 0.25 | -0.10 | +0.10 |
        | archetype              | 0.15 | +0.10 | 0     |
        | proficiency            | 0.15 | 0     | -0.05 |
        """
        weights = dict(self.SIMULATOR_BASE_WEIGHTS)

        # Early blind picks (pick_count == 0, no enemy context)
        if pick_count == 0 and not has_enemy_picks:
            weights["tournament_priority"] += 0.05    # 0.25 -> 0.30
            weights["tournament_performance"] -= 0.05 # 0.20 -> 0.15
            weights["matchup_counter"] -= 0.10        # 0.25 -> 0.15
            weights["archetype"] += 0.10              # 0.15 -> 0.25
            # proficiency stays at 0.15

        # Late counter-pick phase (3+ picks, has enemy context)
        elif has_enemy_picks and pick_count >= 3:
            weights["tournament_priority"] -= 0.10    # 0.25 -> 0.15
            weights["tournament_performance"] += 0.05 # 0.20 -> 0.25
            weights["matchup_counter"] += 0.10        # 0.25 -> 0.35
            # archetype stays at 0.15
            weights["proficiency"] -= 0.05            # 0.15 -> 0.10

        # Handle NO_DATA matchup - redistribute to tournament components
        if matchup_conf == "NO_DATA":
            redistribute = weights["matchup_counter"] * 0.5
            weights["matchup_counter"] *= 0.5
            # Redistribute to tournament_priority (not archetype to avoid specialist bias)
            weights["tournament_priority"] += redistribute
        elif matchup_conf == "PARTIAL":
            redistribute = weights["matchup_counter"] * 0.25
            weights["matchup_counter"] *= 0.75
            weights["tournament_priority"] += redistribute * 0.6
            weights["tournament_performance"] += redistribute * 0.4

        # Handle NO_DATA proficiency
        if prof_conf == "NO_DATA":
            redistribute = weights["proficiency"] * 0.8
            weights["proficiency"] *= 0.2
            weights["tournament_priority"] += redistribute * 0.4
            weights["tournament_performance"] += redistribute * 0.3
            weights["matchup_counter"] += redistribute * 0.3

        return weights

    def _calculate_role_fill(self, our_picks: list[dict]) -> dict[str, float]:
        """Calculate cumulative role fill from existing picks.

        Two-pass approach:
        1. First pass: identify pure role picks that definitively fill roles
        2. Second pass: flex champions redistribute to remaining unfilled roles

        This handles cases like Aurora (mid/top flex) + Ambessa (top) where
        Aurora should commit fully to mid once top is taken.

        Args:
            our_picks: List of pick dicts with 'champion' and 'role' keys

        Returns:
            Dict mapping role -> fill confidence (0.0 to 1.0+)
        """
        role_fill: dict[str, float] = {}
        flex_picks: list[tuple[str, dict[str, float]]] = []  # (champion, role_probs)

        # PASS 1: Process pure role champions first (they definitively fill roles)
        for pick in our_picks:
            champion = pick.get("champion") if isinstance(pick, dict) else pick
            assigned_role = pick.get("role") if isinstance(pick, dict) else None

            if not champion:
                continue

            role_probs = self.flex_resolver.get_role_probabilities(champion, filled_roles=set())

            if not role_probs:
                if assigned_role:
                    normalized = normalize_role(assigned_role)
                    if normalized:
                        role_fill[normalized] = role_fill.get(normalized, 0.0) + 1.0
                continue

            is_flex = self.flex_resolver.is_flex_pick(champion)

            if is_flex:
                # Defer flex champions to pass 2
                flex_picks.append((champion, role_probs))
            else:
                # Pure role champion: 1.0 to assigned or primary role
                role_to_fill = assigned_role
                if role_to_fill:
                    normalized = normalize_role(role_to_fill)
                    if normalized:
                        role_fill[normalized] = role_fill.get(normalized, 0.0) + 1.0
                else:
                    primary_role = max(role_probs, key=role_probs.get)
                    role_fill[primary_role] = role_fill.get(primary_role, 0.0) + 1.0

        # PASS 2: Process flex champions, redistributing to unfilled roles
        for champion, role_probs in flex_picks:
            # Find which of this champion's roles are still unfilled
            unfilled_roles = {
                role: prob for role, prob in role_probs.items()
                if role_fill.get(role, 0.0) < ROLE_FILL_THRESHOLD
            }

            if not unfilled_roles:
                # All roles filled - use primary role anyway (overfill)
                primary_role = max(role_probs, key=role_probs.get)
                role_fill[primary_role] = role_fill.get(primary_role, 0.0) + 1.0
            elif len(unfilled_roles) == 1:
                # Only one role unfilled - commit fully to it
                role = next(iter(unfilled_roles))
                role_fill[role] = role_fill.get(role, 0.0) + 1.0
            else:
                # Multiple unfilled roles - redistribute proportionally among them
                total_prob = sum(unfilled_roles.values())
                for role, prob in unfilled_roles.items():
                    # Normalize probability among unfilled roles only
                    normalized_prob = prob / total_prob if total_prob > 0 else 1.0 / len(unfilled_roles)
                    role_fill[role] = role_fill.get(role, 0.0) + normalized_prob

        return role_fill

    def _get_unfilled_roles(self, role_fill: dict[str, float]) -> set[str]:
        """Get roles that are not yet filled (< ROLE_FILL_THRESHOLD)."""
        return {role for role in self.ALL_ROLES if role_fill.get(role, 0.0) < ROLE_FILL_THRESHOLD}

    def _compute_flag(self, result: dict) -> str | None:
        """Compute recommendation flag for UI badges.

        Thresholds:
        - LOW_CONFIDENCE: confidence < 0.7 (possible range is 0.65-1.0)
        - SURPRISE_PICK: low meta/tournament_priority but high proficiency
        """
        if result["confidence"] < 0.7:
            return "LOW_CONFIDENCE"

        # Check for surprise pick: low meta strength but high player comfort
        # In simulator mode, use tournament_priority instead of meta
        meta_score = result["components"].get("tournament_priority")
        if meta_score is None:
            meta_score = result["components"].get("meta", 0)

        if meta_score < 0.4 and result["components"].get("proficiency", 0) >= 0.7:
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

        # Matchup/Counter - combined lane and team matchup advantage
        matchup_counter = components.get("matchup_counter", 0.5)
        if matchup_counter >= 0.6:
            reasons.append("Strong matchups vs enemy")
        elif matchup_counter >= 0.55:
            reasons.append("Favorable matchups")

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
