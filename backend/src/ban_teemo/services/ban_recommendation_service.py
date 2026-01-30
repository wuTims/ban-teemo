"""Ban recommendation service targeting enemy player pools."""
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ban_teemo.services.archetype_service import ArchetypeService
from ban_teemo.services.scorers import FlexResolver, MatchupCalculator, MetaScorer, ProficiencyScorer
from ban_teemo.services.synergy_service import SynergyService
from ban_teemo.utils.role_normalizer import normalize_role

if TYPE_CHECKING:
    from ban_teemo.repositories.draft_repository import DraftRepository


class BanRecommendationService:
    """Generates ban recommendations based on enemy team analysis."""

    def __init__(
        self,
        knowledge_dir: Optional[Path] = None,
        draft_repository: Optional["DraftRepository"] = None
    ):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parents[4] / "knowledge"

        self.meta_scorer = MetaScorer(knowledge_dir)
        self.proficiency_scorer = ProficiencyScorer(knowledge_dir)
        self.matchup_calculator = MatchupCalculator(knowledge_dir)
        self.flex_resolver = FlexResolver(knowledge_dir)
        self.archetype_service = ArchetypeService(knowledge_dir)
        self.synergy_service = SynergyService(knowledge_dir)
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
                pool_size = len(player_pool)  # Pre-compute once per player for efficiency

                for entry in player_pool[:5]:  # Top 5 per player
                    champ = entry["champion"]
                    if champ in unavailable:
                        continue

                    priority, components = self._calculate_ban_priority(
                        champion=champ,
                        player=player,
                        proficiency=entry,
                        pool_size=pool_size,
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

        # Add high meta picks
        for champ in self.meta_scorer.get_top_meta_champions(limit=15):
            if champ in unavailable:
                continue
            if any(c["champion_name"] == champ for c in ban_candidates):
                continue

            meta_score = self.meta_scorer.get_meta_score(champ)
            if meta_score >= 0.5:
                priority = meta_score * 0.8  # Slightly lower than targeted bans
                ban_candidates.append({
                    "champion_name": champ,
                    "priority": round(priority, 3),
                    "target_player": None,
                    "target_role": None,
                    "reasons": [f"{self.meta_scorer.get_meta_tier(champ) or 'High'}-tier meta pick"],
                    "components": {"meta": round(meta_score, 3)},  # Raw 0-1 score
                })

        # Sort by priority
        ban_candidates.sort(key=lambda x: -x["priority"])
        return ban_candidates[:limit]

    def _calculate_ban_priority(
        self,
        champion: str,
        player: dict,
        proficiency: dict,
        pool_size: int = 0,
        is_phase_1: bool = True,
    ) -> tuple[float, dict[str, float]]:
        """Calculate ban priority score using explicit tiered priority.

        TIERED PRIORITY SYSTEM (Phase 1):
            Tier 1 (Highest): High proficiency + high presence (in pool + meta power)
            Tier 2 (High):    High proficiency only (pool targeting)
            Tier 3 (Medium):  High presence only (global power)
            Tier 4 (Lower):   General meta bans

        Base weights: proficiency(30%), meta(25%), presence(25%), flex(20%)
        Tier bonuses applied on top for combined conditions.
        """
        components: dict[str, float] = {}

        if is_phase_1:
            # Phase 1: Tiered power pick priority

            # Calculate base components
            meta_score = self.meta_scorer.get_meta_score(champion)
            presence = self._get_presence_score(champion)
            flex = self._get_flex_value(champion)
            prof_score = proficiency["score"]
            conf = proficiency.get("confidence", "LOW")

            # Determine tier conditions
            is_high_proficiency = prof_score >= 0.7 and conf in {"HIGH", "MEDIUM"}
            is_high_presence = presence >= 0.25
            is_in_pool = proficiency.get("games", 0) >= 2

            # Store RAW 0-1 scores for display, apply weights only for priority
            # Weights: prof 30%, meta 25%, presence 25%, flex 20%
            components["proficiency"] = round(prof_score, 3)  # Raw 0-1
            components["meta"] = round(meta_score, 3)         # Raw 0-1
            components["presence"] = round(presence, 3)       # Raw 0-1
            components["flex"] = round(flex, 3)               # Raw 0-1

            # Calculate weighted priority
            base_priority = (
                prof_score * 0.30
                + meta_score * 0.25
                + presence * 0.25
                + flex * 0.20
            )

            # Apply tier bonuses
            tier_bonus = 0.0
            meta_tier_bonus = 0.0
            if is_high_proficiency and is_high_presence and is_in_pool:
                # TIER 1: High proficiency + high presence + in pool
                # High-meta champions get extra weight in Tier 1 (worth banning even without
                # perfect player targeting). Domain expert feedback: meta should influence
                # which comfort picks are worth targeting.
                tier_bonus = 0.15
                meta_tier_bonus = meta_score * 0.10  # 10% additional meta weight for Tier 1
                components["tier"] = "T1_POOL_AND_POWER"
                components["meta_tier_bonus"] = round(meta_tier_bonus, 3)
            elif is_high_proficiency and is_in_pool:
                # TIER 2: High proficiency, in pool (comfort pick targeting)
                tier_bonus = 0.10
                components["tier"] = "T2_POOL_TARGET"
            elif is_high_presence:
                # TIER 3: High presence only (global power ban)
                tier_bonus = 0.05
                components["tier"] = "T3_GLOBAL_POWER"
            else:
                # TIER 4: General meta ban
                tier_bonus = 0.0
                components["tier"] = "T4_GENERAL"

            components["tier_bonus"] = round(tier_bonus, 3)

            # Pool depth exploitation (additive - shallow pools = higher impact)
            pool_bonus = 0.0
            if pool_size >= 1:
                if pool_size <= 3:
                    pool_bonus = 0.08
                elif pool_size <= 5:
                    pool_bonus = 0.04
            components["pool_depth_bonus"] = round(pool_bonus, 3)

            priority = base_priority + tier_bonus + pool_bonus + meta_tier_bonus
        else:
            # Phase 2: Store RAW 0-1 scores for display, apply weights for priority
            prof_score = proficiency["score"]
            components["proficiency"] = round(prof_score, 3)  # Raw 0-1

            meta_score = self.meta_scorer.get_meta_score(champion)
            components["meta"] = round(meta_score, 3)  # Raw 0-1

            games = proficiency.get("games", 0)
            comfort = min(1.0, games / 10)
            components["comfort"] = round(comfort, 3)  # Raw 0-1

            conf = proficiency.get("confidence", "LOW")
            conf_value = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}.get(conf, 0)
            components["confidence"] = round(conf_value, 3)  # Raw 0-1

            pool_depth = 0.0
            if pool_size >= 1:
                if pool_size <= 3:
                    pool_depth = 1.0  # Shallow pool - high impact
                elif pool_size <= 5:
                    pool_depth = 0.5  # Medium pool
                # Deep pools (6+) = 0
            components["pool_depth"] = round(pool_depth, 3)  # Raw 0-1

            # Weighted priority calculation (weights: prof 40%, meta 30%, comfort 15%, conf 10%, pool 5%)
            priority = (
                prof_score * 0.40
                + meta_score * 0.30
                + comfort * 0.15
                + conf_value * 0.10
                + pool_depth * 0.05
            )

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

        tier = self.meta_scorer.get_meta_tier(champion)
        if tier in ["S", "A"]:
            reasons.append(f"{tier}-tier meta champion")

        if priority >= 0.8:
            reasons.append("High priority target")

        return reasons if reasons else ["General ban recommendation"]

    def _get_global_power_bans(self, unavailable: set[str]) -> list[dict]:
        """Get high-presence power picks as ban candidates.

        These are always considered regardless of enemy player pool data.

        Returns:
            List of ban candidates based on global meta presence
        """
        candidates = []

        for champ in self.meta_scorer.get_top_meta_champions(limit=15):
            if champ in unavailable:
                continue

            meta_score = self.meta_scorer.get_meta_score(champ)
            presence = self._get_presence_score(champ)
            flex_value = self._get_flex_value(champ)

            # Only include if high enough presence (>= 20%)
            if presence < 0.20:
                continue

            # Calculate priority: presence(40%) + meta(35%) + flex(25%)
            priority = presence * 0.40 + meta_score * 0.35 + flex_value * 0.25

            reasons = []
            tier = self.meta_scorer.get_meta_tier(champ)
            if tier in ["S", "A"]:
                reasons.append(f"{tier}-tier power pick")
            if presence >= 0.30:
                reasons.append(f"High presence ({presence:.0%})")
            if flex_value >= 0.5:
                reasons.append("Role flex value")

            candidates.append({
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": reasons if reasons else ["Global power ban"],
                "components": {
                    "presence": round(presence * 0.40, 3),
                    "meta": round(meta_score * 0.35, 3),
                    "flex": round(flex_value * 0.25, 3),
                    "tier": "T3_GLOBAL_POWER",
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

        # Get top meta champions as potential counters
        meta_champs = self.meta_scorer.get_top_meta_champions(limit=30)

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
            # Average counter score * meta score
            avg_counter = sum(c["score"] for c in data["counters"]) / len(data["counters"])
            meta_score = self.meta_scorer.get_meta_score(champ)

            counter_component = avg_counter * 0.6
            meta_component = meta_score * 0.4
            priority = counter_component + meta_component
            countered_champs = [c["vs"] for c in data["counters"]]

            result.append({
                "champion_name": champ,
                "priority": round(priority, 3),
                "target_player": None,
                "target_role": None,
                "reasons": [f"Counters {', '.join(countered_champs)}"],
                "components": {
                    "counter": round(counter_component, 3),
                    "meta": round(meta_component, 3),
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
        """Get champion's presence rate as a score.

        Presence = pick_rate + ban_rate (how contested is this pick?)

        Returns:
            Float 0.0-1.0 representing presence
        """
        return self.meta_scorer.get_presence(champion)

    def _get_flex_value(self, champion: str) -> float:
        """Get champion's flex pick value based on role versatility.

        Champions that can play multiple roles are harder to plan against
        and more valuable to ban.

        Returns:
            Float 0.0-0.8 representing flex value
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

        Args:
            champion: Champion to potentially ban
            enemy_picks: Champions enemy has already picked
            enemy_players: Enemy player info with 'name' and 'role'

        Returns:
            Float 0.0-0.8 representing role denial value
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

        # Get meta champions as potential ban targets
        meta_champs = set(self.meta_scorer.get_top_meta_champions(limit=30))

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
            meta_score = self.meta_scorer.get_meta_score(champ)

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

            # Base component scores
            if counters_us:
                components["counter_our_picks"] = round(counter_strength * 0.30, 3)
                reasons.append("Counters our picks")
            if arch_score > 0.1:
                components["archetype_counter"] = round(arch_score * 0.25, 3)
                reasons.append("Fits enemy's archetype")
            if synergy_score > 0.1:
                components["synergy_denial"] = round(synergy_score * 0.20, 3)
                reasons.append("Synergizes with enemy")
            if role_score > 0.1:
                components["role_denial"] = round(role_score * 0.15, 3)
                reasons.append("Fills enemy's role")
            components["meta"] = round(meta_score * 0.10, 3)
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
