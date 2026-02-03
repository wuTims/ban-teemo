"""Ban recommendation service targeting enemy player pools."""
import math
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.scorers import (
    FlexResolver,
    MatchupCalculator,
    ProficiencyScorer,
    RolePhaseScorer,
    TournamentScorer,
)
from ban_teemo.services.synergy_service import SynergyService
from ban_teemo.utils.role_normalizer import normalize_role

if TYPE_CHECKING:
    from ban_teemo.repositories.draft_repository import DraftRepository


class BanRecommendationService:
    """Generates ban recommendations based on enemy team analysis."""

    def __init__(
        self,
        knowledge_dir: Optional[Path] = None,
        draft_repository: Optional["DraftRepository"] = None,
        tournament_data_file: Optional[str] = None,
    ):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"

        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir, tournament_data_file=tournament_data_file)
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
        self.tournament_scorer = TournamentScorer(knowledge_dir, data_file=tournament_data_file)
        self.role_phase_scorer = RolePhaseScorer(knowledge_dir)
        self._draft_repository = draft_repository

    def get_ban_recommendations(
        self,
        enemy_team_id: str,
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        phase: str,
        enemy_players: Optional[list[dict]] = None,
        limit: int = 5
    ) -> list[dict]:
        """Generate ban recommendations targeting enemy team.

        Args:
            enemy_team_id: ID of enemy team (used for future roster lookup)
            our_picks: Champions already picked by our team
            enemy_picks: Champions already picked by enemy team
            banned: Champions already banned
            phase: Current draft phase (BAN_PHASE_1, BAN_PHASE_2, etc.)
            enemy_players: Optional list of enemy players with 'name' and 'role' keys
            limit: Maximum recommendations to return

        Returns:
            List of ban recommendations with priority scores
        """
        unavailable = set(banned) | set(our_picks) | set(enemy_picks)
        is_phase_1 = "1" in phase

        ban_candidates = []

        # Auto-lookup roster if not provided but repository is available
        if enemy_players is None and self._draft_repository and enemy_team_id:
            enemy_players = self._lookup_enemy_roster(enemy_team_id)

        # If enemy players provided (or looked up), target their champion pools
        if enemy_players:
            for player in enemy_players:
                player_pool = self.proficiency_scorer.get_player_champion_pool(
                    player["name"], min_games=2
                )

                for entry in player_pool[:5]:  # Top 5 per player
                    champ = entry["champion"]
                    if champ in unavailable:
                        continue

                    priority, components = self._calculate_ban_priority(
                        champion=champ,
                        player=player,
                        proficiency=entry,
                        is_phase_1=is_phase_1,
                    )

                    ban_candidates.append({
                        "champion_name": champ,
                        "priority": priority,
                        "target_player": player["name"],
                        "target_role": player.get("role"),
                        "reasons": self._generate_reasons(champ, player, entry, priority),
                        "components": components,
                    })

        # ALWAYS add global power picks for Phase 1 (regardless of player data)
        if is_phase_1:
            global_power_bans = self._get_global_power_bans(unavailable)
            for power_ban in global_power_bans:
                existing = next(
                    (c for c in ban_candidates if c["champion_name"] == power_ban["champion_name"]),
                    None
                )
                if existing:
                    # Boost if already targeted AND high presence
                    existing["priority"] = min(1.0, existing["priority"] + 0.1)
                    if power_ban["reasons"]:
                        existing["reasons"].extend(power_ban["reasons"])
                else:
                    ban_candidates.append(power_ban)

        # Phase 2: Add contextual bans (archetype, synergy, role denial)
        if not is_phase_1:
            contextual_bans = self._get_contextual_phase2_bans(
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                enemy_players=enemy_players or [],
                unavailable=unavailable,
            )

            for ctx_ban in contextual_bans:
                # Check if already in candidates and boost priority if so
                existing = next(
                    (c for c in ban_candidates if c["champion_name"] == ctx_ban["champion_name"]),
                    None
                )
                if existing:
                    # Merge contextual scores
                    existing["priority"] = min(1.0, existing["priority"] + ctx_ban["priority"] * 0.5)
                    existing["components"].update(ctx_ban["components"])
                    existing["reasons"].extend(ctx_ban["reasons"])
                else:
                    ban_candidates.append(ctx_ban)

        # Add high tournament priority picks
        for champ in self.tournament_scorer.get_top_priority_champions(limit=15):
            if champ in unavailable:
                continue
            if any(c["champion_name"] == champ for c in ban_candidates):
                continue

            t_priority = self.tournament_scorer.get_priority(champ)
            if t_priority >= 0.25:
                priority = t_priority * 0.8  # Slightly lower than targeted bans
                tier = TournamentScorer.priority_to_tier(t_priority)
                ban_candidates.append({
                    "champion_name": champ,
                    "priority": round(priority, 3),
                    "target_player": None,
                    "target_role": None,
                    "reasons": [f"{tier}-tier meta pick"],
                    "components": {"tournament_priority": round(t_priority, 3)},
                })

        # Sort by priority
        ban_candidates.sort(key=lambda x: -x["priority"])
        return ban_candidates[:limit]

    def _calculate_ban_priority(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        is_phase_1: bool = True,
    ) -> tuple[float, dict[str, float]]:
        """Calculate ban priority score using tournament-first tiered priority.

        PHASE 1 - Meta power and flex threats prioritized:
            Tier 1 (Highest): Signature power pick (high tournament priority + high proficiency)
            Tier 2 (High):    Meta power (high tournament priority global threat)
            Tier 3 (Medium):  Comfort pick (player-specific targeting)
            Tier 4 (Lower):   General ban

        Phase 1 weights: tournament_priority(60%), flex(25%), proficiency(15%)

        PHASE 2 - Strategic disruption focus:
            Synergy/counter scoring handled by _get_contextual_phase2_bans.
            This function handles player-targeted portion.

        Phase 2 weights: tournament_priority(50%), proficiency(25%), comfort(15%), confidence(10%)
        """
        components: dict[str, float] = {}

        if is_phase_1:
            # Phase 1: Meta power and flex threats prioritized
            # LLM priority order: meta power > flex threats > player targeting > blind picks

            # Calculate base components
            tournament_priority = self.tournament_scorer.get_priority(champion)
            flex = self._get_flex_value(champion)
            prof_score = proficiency["score"]
            conf = proficiency.get("confidence", "LOW")

            # Determine tier conditions
            is_high_proficiency = prof_score >= 0.7 and conf in {"HIGH", "MEDIUM"}
            is_in_pool = proficiency.get("games", 0) >= 2

            # tournament_priority 60%, flex 25%, proficiency 15%
            WEIGHT_TOURNAMENT = 0.60
            WEIGHT_FLEX = 0.25
            WEIGHT_PROF = 0.15

            components["tournament_priority"] = round(tournament_priority * WEIGHT_TOURNAMENT, 3)
            components["flex"] = round(flex * WEIGHT_FLEX, 3)
            components["proficiency"] = round(prof_score * WEIGHT_PROF, 3)

            base_priority = (
                tournament_priority * WEIGHT_TOURNAMENT
                + flex * WEIGHT_FLEX
                + prof_score * WEIGHT_PROF
            )

            # Tier conditions based on tournament priority
            is_high_tournament = tournament_priority >= 0.50

            # Apply tier bonuses (reduced since base weights already prioritize meta)
            tier_bonus = 0.0
            tier_high_meta = is_high_tournament

            if is_high_proficiency and tier_high_meta and is_in_pool:
                # TIER 1: High meta + high proficiency (signature power pick)
                tier_bonus = 0.10
                components["tier"] = "T1_SIGNATURE_POWER"
            elif tier_high_meta:
                # TIER 2: High presence/meta power (global threat)
                tier_bonus = 0.05
                components["tier"] = "T2_META_POWER"
            elif is_high_proficiency and is_in_pool:
                # TIER 3: Player comfort pick (lower priority in Phase 1)
                tier_bonus = 0.03
                components["tier"] = "T3_COMFORT_PICK"
            else:
                # TIER 4: General ban
                tier_bonus = 0.0
                components["tier"] = "T4_GENERAL"

            components["tier_bonus"] = round(tier_bonus, 3)

            priority = base_priority + tier_bonus

            # Apply role-phase penalty for player-targeted bans
            # Softer penalty (sqrt) since we don't know exactly when enemy will pick
            target_role = player.get("role")
            if target_role:
                pick_mult = self.role_phase_scorer.get_multiplier(target_role, total_picks=0)
                ban_mult = math.sqrt(pick_mult)  # Softer penalty for bans
                priority *= ban_mult
                components["role_phase_penalty"] = round(ban_mult, 3)
        else:
            # Phase 2: Strategic bans - synergy disruption and counter denial
            # LLM priority: break synergies > deny counters > archetype enablers > player comfort
            # Note: synergy/counter scoring is handled by _get_contextual_phase2_bans
            # This function handles player-targeted portion

            prof_score = proficiency["score"]
            tournament_priority = self.tournament_scorer.get_priority(champion)

            games = proficiency.get("games", 0)
            comfort = min(1.0, games / 10)

            conf = proficiency.get("confidence", "LOW")
            conf_value = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}.get(conf, 0)

            # Phase 2 weights: tournament meta + strategic context
            # tournament_priority 50%, proficiency 25%, comfort 15%, confidence 10%
            WEIGHT_TOURNAMENT = 0.50
            WEIGHT_PROF = 0.25
            WEIGHT_COMFORT = 0.15
            WEIGHT_CONF = 0.10

            # Store WEIGHTED scores for display
            components["tournament_priority"] = round(tournament_priority * WEIGHT_TOURNAMENT, 3)
            components["proficiency"] = round(prof_score * WEIGHT_PROF, 3)
            components["comfort"] = round(comfort * WEIGHT_COMFORT, 3)
            components["confidence"] = round(conf_value * WEIGHT_CONF, 3)

            priority = (
                tournament_priority * WEIGHT_TOURNAMENT
                + prof_score * WEIGHT_PROF
                + comfort * WEIGHT_COMFORT
                + conf_value * WEIGHT_CONF
            )

            # Apply role-phase penalty for phase 2 (jungle/mid bans less valuable late)
            target_role = player.get("role")
            if target_role:
                # Phase 2 starts at pick 6, use total_picks=6 for phase lookup
                pick_mult = self.role_phase_scorer.get_multiplier(target_role, total_picks=6)
                ban_mult = math.sqrt(pick_mult)  # Softer penalty for bans
                priority *= ban_mult
                components["role_phase_penalty"] = round(ban_mult, 3)

        return (round(min(1.0, priority), 3), components)

    def _generate_reasons(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        priority: float
    ) -> list[str]:
        """Generate human-readable ban reasons."""
        reasons = []

        games = proficiency.get("games", 0)
        if games >= 5:
            reasons.append(f"{player['name']}'s comfort pick ({games} games)")
        elif games >= 2:
            reasons.append(f"In {player['name']}'s pool")

        tier = TournamentScorer.priority_to_tier(self.tournament_scorer.get_priority(champion))
        if tier in ["S", "A"]:
            reasons.append(f"{tier}-tier meta champion")

        if priority >= 0.8:
            reasons.append("High priority target")

        return reasons if reasons else ["General ban recommendation"]

    def _get_global_power_bans(self, unavailable: set[str]) -> list[dict]:
        """Get high-priority power picks as ban candidates.

        These are always considered regardless of enemy player pool data.
        Uses tournament_priority as the primary signal.

        Returns:
            List of ban candidates based on tournament priority
        """
        candidates = []

        # Collect candidate champions from tournament priority
        candidate_champs = set(self.tournament_scorer.get_top_priority_champions(limit=20))

        for champ in candidate_champs:
            if champ in unavailable:
                continue

            flex_value = self._get_flex_value(champ)
            tournament_priority = self.tournament_scorer.get_priority(champ)

            # Only include if high enough tournament priority (>= 30%)
            if tournament_priority < 0.30:
                continue

            # Calculate priority: tournament(75%) + flex(25%)
            priority = (
                tournament_priority * 0.75
                + flex_value * 0.25
            )

            reasons = []
            if tournament_priority >= 0.50:
                reasons.append(f"High tournament priority ({tournament_priority:.0%})")
            tier = TournamentScorer.priority_to_tier(tournament_priority)
            if tier in ["S", "A"]:
                reasons.append(f"{tier}-tier power pick")
            if flex_value >= 0.5:
                reasons.append("Role flex value")

            candidates.append({
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": reasons if reasons else ["Global power ban"],
                "components": {
                    "tournament_priority": round(tournament_priority * 0.75, 3),
                    "flex": round(flex_value * 0.25, 3),
                    "tier": "T2_META_POWER",
                },
            })

        return sorted(candidates, key=lambda x: -x["priority"])[:10]

    def _get_counter_pick_bans(
        self,
        our_picks: list[str],
        unavailable: set[str]
    ) -> list[dict]:
        """Find champions that counter our picks for Phase 2 bans.

        Uses MatchupCalculator to identify champions with favorable matchups
        against our picks.
        """
        counter_candidates: dict[str, dict] = {}

        # Get top tournament priority champions as potential counters
        meta_champs = self.tournament_scorer.get_top_priority_champions(limit=30)

        for our_champ in our_picks:
            for potential_counter in meta_champs:
                if potential_counter in unavailable:
                    continue
                if potential_counter in our_picks:
                    continue

                # Check if this champion counters our pick
                # We use team matchup since we may not know exact roles
                matchup = self.matchup_calculator.get_team_matchup(
                    our_champion=our_champ,
                    enemy_champion=potential_counter
                )

                # If our champion has < 0.45 win rate against this counter,
                # it's a strong counter we should consider banning
                if matchup["score"] < 0.45 and matchup["data_source"] != "none":
                    counter_score = 1.0 - matchup["score"]  # Higher score = better counter

                    if potential_counter not in counter_candidates:
                        counter_candidates[potential_counter] = {
                            "champion_name": potential_counter,
                            "priority": 0.0,
                            "target_player": None,
                            "target_role": None,
                            "counters": [],
                            "reasons": []
                        }

                    counter_candidates[potential_counter]["counters"].append({
                        "vs": our_champ,
                        "score": counter_score
                    })

        # Calculate final priority for counter bans
        result = []
        for champ, data in counter_candidates.items():
            # Average counter score * tournament priority
            avg_counter = sum(c["score"] for c in data["counters"]) / len(data["counters"])
            t_priority = self.tournament_scorer.get_priority(champ)

            counter_component = avg_counter * 0.6
            priority_component = t_priority * 0.4
            priority = counter_component + priority_component
            countered_champs = [c["vs"] for c in data["counters"]]

            result.append({
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": [f"Counters {', '.join(countered_champs)}"],
                "components": {
                    "counter": round(counter_component, 3),
                    "tournament_priority": round(priority_component, 3),
                },
            })

        return sorted(result, key=lambda x: -x["priority"])[:5]

    def _lookup_enemy_roster(self, enemy_team_id: str) -> list[dict]:
        """Lookup enemy roster from repository.

        Converts repository format to expected player format.

        Args:
            enemy_team_id: The enemy team's ID

        Returns:
            List of player dicts with 'name' and 'role' keys
        """
        if not self._draft_repository:
            return []

        roster = self._draft_repository.get_team_roster(enemy_team_id)
        if not roster:
            return []

        players = []
        for player in roster:
            # Role is already normalized by repository, but ensure consistency
            role = normalize_role(player.get("role"))

            players.append({
                "name": player.get("player_name", ""),
                "role": role,
                "player_id": player.get("player_id")
            })

        return players

    def _get_presence_score(self, champion: str) -> float:
        """Get champion's contestation rate as a score.

        Uses tournament priority (pick+ban rate from pro play) as the
        presence signal. This ensures era-appropriate data is used for
        both replays and simulator mode.

        Returns:
            Float 0.0-1.0 representing tournament presence
        """
        return self.tournament_scorer.get_priority(champion)

    def _get_flex_value(self, champion: str) -> float:
        """Get champion's flex pick value based on role versatility.

        Champions that can play multiple roles are harder to plan against
        and more valuable to ban.

        WHY FLEX MATTERS: Flex picks create draft uncertainty. If Ambessa
        can go top or mid, the enemy can't tell which lane to counter.
        Banning flex picks removes this strategic ambiguity, making
        enemy draft intentions more readable.

        Scoring rationale:
        - 0.8 for 3+ roles: True flex threats like Aurora, Ambessa
        - 0.5 for 2 roles: Common dual-flex like Gragas (top/jungle)
        - 0.2 for 1 role: Single-role specialists are predictable

        Returns:
            Float 0.0-0.8 representing flex value (capped to avoid over-weighting)
        """
        probs = self.flex_resolver.get_role_probabilities(champion)
        if not probs:
            return 0.2  # Unknown - assume single role

        # Count roles with >= 15% probability (viable roles)
        viable_roles = [r for r, p in probs.items() if p >= 0.15]

        if len(viable_roles) >= 3:
            return 0.8  # True flex (3+ roles)
        elif len(viable_roles) >= 2:
            return 0.5  # Dual flex
        return 0.2  # Single role

    def _get_archetype_counter_score(self, champion: str, enemy_picks: list[str]) -> float:
        """Calculate how much banning this champion disrupts enemy's archetype.

        WHY ARCHETYPE DISRUPTION MATTERS: Teams build toward a game plan
        (teamfight, split-push, pick-comp). If enemy picks Malphite + Orianna,
        they're likely building teamfight. Banning Yasuo/Samira denies wombo
        combo completion. Disrupting archetype coherence weakens enemy's
        win condition execution.

        Scoring logic:
        - contribution (60%): How much does this champ add to enemy's archetype?
        - alignment_boost (40%): Would this champ significantly improve their comp coherence?

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked

        Returns:
            Float 0.0-1.0 representing archetype disruption value
        """
        if not enemy_picks:
            return 0.0

        # Get enemy's emerging archetype
        enemy_arch = self.archetype_service.calculate_team_archetype(enemy_picks)
        enemy_primary = enemy_arch.get("primary")

        if not enemy_primary:
            return 0.0

        # How much does this champion contribute to enemy's direction?
        contribution = self.archetype_service.get_contribution_to_archetype(
            champion, enemy_primary
        )

        # Also check alignment boost - would adding this champion increase enemy's alignment?
        current_alignment = enemy_arch.get("alignment", 0)
        with_champ = self.archetype_service.calculate_team_archetype(
            enemy_picks + [champion]
        )
        new_alignment = with_champ.get("alignment", 0)
        alignment_boost = max(0, new_alignment - current_alignment)

        # Combine contribution and alignment boost
        return round(contribution * 0.6 + alignment_boost * 0.4, 3)

    def _get_synergy_denial_score(self, champion: str, enemy_picks: list[str]) -> float:
        """Calculate synergy denial value of banning this champion.

        Would this champion complete a strong synergy with enemy picks?

        WHY SYNERGY DENIAL MATTERS: Synergies amplify team effectiveness
        beyond individual champion strength. Yasuo + knock-up, Yone + engage,
        or ADC + enchanter pairs can dominate games. Denying key synergy
        completions forces enemy into suboptimal combinations.

        Scaling note: Synergy gains are typically 0.0-0.2 per champion added.
        Multiply by 3 to normalize to 0-1 scale for comparison with other
        ban priority factors.

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked

        Returns:
            Float 0.0-1.0 representing synergy denial value
        """
        if not enemy_picks:
            return 0.0

        # Calculate synergy gain if enemy added this champion
        synergy_with = self.synergy_service.calculate_team_synergy(
            enemy_picks + [champion]
        )
        synergy_without = self.synergy_service.calculate_team_synergy(enemy_picks)

        synergy_gain = synergy_with["total_score"] - synergy_without["total_score"]

        # Scale the gain (typical range is 0.0-0.2) to 0-1
        return round(max(0, min(1.0, synergy_gain * 3)), 3)

    def _get_role_denial_score(
        self,
        champion: str,
        enemy_picks: list[str],
        enemy_players: list[dict]
    ) -> float:
        """Calculate role denial value of banning this champion.

        Does banning this deny a role the enemy still needs to fill?

        WHY ROLE DENIAL MATTERS: Late draft picks for unfilled roles are
        constrained. If enemy ADC hasn't picked yet, banning their ADC's
        comfort picks forces them onto unfamiliar champions. This is
        especially impactful in Bo5 when you've seen their pool.

        Scoring rationale:
        - 0.8: Champion is in the specific player's pool AND fills an unfilled role.
               Maximum impact - directly targeting player weakness.
        - 0.4: Champion fills unfilled role but not necessarily in player's pool.
               General denial - reduces enemy's options even if not targeting player.
        - 0.0: Champion doesn't fill any unfilled roles or all roles are already covered.

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked
            enemy_players: Enemy player info with 'name' and 'role'

        Returns:
            Float 0.0-0.8 representing role denial value (capped below 1.0 since
            role denial alone isn't decisive without other factors)
        """
        if not enemy_players:
            return 0.0

        # Infer which roles enemy has filled
        filled_roles = set()
        for pick in enemy_picks:
            probs = self.flex_resolver.get_role_probabilities(pick)
            if probs:
                primary_role = max(probs, key=probs.get)
                filled_roles.add(primary_role)

        unfilled_roles = {"top", "jungle", "mid", "bot", "support"} - filled_roles

        if not unfilled_roles:
            return 0.0

        # Can this champion fill an unfilled role?
        champ_probs = self.flex_resolver.get_role_probabilities(champion)
        if not champ_probs:
            return 0.0

        for role in unfilled_roles:
            if champ_probs.get(role, 0) >= 0.25:  # Viable in this role
                # Check if any enemy player in this role has this in their pool
                player = next(
                    (p for p in enemy_players if p.get("role") == role),
                    None
                )
                if player:
                    pool = self.proficiency_scorer.get_player_champion_pool(
                        player["name"], min_games=2
                    )
                    pool_champs = [e["champion"] for e in pool[:10]]
                    if champion in pool_champs:
                        return 0.8  # High denial - in player's pool for unfilled role
                return 0.4  # General denial - fills unfilled role

        return 0.0

    def _get_contextual_phase2_bans(
        self,
        our_picks: list[str],
        enemy_picks: list[str],
        enemy_players: list[dict],
        unavailable: set[str],
    ) -> list[dict]:
        """Generate contextual Phase 2 ban recommendations with TIERED PRIORITY.

        TIERED PRIORITY SYSTEM (Phase 2):
            Tier 1 (Highest): Counters our picks + in enemy pool
            Tier 2 (High):    Completes enemy archetype + in pool
            Tier 3 (Medium):  Counters our picks (regardless of pool)
            Tier 4 (Lower):   General archetype/synergy counter

        Considers:
        - Counter to our picks: Champions that counter what we've picked
        - Archetype completion: Champions that complete enemy's comp direction
        - Synergy denial: Champions that would synergize with enemy picks
        - Role denial: Champions that fill roles enemy still needs

        Returns:
            List of ban candidates with contextual scoring and tier info
        """
        candidates: dict[str, dict] = {}

        # Get tournament priority champions as potential ban targets
        meta_champs = set(self.tournament_scorer.get_top_priority_champions(limit=30))

        # Also include enemy player pool champions for unfilled roles
        filled_roles = set()
        for pick in enemy_picks:
            probs = self.flex_resolver.get_role_probabilities(pick)
            if probs:
                primary = max(probs, key=probs.get)
                filled_roles.add(primary)
        unfilled_roles = {"top", "jungle", "mid", "bot", "support"} - filled_roles

        enemy_pool_champs = set()
        for player in enemy_players:
            if player.get("role") in unfilled_roles:
                pool = self.proficiency_scorer.get_player_champion_pool(
                    player["name"], min_games=2
                )
                for entry in pool[:8]:
                    enemy_pool_champs.add(entry["champion"])
                    meta_champs.add(entry["champion"])

        for champ in meta_champs:
            if champ in unavailable:
                continue

            components: dict[str, float] = {}
            reasons: list[str] = []

            # Calculate contextual scores
            arch_score = self._get_archetype_counter_score(champ, enemy_picks)
            synergy_score = self._get_synergy_denial_score(champ, enemy_picks)
            role_score = self._get_role_denial_score(champ, enemy_picks, enemy_players)
            tournament_priority = self.tournament_scorer.get_priority(champ)

            # Check if counters our picks
            counters_us = False
            counter_strength = 0.0
            for our_pick in our_picks:
                matchup = self.matchup_calculator.get_team_matchup(our_pick, champ)
                if matchup["score"] < 0.45:  # This champ counters our pick
                    counters_us = True
                    counter_strength = max(counter_strength, 1.0 - matchup["score"])

            is_in_enemy_pool = champ in enemy_pool_champs

            # Determine tier and calculate priority
            tier_bonus = 0.0
            if counters_us and is_in_enemy_pool:
                # TIER 1: Counters our picks + in enemy pool
                tier_bonus = 0.20
                components["tier"] = "T1_COUNTER_AND_POOL"
                reasons.append("Counters our picks AND in enemy pool")
            elif arch_score > 0.3 and is_in_enemy_pool:
                # TIER 2: Completes enemy archetype + in pool
                tier_bonus = 0.15
                components["tier"] = "T2_ARCHETYPE_AND_POOL"
                reasons.append("Completes enemy comp AND in pool")
            elif counters_us:
                # TIER 3: Counters our picks (regardless of pool)
                tier_bonus = 0.10
                components["tier"] = "T3_COUNTER_ONLY"
                reasons.append("Counters our picks")
            elif arch_score > 0.2 or synergy_score > 0.2 or role_score > 0.2:
                # TIER 4: General contextual ban
                tier_bonus = 0.0
                components["tier"] = "T4_CONTEXTUAL"
            else:
                continue  # Skip if no meaningful contextual value

            # Base component scores - tournament_priority as foundation
            # Weights: tournament 25%, contextual factors 75%
            components["tournament_priority"] = round(tournament_priority * 0.25, 3)
            if counters_us:
                components["counter_our_picks"] = round(counter_strength * 0.25, 3)
            if arch_score > 0.1:
                components["archetype_counter"] = round(arch_score * 0.20, 3)
                reasons.append("Fits enemy's archetype")
            if synergy_score > 0.1:
                components["synergy_denial"] = round(synergy_score * 0.15, 3)
                reasons.append("Synergizes with enemy")
            if role_score > 0.1:
                components["role_denial"] = round(role_score * 0.10, 3)
                reasons.append("Fills enemy's role")
            components["tier_bonus"] = round(tier_bonus, 3)

            # Calculate priority
            priority = sum(v for k, v in components.items() if k != "tier")

            candidates[champ] = {
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": list(set(reasons[:3])) if reasons else ["Contextual ban"],
                "components": components,
            }

        # Sort by priority and return top candidates
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda x: -x["priority"]
        )
        return sorted_candidates[:10]
